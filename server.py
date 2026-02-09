#!/usr/bin/env python3
"""MCP Server for Zoom Meetings via Composio.

Provides tools for:
- Meeting management (create, list, get, update, delete)
- Recording access (list, get recordings)
- Post-meeting data (participants, AI summaries)
- Registrant management

Note: Uses Composio as the OAuth/API layer for Zoom.
"""

import os
import json
from typing import Optional
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("zoom")

# Configuration from environment
COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
ZOOM_CONNECTED_ACCOUNT_ID = os.environ.get("ZOOM_CONNECTED_ACCOUNT_ID")
COMPOSIO_BASE_URL = "https://backend.composio.dev/api/v2/actions"

# Default settings
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_DURATION = 45

# HTTP client for Composio API
client = httpx.AsyncClient(
    headers={
        "X-API-Key": COMPOSIO_API_KEY or "",
        "Content-Type": "application/json",
    },
    timeout=30.0
)


async def execute_composio_action(action: str, params: dict) -> dict:
    """Execute a Composio action for Zoom."""
    if not COMPOSIO_API_KEY or not ZOOM_CONNECTED_ACCOUNT_ID:
        raise ValueError("Missing COMPOSIO_API_KEY or ZOOM_CONNECTED_ACCOUNT_ID")

    response = await client.post(
        f"{COMPOSIO_BASE_URL}/{action}/execute",
        json={
            "connectedAccountId": ZOOM_CONNECTED_ACCOUNT_ID,
            "input": params,
        }
    )
    response.raise_for_status()

    data = response.json()
    if not data.get("successful"):
        raise Exception(f"Zoom action failed: {data.get('error')}")

    return data["data"]


# ============== MEETING MANAGEMENT ==============

@mcp.tool()
async def list_meetings(meeting_type: str = "upcoming") -> str:
    """List Zoom meetings.

    Args:
        meeting_type: Type of meetings to list - 'upcoming', 'scheduled', 'live', or 'pending'
    """
    data = await execute_composio_action("ZOOM_LIST_MEETINGS", {
        "userId": "me",
        "type": meeting_type,
    })

    meetings = data.get("meetings", [])
    if not meetings:
        return "No meetings found."

    result = []
    for m in meetings:
        result.append({
            "id": m.get("id"),
            "topic": m.get("topic"),
            "start_time": m.get("start_time"),
            "duration": m.get("duration"),
            "join_url": m.get("join_url"),
            "timezone": m.get("timezone"),
        })

    return json.dumps(result, indent=2)


