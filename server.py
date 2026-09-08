#!/usr/bin/env python3
"""MCP Server for Zoom Meetings.

Uses the zoom.ZoomClient library for all operations.
"""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.zoom import ZoomClient
from src.zoom.models import MeetingCreate

# Initialize MCP server
mcp = FastMCP("zoom")

# Lazy-loaded client
_client: Optional[ZoomClient] = None


def get_client() -> ZoomClient:
    """Get or create the Zoom client."""
    global _client
    if _client is None:
        _client = ZoomClient.from_env()
    return _client


# ============== MEETING TOOLS ==============

@mcp.tool()
async def list_meetings(meeting_type: str = "upcoming") -> str:
    """List Zoom meetings.

    Args:
        meeting_type: Type of meetings - 'upcoming', 'scheduled', 'live', or 'pending'
    """
    client = get_client()
    meetings = await client.list_meetings(meeting_type)
    return json.dumps([m.model_dump(mode="json") for m in meetings], indent=2)


@mcp.tool()
async def create_meeting(
    topic: str,
    start_time: str,
    duration: int = 45,
    timezone: str = "America/New_York",
    agenda: Optional[str] = None,
    waiting_room: bool = True,
    auto_recording: str = "cloud"
) -> str:
    """Create a new Zoom meeting.

    Args:
        topic: Meeting title
        start_time: Start time in ISO format (e.g., '2026-02-11T10:00:00')
        duration: Duration in minutes (default: 45)
        timezone: IANA timezone (default: America/New_York)
        agenda: Optional meeting description
        waiting_room: Enable waiting room (default: True)
        auto_recording: 'cloud', 'local', or 'none' (default: cloud)
    """
    client = get_client()
    meeting = await client.create_meeting(MeetingCreate(
        topic=topic,
        start_time=start_time,
        duration=duration,
        timezone=timezone,
        agenda=agenda,
        waiting_room=waiting_room,
        auto_recording=auto_recording,
    ))
    return json.dumps(meeting.model_dump(mode="json"), indent=2)


@mcp.tool()
async def get_meeting(meeting_id: int) -> str:
    """Get details for a specific meeting.

    Args:
        meeting_id: The Zoom meeting ID
    """
    client = get_client()
    meeting = await client.get_meeting(meeting_id)
    return json.dumps(meeting.model_dump(mode="json"), indent=2)


@mcp.tool()
async def update_meeting(
    meeting_id: int,
    topic: Optional[str] = None,
    start_time: Optional[str] = None,
    duration: Optional[int] = None,
    agenda: Optional[str] = None
) -> str:
    """Update an existing meeting.

    Args:
        meeting_id: The Zoom meeting ID
        topic: New title (optional)
        start_time: New start time in ISO format (optional)
        duration: New duration in minutes (optional)
        agenda: New agenda (optional)
    """
    client = get_client()
    await client.update_meeting(meeting_id, topic, start_time, duration, agenda)
    return json.dumps({"status": "updated", "meeting_id": meeting_id})


@mcp.tool()
async def add_registrant(
    meeting_id: int,
    email: str,
    first_name: str,
    last_name: str = ""
) -> str:
    """Add a registrant to a meeting.

    Args:
        meeting_id: The Zoom meeting ID
        email: Registrant's email
        first_name: Registrant's first name
        last_name: Registrant's last name (optional)
    """
    client = get_client()
    registrant = await client.add_registrant(meeting_id, email, first_name, last_name)
    return json.dumps(registrant.model_dump(mode="json"), indent=2)


# ============== RECORDING TOOLS ==============

@mcp.tool()
async def list_recordings(from_date: str, to_date: Optional[str] = None) -> str:
    """List cloud recordings in a date range.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD, optional)
    """
    client = get_client()
    recordings = await client.list_recordings(from_date, to_date)
    return json.dumps([r.model_dump(mode="json") for r in recordings], indent=2)


@mcp.tool()
async def get_recording(meeting_id: int) -> str:
    """Get recording details for a meeting.

    Args:
        meeting_id: The Zoom meeting ID
    """
    client = get_client()
    recording = await client.get_recording(meeting_id)
    return json.dumps(recording.model_dump(mode="json"), indent=2)


# ============== POST-MEETING TOOLS ==============

@mcp.tool()
async def get_participants(meeting_id: int) -> str:
    """Get participants from a past meeting.

    Args:
        meeting_id: The Zoom meeting ID (must be a past meeting)
    """
    client = get_client()
    participants = await client.get_participants(meeting_id)
    return json.dumps([p.model_dump(mode="json") for p in participants], indent=2)


@mcp.tool()
async def get_meeting_summary(meeting_id: int) -> str:
    """Get AI-generated meeting summary.

    Args:
        meeting_id: The Zoom meeting ID
    """
    client = get_client()
    summary = await client.get_meeting_summary(meeting_id)
    return json.dumps(summary.model_dump(mode="json"), indent=2)


# ============== TRANSCRIPT TOOLS ==============

@mcp.tool()
async def get_transcript(meeting_id: int) -> str:
    """Get the full transcript (VTT/CC) for a past meeting, parsed into
    timestamped entries plus a single plain-text block.

    Requires cloud recording with audio transcription enabled for the meeting.
    If the file exists but cannot be downloaded anonymously or via Composio,
    returns metadata + a `note` explaining how to fetch it manually.

    Args:
        meeting_id: The Zoom meeting ID (must be a past meeting with a recording)
    """
    client = get_client()
    transcript = await client.get_transcript(meeting_id)
    return json.dumps(transcript.model_dump(mode="json"), indent=2)


@mcp.tool()
async def get_transcript_text(meeting_id: int) -> str:
    """Get only the plain-text body of a meeting transcript — no JSON wrapper,
    no timestamps. Useful for piping into an LLM for summarization.

    Args:
        meeting_id: The Zoom meeting ID (must be a past meeting with a recording)
    """
    client = get_client()
    transcript = await client.get_transcript(meeting_id)
    if not transcript.plain_text:
        return transcript.note or "No transcript content available."
    return transcript.plain_text


if __name__ == "__main__":
    mcp.run()
