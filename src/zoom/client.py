"""Zoom client via Composio API.

This is the core library that can be used by:
- MCP server (server.py)
- CLI (cli.py)
- zI or any other integration

Usage:
    from zoom import ZoomClient

    # With explicit credentials
    client = ZoomClient(
        composio_api_key="ak_xxx",
        connected_account_id="xxx"
    )

    # Or from environment/AWS Secrets Manager
    client = ZoomClient.from_env()

    # Use it
    meetings = await client.list_meetings()
"""

import json
import os
from typing import Optional

import httpx

import re

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


class ZoomClient:
    """Zoom client using Composio as the OAuth/API layer."""

    COMPOSIO_BASE_URL = "https://backend.composio.dev/api/v2/actions"

    def __init__(
        self,
        composio_api_key: str,
        connected_account_id: str,
        timeout: float = 30.0,
    ):
        self.composio_api_key = composio_api_key
        self.connected_account_id = connected_account_id
        self._client = httpx.AsyncClient(
            headers={
                "X-API-Key": composio_api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    @classmethod
    def from_env(cls) -> "ZoomClient":
        """Create client from environment variables or AWS Secrets Manager."""
        api_key = None
        account_id = None

        # Try AWS Secrets Manager first
        try:
            import boto3
            client = boto3.client("secretsmanager", region_name="us-east-1")
            secret = json.loads(
                client.get_secret_value(SecretId="composio/api-key")["SecretString"]
            )
            api_key = secret.get("api_key")
            account_id = secret.get("zoom_connected_account_id")
        except Exception:
            pass

        # Fallback to environment
        api_key = api_key or os.environ.get("COMPOSIO_API_KEY")
        account_id = account_id or os.environ.get("ZOOM_CONNECTED_ACCOUNT_ID")

        if not api_key or not account_id:
            raise ValueError(
                "Missing credentials. Set COMPOSIO_API_KEY and ZOOM_CONNECTED_ACCOUNT_ID "
                "or store in AWS Secrets Manager at composio/api-key"
            )

        return cls(composio_api_key=api_key, connected_account_id=account_id)

    async def _execute(self, action: str, params: dict) -> dict:
        """Execute a Composio action."""
        response = await self._client.post(
            f"{self.COMPOSIO_BASE_URL}/{action}/execute",
            json={
                "connectedAccountId": self.connected_account_id,
                "input": params,
            },
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("successful"):
            raise Exception(f"Zoom action failed: {data.get('error')}")

        return data["data"]

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
        data = await self._execute("ZOOM_LIST_MEETINGS", {
            "userId": "me",
            "type": meeting_type,
        })

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
        params = {
            "userId": "me",
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
            params["agenda"] = meeting.agenda

        data = await self._execute("ZOOM_CREATE_A_MEETING", params)

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
        data = await self._execute("ZOOM_GET_A_MEETING", {"meetingId": meeting_id})

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
        params = {"meetingId": meeting_id}
        if topic:
            params["topic"] = topic
        if start_time:
            params["start_time"] = start_time
        if duration:
            params["duration"] = duration
        if agenda:
            params["agenda"] = agenda

        await self._execute("ZOOM_UPDATE_A_MEETING", params)

    async def add_registrant(
        self,
        meeting_id: int,
        email: str,
        first_name: str,
        last_name: str = "",
    ) -> Registrant:
        """Add a meeting registrant."""
        data = await self._execute("ZOOM_ADD_A_MEETING_REGISTRANT", {
            "meetingId": str(meeting_id),
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        })

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
        params = {"userId": "me", "from": from_date}
        if to_date:
            params["to"] = to_date

        data = await self._execute("ZOOM_LIST_ALL_RECORDINGS", params)

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
        data = await self._execute("ZOOM_GET_MEETING_RECORDINGS", {
            "meetingId": str(meeting_id),
        })

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
        data = await self._execute("ZOOM_GET_PAST_MEETING_PARTICIPANTS", {
            "meetingId": str(meeting_id),
        })

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
        data = await self._execute("ZOOM_GET_A_MEETING_SUMMARY", {
            "meetingId": str(meeting_id),
        })

        return MeetingSummary(
            meeting_id=meeting_id,
            summary=data.get("summary"),
            next_steps=data.get("next_steps"),
            topics=data.get("topics"),
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
        """Fetch raw VTT/CC content. Tries anonymous, then Composio-proxied download.

        Returns None if both fail.
        """
        # Attempt 1: direct anonymous download (works when recording is public-shared)
        try:
            resp = await self._client.get(download_url, follow_redirects=True)
            if resp.status_code == 200 and "WEBVTT" in resp.text[:200].upper():
                return resp.text
        except Exception:
            pass

        # Attempt 2: Composio proxied download (if this action is available in the account)
        try:
            data = await self._execute("ZOOM_DOWNLOAD_RECORDING_FILE", {
                "downloadUrl": download_url,
            })
            content = data.get("content") or data.get("text") or data.get("body")
            if content and "WEBVTT" in content[:200].upper():
                return content
        except Exception:
            pass

        return None

    async def get_transcript(self, meeting_id: int) -> MeetingTranscript:
        """Fetch and parse the transcript (VTT) for a past meeting.

        Falls back from anonymous download → Composio proxy → metadata-only
        if the raw file is unreachable without additional auth.
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
                note="No TRANSCRIPT or CC file found for this meeting. "
                     "Ensure cloud recording with audio transcription was enabled.",
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
                note="Transcript file exists but could not be fetched without "
                     "additional auth. Download the URL manually or extend Composio "
                     "with a download-recording action.",
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
