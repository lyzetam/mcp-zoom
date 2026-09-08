"""Zoom client library via Composio.

Usage:
    from zoom import ZoomClient

    client = ZoomClient()
    meetings = await client.list_meetings()
    meeting = await client.create_meeting("Demo", "2026-02-11T10:00:00")
"""

from .client import ZoomClient
from .models import (
    Meeting,
    MeetingSummary,
    MeetingTranscript,
    Participant,
    Recording,
    TranscriptEntry,
)

__all__ = [
    "ZoomClient",
    "Meeting",
    "MeetingSummary",
    "MeetingTranscript",
    "Participant",
    "Recording",
    "TranscriptEntry",
]