@mcp.tool()
async def create_meeting(
    topic: str,
    start_time: str,
    duration: int = DEFAULT_DURATION,
    timezone: str = DEFAULT_TIMEZONE,
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
        agenda: Optional meeting description/agenda
        waiting_room: Enable waiting room (default: True)
        auto_recording: Recording mode - 'cloud', 'local', or 'none' (default: cloud)
    """
    params = {
        "userId": "me",
        "topic": topic,
        "type": 2,  # Scheduled meeting
        "start_time": start_time,
        "duration": duration,
        "timezone": timezone,
        "settings": {
            "host_video": True,
            "participant_video": True,
            "waiting_room": waiting_room,
            "auto_recording": auto_recording,
            "mute_upon_entry": True,
        },
    }
    if agenda:
        params["agenda"] = agenda

    data = await execute_composio_action("ZOOM_CREATE_A_MEETING", params)

    return json.dumps({
        "id": data.get("id"),
        "topic": data.get("topic"),
        "start_time": data.get("start_time"),
        "duration": data.get("duration"),
        "timezone": data.get("timezone"),
        "password": data.get("password"),
        "join_url": data.get("join_url"),
        "start_url": data.get("start_url"),
        "host_email": data.get("host_email"),
    }, indent=2)


@mcp.tool()
async def get_meeting(meeting_id: int) -> str:
    """Get details for a specific meeting.

    Args:
        meeting_id: The Zoom meeting ID
    """
    data = await execute_composio_action("ZOOM_GET_A_MEETING", {
        "meetingId": meeting_id,
    })

    return json.dumps({
        "id": data.get("id"),
        "topic": data.get("topic"),
        "start_time": data.get("start_time"),
        "duration": data.get("duration"),
        "timezone": data.get("timezone"),
        "agenda": data.get("agenda"),
        "password": data.get("password"),
        "join_url": data.get("join_url"),
        "start_url": data.get("start_url"),
        "status": data.get("status"),
        "settings": data.get("settings"),
    }, indent=2)


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
        meeting_id: The Zoom meeting ID to update
        topic: New meeting title (optional)
        start_time: New start time in ISO format (optional)
        duration: New duration in minutes (optional)
        agenda: New agenda/description (optional)
    """
    params = {"meetingId": meeting_id}
    if topic:
        params["topic"] = topic
    if start_time:
        params["start_time"] = start_time
    if duration:
        params["duration"] = duration
    if agenda:
        params["agenda"] = agenda

    await execute_composio_action("ZOOM_UPDATE_A_MEETING", params)
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
        email: Registrant's email address
        first_name: Registrant's first name
        last_name: Registrant's last name (optional)
    """
    data = await execute_composio_action("ZOOM_ADD_A_MEETING_REGISTRANT", {
        "meetingId": meeting_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
    })

    return json.dumps({
        "registrant_id": data.get("registrant_id"),
        "email": email,
        "join_url": data.get("join_url"),
    }, indent=2)


# ============== RECORDINGS ==============

@mcp.tool()
async def list_recordings(from_date: str, to_date: Optional[str] = None) -> str:
    """List cloud recordings in a date range.

    Args:
        from_date: Start date (YYYY-MM-DD format)
        to_date: End date (YYYY-MM-DD format, optional)
    """
    params = {
        "userId": "me",
        "from": from_date,
    }
    if to_date:
        params["to"] = to_date

    data = await execute_composio_action("ZOOM_LIST_ALL_RECORDINGS", params)

    meetings = data.get("meetings", [])
    result = []
    for m in meetings:
        files = m.get("recording_files", [])
        result.append({
            "meeting_id": m.get("id"),
            "topic": m.get("topic"),
            "start_time": m.get("start_time"),
            "duration": m.get("duration"),
            "recording_count": len(files),
            "total_size": sum(f.get("file_size", 0) for f in files),
        })

    return json.dumps(result, indent=2)


@mcp.tool()
async def get_recording(meeting_id: int) -> str:
    """Get recording details for a specific meeting.

    Args:
        meeting_id: The Zoom meeting ID
    """
    data = await execute_composio_action("ZOOM_GET_MEETING_RECORDINGS", {
        "meetingId": meeting_id,
    })

    files = data.get("recording_files", [])
    return json.dumps({
        "meeting_id": data.get("id"),
        "topic": data.get("topic"),
        "start_time": data.get("start_time"),
        "duration": data.get("duration"),
        "share_url": data.get("share_url"),
        "password": data.get("password"),
        "files": [
            {
                "id": f.get("id"),
                "file_type": f.get("file_type"),
                "file_size": f.get("file_size"),
                "download_url": f.get("download_url"),
                "play_url": f.get("play_url"),
                "status": f.get("status"),
            }
            for f in files
        ],
    }, indent=2)


# ============== POST-MEETING DATA ==============

@mcp.tool()
async def get_participants(meeting_id: int) -> str:
    """Get participants from a past meeting.

    Args:
        meeting_id: The Zoom meeting ID (must be a past meeting)
    """
    data = await execute_composio_action("ZOOM_GET_PAST_MEETING_PARTICIPANTS", {
        "meetingId": meeting_id,
    })

    participants = data.get("participants", [])
    return json.dumps([
        {
            "name": p.get("name"),
            "email": p.get("user_email"),
            "join_time": p.get("join_time"),
            "leave_time": p.get("leave_time"),
            "duration": p.get("duration"),
        }
        for p in participants
    ], indent=2)


@mcp.tool()
async def get_meeting_summary(meeting_id: int) -> str:
    """Get AI-generated meeting summary.

    Args:
        meeting_id: The Zoom meeting ID (must have AI Companion enabled)
    """
    data = await execute_composio_action("ZOOM_GET_A_MEETING_SUMMARY", {
        "meetingId": meeting_id,
    })

    return json.dumps({
        "meeting_id": data.get("meeting_id"),
        "summary": data.get("summary"),
        "next_steps": data.get("next_steps"),
        "topics": data.get("topics"),
    }, indent=2)


# ============== USAGE REPORTS ==============

@mcp.tool()
async def get_daily_usage(date: str) -> str:
    """Get daily usage report.

    Args:
        date: Date for the report (YYYY-MM-DD format)
    """
    data = await execute_composio_action("ZOOM_GET_DAILY_USAGE_REPORT", {
        "year": int(date[:4]),
        "month": int(date[5:7]),
        "day": int(date[8:10]),
    })

    return json.dumps(data, indent=2)


if __name__ == "__main__":
    mcp.run()
