"""Tests for the direct Zoom API client (Server-to-Server OAuth).

These pin the transport: the client must talk to api.zoom.us directly and
must never reach for Composio, whose v2 action API was retired (410 Gone).
"""

import base64
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.zoom.client import ZoomClient  # noqa: E402
from src.zoom.models import MeetingCreate  # noqa: E402

TOKEN_URL = "https://zoom.us/oauth/token"
API = "https://api.zoom.us/v2"

VTT = """WEBVTT

1
00:00:00.000 --> 00:00:04.000
Landry Zetam: so where did we land on the pricing

2
00:00:04.000 --> 00:00:09.000
Yolanda Hayes: I want to start in September.
"""


def build_client(handler):
    """ZoomClient wired to a mock transport."""
    client = ZoomClient(
        account_id="acct-1",
        client_id="cid",
        client_secret="csecret",
    )
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def token_response(request):
    return httpx.Response(200, json={"access_token": "tok-abc", "expires_in": 3600})


# ---------------------------------------------------------------- auth


@pytest.mark.asyncio
async def test_token_uses_account_credentials_grant_with_basic_auth():
    seen = {}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            return token_response(request)
        return httpx.Response(200, json={"meetings": []})

    client = build_client(handler)
    token = await client._get_token()

    assert token == "tok-abc"
    assert "grant_type=account_credentials" in seen["url"]
    assert "account_id=acct-1" in seen["url"]
    expected = base64.b64encode(b"cid:csecret").decode()
    assert seen["auth"] == f"Basic {expected}"


@pytest.mark.asyncio
async def test_token_is_cached_across_calls():
    calls = {"n": 0}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            calls["n"] += 1
            return token_response(request)
        return httpx.Response(200, json={"meetings": []})

    client = build_client(handler)
    await client.list_meetings()
    await client.list_meetings()

    assert calls["n"] == 1, "token should be fetched once and reused"


@pytest.mark.asyncio
async def test_api_calls_send_bearer_token():
    seen = {}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return token_response(request)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"meetings": []})

    client = build_client(handler)
    await client.list_meetings()

    assert seen["auth"] == "Bearer tok-abc"


# ---------------------------------------------------------------- routing


@pytest.mark.asyncio
async def test_list_recordings_hits_zoom_recordings_endpoint():
    seen = {}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return token_response(request)
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"meetings": []})

    client = build_client(handler)
    await client.list_recordings(from_date="2026-08-01", to_date="2026-08-31")

    assert seen["url"].startswith(f"{API}/users/me/recordings")
    assert "from=2026-08-01" in seen["url"]
    assert "to=2026-08-31" in seen["url"]


@pytest.mark.asyncio
async def test_get_recording_hits_meeting_recordings_endpoint():
    seen = {}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return token_response(request)
        seen["url"] = str(request.url)
        return httpx.Response(200, json={
            "id": 81112228045,
            "topic": "Landry <> Yolanda",
            "start_time": "2026-08-21T14:00:00Z",
            "duration": 70,
            "recording_files": [],
        })

    client = build_client(handler)
    await client.get_recording(81112228045)

    assert seen["url"] == f"{API}/meetings/81112228045/recordings"


@pytest.mark.asyncio
async def test_create_meeting_posts_to_users_me_meetings():
    seen = {}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return token_response(request)
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(201, json={
            "id": 999,
            "topic": "Demo",
            "start_time": "2026-09-10T15:00:00Z",
            "duration": 45,
            "join_url": "https://zoom.us/j/999",
        })

    client = build_client(handler)
    await client.create_meeting(MeetingCreate(
        topic="Demo", start_time="2026-09-10T15:00:00Z",
    ))

    assert seen["method"] == "POST"
    assert seen["url"] == f"{API}/users/me/meetings"


@pytest.mark.asyncio
async def test_get_participants_hits_past_meetings_endpoint():
    seen = {}

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return token_response(request)
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"participants": []})

    client = build_client(handler)
    await client.get_participants(81112228045)

    assert seen["url"].startswith(f"{API}/past_meetings/81112228045/participants")


# ---------------------------------------------------------------- transcript


@pytest.mark.asyncio
async def test_get_transcript_downloads_vtt_with_bearer_and_parses_it():
    """The whole point: with a real Zoom token the VTT is fetchable."""
    def handler(request):
        url = str(request.url)
        if url.startswith(TOKEN_URL):
            return token_response(request)
        if url.endswith("/recordings"):
            return httpx.Response(200, json={
                "id": 81112228045,
                "topic": "Landry <> Yolanda",
                "start_time": "2026-08-21T14:00:00Z",
                "duration": 70,
                "recording_files": [{
                    "id": "file-1",
                    "file_type": "TRANSCRIPT",
                    "file_size": 1024,
                    "download_url": "https://zoom.us/rec/download/file-1",
                }],
            })
        if "rec/download" in url:
            assert request.headers.get("authorization") == "Bearer tok-abc", \
                "transcript download must be authenticated"
            return httpx.Response(200, text=VTT)
        return httpx.Response(404)

    client = build_client(handler)
    transcript = await client.get_transcript(81112228045)

    assert transcript.source == "TRANSCRIPT"
    assert transcript.note is None
    assert len(transcript.entries) == 2
    assert transcript.entries[0].speaker == "Landry Zetam"
    assert "pricing" in transcript.entries[0].text
    assert transcript.entries[1].speaker == "Yolanda Hayes"
    assert "Yolanda Hayes: I want to start in September." in transcript.plain_text


@pytest.mark.asyncio
async def test_get_transcript_reports_when_no_transcript_file_exists():
    """A call recorded without transcription must say so, not fabricate."""
    def handler(request):
        url = str(request.url)
        if url.startswith(TOKEN_URL):
            return token_response(request)
        return httpx.Response(200, json={
            "id": 5,
            "topic": "No transcript",
            "start_time": "2026-08-21T14:00:00Z",
            "duration": 10,
            "recording_files": [{
                "id": "f",
                "file_type": "MP4",
                "file_size": 10,
                "download_url": "https://zoom.us/rec/download/f",
            }],
        })

    client = build_client(handler)
    transcript = await client.get_transcript(5)

    assert transcript.source == "NONE"
    assert transcript.entries == []
    assert "transcription" in (transcript.note or "").lower()


@pytest.mark.asyncio
async def test_missing_recording_raises_a_clear_error():
    """A meeting with no cloud recording must fail loudly, not return empty."""
    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return token_response(request)
        return httpx.Response(404, json={
            "code": 3301, "message": "There is no recording for this meeting.",
        })

    client = build_client(handler)
    with pytest.raises(Exception) as exc:
        await client.get_transcript(12345)

    assert "no recording" in str(exc.value).lower()


# ---------------------------------------------------------------- regression


def test_client_never_calls_composio():
    """Composio's v2 action API is retired (410). Nothing may call it.

    Checks for *use*, not mention — the docstring explains the migration on
    purpose, so banning the word would forbid the explanation.
    """
    source = (Path(__file__).resolve().parents[1] / "src/zoom/client.py").read_text()
    assert "backend.composio.dev" not in source
    assert "connectedAccountId" not in source
    assert "COMPOSIO_API_KEY" not in source
    assert "_execute(" not in source


def test_client_targets_the_real_zoom_hosts():
    """Positive control: the ban above passes trivially if the file is empty."""
    source = (Path(__file__).resolve().parents[1] / "src/zoom/client.py").read_text()
    assert "https://api.zoom.us/v2" in source
    assert "https://zoom.us/oauth/token" in source
