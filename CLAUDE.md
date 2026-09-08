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
                    │  S2S OAuth      │  ← account credentials
                    │  (v2 Actions)   │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Zoom API     │
                    └─────────────────┘
```

**Key Design:** Core logic lives in `src/zoom/client.py`. Both `server.py` (MCP) and `cli.py` are thin wrappers that call `ZoomClient` methods. This allows the same code to be imported by zI or any other integration.

## Auth: Server-to-Server OAuth

This server calls the Zoom REST API directly. Auth handles:
- OAuth token storage and refresh
- Rate limiting and retries
- Unified action execution API

All operations are plain REST calls to `https://api.zoom.us/v2`.

> **History:** this server used Composio as its API layer until 2026-09-08,
> when Composio retired `/api/v2/actions/{ACTION}/execute` (410 Gone) and every
> tool broke at once. Do not reintroduce that dependency.

## Credentials

**AWS Secret:** `zoom/s2s` — `{account_id, client_id, client_secret}`
```json
{
  "api_key": "ak_xxx",
  "zoom_connected_account_id": "xxx"
}
```

`ZoomClient.from_env()` auto-loads from AWS Secrets Manager, falls back to environment variables.

## Tools → Zoom Endpoints

| MCP Tool | Zoom Endpoint |
|----------|-----------------|
| `list_meetings` | `GET /users/me/meetings` |
| `create_meeting` | `POST /users/me/meetings` |
| `get_meeting` | `GET /meetings/{id}` |
| `update_meeting` | `PATCH /meetings/{id}` |
| `add_registrant` | `POST /meetings/{id}/registrants` |
| `list_recordings` | `GET /users/me/recordings` |
| `get_recording` | `GET /meetings/{id}/recordings` |
| `get_participants` | `GET /past_meetings/{id}/participants` |
| `get_meeting_summary` | `GET /meetings/{id}/meeting_summary` |

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
