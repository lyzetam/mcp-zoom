# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -e ".[aws]"

# Run MCP server
python server.py

# Run CLI
python cli.py list
python cli.py create --topic "Demo" --datetime "2026-02-15T10:00:00"

# Run tests
pytest
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        mcp-zoom                              │
├─────────────────────────────────────────────────────────────┤
│  src/zoom/           ← Core library (importable by zI)      │
│  ├── client.py       ← ZoomClient async class               │
│  └── models.py       ← Pydantic models                      │
│                                                              │
│  server.py           ← MCP server (thin wrapper)            │
│  cli.py              ← CLI (thin wrapper)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Composio     │  ← OAuth layer
                    │  (v2 Actions)   │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Zoom API     │
                    └─────────────────┘
```

**Key Design:** Core logic lives in `src/zoom/client.py`. Both `server.py` (MCP) and `cli.py` are thin wrappers that call `ZoomClient` methods. This allows the same code to be imported by zI or any other integration.

## Composio Integration

This server doesn't call Zoom API directly. Composio handles:
- OAuth token storage and refresh
- Rate limiting and retries
- Unified action execution API

All operations go through `ZOOM_*` Composio actions via their v2 execute endpoint.

## Credentials

**AWS Secret:** `composio/api-key`
```json
{
  "api_key": "ak_xxx",
  "zoom_connected_account_id": "xxx"
}
```

`ZoomClient.from_env()` auto-loads from AWS Secrets Manager, falls back to environment variables.

## Tools → Composio Actions Mapping

| MCP Tool | Composio Action |
|----------|-----------------|
| `list_meetings` | `ZOOM_LIST_MEETINGS` |
| `create_meeting` | `ZOOM_CREATE_A_MEETING` |
| `get_meeting` | `ZOOM_GET_A_MEETING` |
| `update_meeting` | `ZOOM_UPDATE_A_MEETING` |
| `add_registrant` | `ZOOM_ADD_A_MEETING_REGISTRANT` |
| `list_recordings` | `ZOOM_LIST_ALL_RECORDINGS` |
| `get_recording` | `ZOOM_GET_MEETING_RECORDINGS` |
| `get_participants` | `ZOOM_GET_PAST_MEETING_PARTICIPANTS` |
| `get_meeting_summary` | `ZOOM_GET_A_MEETING_SUMMARY` |

## Library Usage (for zI)

```python
from zoom import ZoomClient
from zoom.models import MeetingCreate

async with ZoomClient.from_env() as client:
    meetings = await client.list_meetings()
    meeting = await client.create_meeting(MeetingCreate(
        topic="Demo",
        start_time="2026-02-15T10:00:00",
        duration=45,
    ))
```

See `docs/ZI_INTEGRATION.md` for complete integration guide.
