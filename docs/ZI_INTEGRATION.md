# zI Integration Guide: mcp-zoom

## Overview

`mcp-zoom` provides a Zoom client library that can be imported directly into zI for meeting management, recordings, and post-meeting analytics.

**Repository:** https://github.com/lyzetam/mcp-zoom (private)

## Architecture

```
zI Agent
    │
    ▼
┌─────────────────────────────────────┐
│          from zoom import           │
│            ZoomClient               │
│                                     │
│  - Async client (httpx)             │
│  - Type-safe (Pydantic models)      │
│  - AWS Secrets Manager support      │
└─────────────────────────────────────┘
    │
    ▼
Composio API (OAuth layer)
    │
    ▼
Zoom API
```

## Installation

```bash
# Clone (private repo - requires auth)
git clone https://github.com/lyzetam/mcp-zoom.git

# Install as package
cd mcp-zoom
pip install -e ".[aws]"
```

Or add to requirements.txt / pyproject.toml:
```
mcp-zoom @ git+https://github.com/lyzetam/mcp-zoom.git
```

## Credentials

Credentials are fetched from AWS Secrets Manager automatically:

**Secret:** `composio/api-key`
```json
{
  "api_key": "ak_xxx",
  "zoom_connected_account_id": "xxx"
}
```

Fallback to environment variables:
- `COMPOSIO_API_KEY`
- `ZOOM_CONNECTED_ACCOUNT_ID`

## Usage in zI

### Basic Import

```python
from zoom import ZoomClient
from zoom.models import MeetingCreate, Meeting

# Client auto-loads credentials from AWS Secrets Manager
client = ZoomClient.from_env()
```

### Available Methods

```python
# ============== MEETINGS ==============

# List meetings
meetings: list[Meeting] = await client.list_meetings(meeting_type="upcoming")
# meeting_type: "upcoming" | "scheduled" | "live" | "pending"

# Create meeting
meeting = await client.create_meeting(MeetingCreate(
    topic="Client Demo",
    start_time="2026-02-15T10:00:00",  # ISO format
    duration=45,                        # minutes
    timezone="America/New_York",        # IANA timezone
    agenda="Discuss Q1 roadmap",        # optional
    waiting_room=True,                  # optional, default True
    auto_recording="cloud",             # "cloud" | "local" | "none"
))
print(meeting.join_url)
print(meeting.password)

# Get meeting details
meeting = await client.get_meeting(meeting_id=83331079684)

# Update meeting
await client.update_meeting(
    meeting_id=83331079684,
    topic="Updated Title",      # optional
    start_time="2026-02-16T14:00:00",  # optional
    duration=60,                # optional
    agenda="New agenda",        # optional
)

# Add registrant
registrant = await client.add_registrant(
    meeting_id=83331079684,
    email="john@example.com",
    first_name="John",
    last_name="Doe",
)


# ============== RECORDINGS ==============

# List recordings in date range
recordings = await client.list_recordings(
    from_date="2026-01-01",
    to_date="2026-02-09",  # optional
)

# Get recording with download URLs
recording = await client.get_recording(meeting_id=83331079684)
for file in recording.files:
    print(f"{file.file_type}: {file.download_url}")


# ============== POST-MEETING ==============

# Get participants
participants = await client.get_participants(meeting_id=83331079684)
for p in participants:
    print(f"{p.name} ({p.email}) - {p.duration} seconds")

# Get AI summary (requires Zoom AI Companion)
summary = await client.get_meeting_summary(meeting_id=83331079684)
print(summary.summary)
print(summary.next_steps)
```

### Context Manager Pattern

```python
async with ZoomClient.from_env() as client:
    meetings = await client.list_meetings()
    # client.close() called automatically
```

### Explicit Credentials

```python
client = ZoomClient(
    composio_api_key="ak_xxx",
    connected_account_id="xxx",
)
```

## Pydantic Models

All responses are typed with Pydantic models:

```python
from zoom.models import (
    Meeting,          # Full meeting details
    MeetingCreate,    # Input for creating meetings
    Recording,        # Recording with files
    RecordingFile,    # Individual recording file
    Participant,      # Meeting participant
    Registrant,       # Meeting registrant
    MeetingSummary,   # AI-generated summary
)
```

### Meeting Model

```python
class Meeting(BaseModel):
    id: int
    topic: str
    start_time: datetime
    duration: int
    timezone: str
    join_url: Optional[str]
    start_url: Optional[str]
    password: Optional[str]
    agenda: Optional[str]
    status: Optional[str]
    host_email: Optional[str]
```

## Error Handling

```python
try:
    meeting = await client.get_meeting(invalid_id)
except Exception as e:
    # Composio/Zoom API errors raised as exceptions
    print(f"Error: {e}")
```

## Example: zI Meeting Scheduling Agent

```python
from zoom import ZoomClient
from zoom.models import MeetingCreate

class MeetingSchedulerTool:
    """Tool for zI to schedule Zoom meetings."""

    def __init__(self):
        self.client = ZoomClient.from_env()

    async def schedule_meeting(
        self,
        title: str,
        datetime_iso: str,
        duration_minutes: int = 45,
        attendee_email: str = None,
    ) -> dict:
        """Schedule a Zoom meeting and optionally add registrant."""

        meeting = await self.client.create_meeting(MeetingCreate(
            topic=title,
            start_time=datetime_iso,
            duration=duration_minutes,
        ))

        result = {
            "meeting_id": meeting.id,
            "join_url": meeting.join_url,
            "password": meeting.password,
            "start_time": meeting.start_time.isoformat(),
        }

        if attendee_email:
            registrant = await self.client.add_registrant(
                meeting_id=meeting.id,
                email=attendee_email,
                first_name=attendee_email.split("@")[0],
            )
            result["registrant_url"] = registrant.join_url

        return result

    async def get_upcoming_meetings(self) -> list[dict]:
        """Get all upcoming meetings."""
        meetings = await self.client.list_meetings("upcoming")
        return [
            {
                "id": m.id,
                "topic": m.topic,
                "start_time": m.start_time.isoformat(),
                "join_url": m.join_url,
            }
            for m in meetings
        ]
```

## Dependencies

Core:
- `httpx>=0.24.0` - Async HTTP client
- `pydantic>=2.0.0` - Data validation

Optional:
- `boto3>=1.26.0` - AWS Secrets Manager (install with `.[aws]`)

## Files

```
mcp-zoom/
├── src/zoom/
│   ├── __init__.py     # Exports: ZoomClient, Meeting, Recording, Participant
│   ├── client.py       # ZoomClient class
│   └── models.py       # Pydantic models
├── server.py           # MCP server (not needed for zI)
├── cli.py              # CLI (not needed for zI)
└── pyproject.toml
```

## Support

For issues with:
- **OAuth/Auth**: Check Composio dashboard at platform.composio.dev
- **API errors**: Check Zoom API status and rate limits
- **Credentials**: Verify AWS Secrets Manager secret `composio/api-key`
