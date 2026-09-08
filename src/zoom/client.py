"""Zoom client using the Zoom REST API directly.

Auth is Server-to-Server OAuth: the account's own credentials are exchanged
for a short-lived token, so there is no browser flow and no third-party
broker in the path.

This replaced a Composio-brokered transport on 2026-09-08. Composio retired
its v2 action API (`/api/v2/actions/{ACTION}/execute` now returns 410 Gone),
which took every Zoom tool down at once. Talking to api.zoom.us directly
removes that dependency and, as a side effect, makes transcript downloads
work — they need a Zoom bearer token, which the broker never exposed.

Usage:
    from zoom import ZoomClient

    client = ZoomClient(
        account_id="xxx", client_id="xxx", client_secret="xxx"
    )

    # Or from environment / AWS Secrets Manager ('zoom/s2s')
    client = ZoomClient.from_env()

    recordings = await client.list_recordings(from_date="2026-08-01")
"""

import json
import os
import re
import time
from typing import Optional

import httpx

from .models import (
    Meeting,
    MeetingCreate,
    MeetingSummary,
    MeetingTranscript,
    Participant,
    Recording,
    Registrant,
    TranscriptEntry,
)


class ZoomError(Exception):
    """A Zoom API call failed."""


class ZoomClient:
    """Zoom client speaking directly to the Zoom REST API."""

    API_BASE = "https://api.zoom.us/v2"
    TOKEN_URL = "https://zoom.us/oauth/token"

    # Refresh a little before expiry so a call never lands on a dead token.
    _TOKEN_SKEW_SECONDS = 60

    def __init__(
        self,
        account_id: str,
        client_id: str,
        client_secret: str,
        timeout: float = 30.0,
    ):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._client = httpx.AsyncClient(timeout=timeout)
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @classmethod
    def from_env(cls) -> "ZoomClient":
        """Build a client from AWS Secrets Manager or environment variables.

        Secrets Manager `zoom/s2s` is a JSON object with `account_id`,
        `client_id` and `client_secret`.
        """
        account_id = client_id = client_secret = None

        try:
            import boto3
            sm = boto3.client("secretsmanager", region_name="us-east-1")
            secret = json.loads(
                sm.get_secret_value(SecretId="zoom/s2s")["SecretString"]
            )
            account_id = secret.get("account_id")
            client_id = secret.get("client_id")
            client_secret = secret.get("client_secret")
        except Exception:
            pass

        account_id = account_id or os.environ.get("ZOOM_ACCOUNT_ID")
        client_id = client_id or os.environ.get("ZOOM_CLIENT_ID")
        client_secret = client_secret or os.environ.get("ZOOM_CLIENT_SECRET")

        if not (account_id and client_id and client_secret):
            raise ValueError(
                "Missing Zoom credentials. Create a Server-to-Server OAuth app "
                "at marketplace.zoom.us, then store {account_id, client_id, "
                "client_secret} in AWS Secrets Manager at 'zoom/s2s' or set "
                "ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET."
            )

        return cls(
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    # ============== AUTH ==============

    async def _get_token(self) -> str:
        """Return a valid access token, fetching a new one only when needed."""
        if self._token and time.time() < self._token_expires_at:
            return self._token

        response = await self._client.post(
            self.TOKEN_URL,
            params={
                "grant_type": "account_credentials",
                "account_id": self.account_id,
            },
            auth=(self.client_id, self.client_secret),
        )
        if response.status_code != 200:
            raise ZoomError(
                f"Zoom token request failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = (
            time.time() + payload.get("expires_in", 3600) - self._TOKEN_SKEW_SECONDS
        )
        return self._token

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict:
        """Call the Zoom API and return the decoded body."""
        token = await self._get_token()
        response = await self._client.request(
            method,
            f"{self.API_BASE}{path}",
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code >= 400:
            message = response.text
            try:
                message = response.json().get("message", message)
            except Exception:
                pass
            raise ZoomError(f"Zoom {method} {path} failed ({response.status_code}): {message}")

        if not response.content:
            return {}
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ============== MEETINGS ==============

    async def list_meetings(self, meeting_type: str = "upcoming") -> list[Meeting]:
        """List meetings.

        Args:
            meeting_type: 'upcoming', 'scheduled', 'live', or 'pending'
        """
        data = await self._request(
            "GET", "/users/me/meetings",
            params={"type": meeting_type, "page_size": 300},
        )

        return [
            Meeting(
                id=m["id"],
                topic=m["topic"],
                start_time=m["start_time"],
                duration=m["duration"],
                timezone=m.get("timezone", "UTC"),
                join_url=m.get("join_url"),
            )
            for m in data.get("meetings", [])
        ]

    async def create_meeting(self, meeting: MeetingCreate) -> Meeting:
        """Create a new meeting."""
        body = {
            "topic": meeting.topic,
            "type": 2,
            "start_time": meeting.start_time,
            "duration": meeting.duration,
            "timezone": meeting.timezone,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "waiting_room": meeting.waiting_room,
                "auto_recording": meeting.auto_recording,
                "mute_upon_entry": True,
            },
        }
        if meeting.agenda:
            body["agenda"] = meeting.agenda

        data = await self._request("POST", "/users/me/meetings", json_body=body)

        return Meeting(
            id=data["id"],
            topic=data["topic"],
            start_time=data["start_time"],
            duration=data["duration"],
            timezone=data.get("timezone", meeting.timezone),
            join_url=data.get("join_url"),
            start_url=data.get("start_url"),
            password=data.get("password"),
            host_email=data.get("host_email"),
        )

    async def get_meeting(self, meeting_id: int) -> Meeting:
        """Get meeting details."""
        data = await self._request("GET", f"/meetings/{meeting_id}")

        return Meeting(
            id=data["id"],
            topic=data["topic"],
            start_time=data["start_time"],
            duration=data["duration"],
            timezone=data.get("timezone", "UTC"),
            join_url=data.get("join_url"),
            start_url=data.get("start_url"),
            password=data.get("password"),
            agenda=data.get("agenda"),
            status=data.get("status"),
        )

    async def update_meeting(
        self,
        meeting_id: int,
        topic: Optional[str] = None,
        start_time: Optional[str] = None,
        duration: Optional[int] = None,
        agenda: Optional[str] = None,
    ) -> None:
        """Update a meeting."""
        body = {}
        if topic:
            body["topic"] = topic
        if start_time:
            body["start_time"] = start_time
        if duration:
            body["duration"] = duration
        if agenda:
            body["agenda"] = agenda

        await self._request("PATCH", f"/meetings/{meeting_id}", json_body=body)

    async def add_registrant(
        self,
        meeting_id: int,
        email: str,
        first_name: str,
        last_name: str = "",
    ) -> Registrant:
        """Add a meeting registrant."""
        data = await self._request(
            "POST", f"/meetings/{meeting_id}/registrants",
            json_body={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        return Registrant(
            registrant_id=data.get("registrant_id"),
            email=email,
            first_name=first_name,
            last_name=last_name,
            join_url=data.get("join_url"),
        )

    # ============== RECORDINGS ==============

    async def list_recordings(
        self,
        from_date: str,
        to_date: Optional[str] = None,
    ) -> list[Recording]:
        """List cloud recordings in date range."""
        params = {"from": from_date, "page_size": 300}
        if to_date:
            params["to"] = to_date

        data = await self._request("GET", "/users/me/recordings", params=params)

        return [
            Recording(
                meeting_id=m["id"],
                topic=m["topic"],
                start_time=m["start_time"],
                duration=m.get("duration", 0),
                files=[],  # Summary only
            )
            for m in data.get("meetings", [])
        ]

    async def get_recording(self, meeting_id: int) -> Recording:
        """Get recording details for a meeting."""
        data = await self._request("GET", f"/meetings/{meeting_id}/recordings")

        from .models import RecordingFile

        return Recording(
            meeting_id=data["id"],
            topic=data["topic"],
            start_time=data["start_time"],
            duration=data.get("duration", 0),
            share_url=data.get("share_url"),
            password=data.get("password"),
            files=[
                RecordingFile(
                    id=f["id"],
                    file_type=f["file_type"],
                    file_size=f.get("file_size", 0),
                    download_url=f.get("download_url"),
                    play_url=f.get("play_url"),
                    status=f.get("status"),
                )
                for f in data.get("recording_files", [])
            ],
        )

    # ============== POST-MEETING ==============

    async def get_participants(self, meeting_id: int) -> list[Participant]:
        """Get participants from a past meeting."""
        data = await self._request(
            "GET", f"/past_meetings/{meeting_id}/participants",
            params={"page_size": 300},
        )

        return [
            Participant(
                name=p.get("name"),
                email=p.get("user_email"),
                join_time=p.get("join_time"),
                leave_time=p.get("leave_time"),
                duration=p.get("duration"),
            )
            for p in data.get("participants", [])
        ]

    async def get_meeting_summary(self, meeting_id: int) -> MeetingSummary:
        """Get AI-generated meeting summary."""
        data = await self._request("GET", f"/meetings/{meeting_id}/meeting_summary")

        return MeetingSummary(
            meeting_id=meeting_id,
            summary=data.get("summary_overview") or data.get("summary"),
            next_steps=data.get("next_steps"),
            topics=[
                d.get("summary") for d in data.get("summary_details", [])
            ] or data.get("topics"),
        )

    # ============== TRANSCRIPT ==============

    _TRANSCRIPT_FILE_TYPES = ("TRANSCRIPT", "CC")

    @staticmethod
    def _parse_vtt(vtt: str) -> list[TranscriptEntry]:
        """Parse WEBVTT content into structured entries.

        Handles the common Zoom format where speaker is prefixed like
        "Landry Zetam: hello world" on the content line.
        """
        entries: list[TranscriptEntry] = []
        blocks = re.split(r"\n\s*\n", vtt.strip())
        for block in blocks:
            if block.upper().startswith("WEBVTT"):
                continue
            lines = [ln for ln in block.splitlines() if ln.strip()]
            if not lines:
                continue
            # Optional cue identifier on first line
            if "-->" not in lines[0] and len(lines) > 1:
                lines = lines[1:]
            if not lines or "-->" not in lines[0]:
                continue
            start, _, end = lines[0].partition("-->")
            content = " ".join(ln.strip() for ln in lines[1:]).strip()
            if not content:
                continue
            speaker: Optional[str] = None
            if ":" in content:
                maybe_speaker, _, rest = content.partition(":")
                # Simple heuristic: speaker is short, no sentence punctuation
                if len(maybe_speaker) < 60 and "." not in maybe_speaker and "?" not in maybe_speaker:
                    speaker = maybe_speaker.strip()
                    content = rest.strip()
            entries.append(TranscriptEntry(
                start=start.strip(),
                end=end.strip(),
                speaker=speaker,
                text=content,
            ))
        return entries

    async def _download_transcript_text(self, download_url: str) -> Optional[str]:
        """Fetch raw VTT/CC content using the account's own bearer token.

        Zoom's download URLs require the same OAuth token as the API. Returns
        None if the body does not look like VTT, so a login redirect page is
        never mistaken for a transcript.
        """
        token = await self._get_token()
        try:
            response = await self._client.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
            )
        except Exception:
            return None

        if response.status_code == 200 and "WEBVTT" in response.text[:200].upper():
            return response.text
        return None

    async def get_transcript(self, meeting_id: int) -> MeetingTranscript:
        """Fetch and parse the transcript (VTT) for a past meeting.

        Raises ZoomError when the meeting has no cloud recording at all.
        Returns a `note` when a recording exists but carries no transcript
        file — that means the call was recorded without audio transcription
        enabled, and no transcript exists to recover.
        """
        recording = await self.get_recording(meeting_id)

        transcript_file = next(
            (f for f in recording.files if f.file_type in self._TRANSCRIPT_FILE_TYPES),
            None,
        )
        if transcript_file is None:
            return MeetingTranscript(
                meeting_id=meeting_id,
                source="NONE",
                note="No TRANSCRIPT or CC file found for this meeting. The call "
                     "was recorded without audio transcription enabled, so no "
                     "transcript exists to recover.",
            )

        raw = None
        if transcript_file.download_url:
            raw = await self._download_transcript_text(transcript_file.download_url)

        if not raw:
            return MeetingTranscript(
                meeting_id=meeting_id,
                source=transcript_file.file_type,
                file_id=transcript_file.id,
                download_url=transcript_file.download_url,
                note="Transcript file exists but the download did not return VTT. "
                     "Check that the Server-to-Server OAuth app has the "
                     "cloud_recording:read:list_recording_files:admin scope.",
            )

        entries = self._parse_vtt(raw)
        plain_text = "\n".join(
            f"{e.speaker}: {e.text}" if e.speaker else e.text for e in entries
        )
        return MeetingTranscript(
            meeting_id=meeting_id,
            source=transcript_file.file_type,
            file_id=transcript_file.id,
            download_url=transcript_file.download_url,
            entries=entries,
            plain_text=plain_text,
        )
