# CLAUDE.md

MCP Server for Zoom Meetings via Composio OAuth integration.

## Quick Start

```bash
# Install
cd ~/dev/mcp-zoom
uv venv && source .venv/bin/activate
uv pip install -e .

# Run
COMPOSIO_API_KEY=ak_xxx ZOOM_CONNECTED_ACCOUNT_ID=xxx python server.py
```

## Architecture

```
Zoom API <--OAuth--> Composio <--API--> mcp-zoom <--MCP--> Claude
```

This server doesn't call Zoom directly. It uses Composio as the OAuth/API abstraction layer:
- Composio handles OAuth token refresh
- Composio provides unified action API
- We just call `ZOOM_*` actions via Composio's execute endpoint

## Tools

| Tool | Composio Action |
|------|-----------------|
| `list_meetings` | `ZOOM_LIST_MEETINGS` |
| `create_meeting` | `ZOOM_CREATE_A_MEETING` |
| `get_meeting` | `ZOOM_GET_A_MEETING` |
| `update_meeting` | `ZOOM_UPDATE_A_MEETING` |
| `add_registrant` | `ZOOM_ADD_A_MEETING_REGISTRANT` |
| `list_recordings` | `ZOOM_LIST_ALL_RECORDINGS` |
| `get_recording` | `ZOOM_GET_MEETING_RECORDINGS` |
| `get_participants` | `ZOOM_GET_PAST_MEETING_PARTICIPANTS` |
| `get_meeting_summary` | `ZOOM_GET_A_MEETING_SUMMARY` |
| `get_daily_usage` | `ZOOM_GET_DAILY_USAGE_REPORT` |

## Credentials

From AWS Secrets Manager (`composio/api-key`):
- `api_key`: Composio API key
- `zoom_connected_account_id`: OAuth connected account ID

## Testing

```bash
# List meetings
curl -s localhost:3000/tools/list_meetings

# Create meeting
curl -s localhost:3000/tools/create_meeting \
  -d '{"topic": "Test", "start_time": "2026-02-15T10:00:00"}'
```
