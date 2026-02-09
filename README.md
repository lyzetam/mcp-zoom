# MCP Zoom Server

MCP (Model Context Protocol) server for Zoom Meetings via Composio OAuth integration.

## Features

- **Meeting Management**: Create, list, get, update meetings
- **Recordings**: List and access cloud recordings
- **Post-Meeting Data**: Participants, AI summaries
- **Registrants**: Add meeting registrants

## Prerequisites

1. **Composio Account** with Zoom OAuth connected
2. Get your Composio API key from [platform.composio.dev](https://platform.composio.dev)
3. Connect your Zoom account via Composio dashboard

## Installation

```bash
cd ~/dev/mcp-zoom
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Configuration

### Environment Variables

```bash
export COMPOSIO_API_KEY="ak_your_api_key"
export ZOOM_CONNECTED_ACCOUNT_ID="your_connected_account_id"
```

Or create `.env` file (see `.env.example`).

### Claude Code Configuration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "zoom": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/zz/dev/mcp-zoom", "python", "server.py"],
      "env": {
        "COMPOSIO_API_KEY": "${COMPOSIO_API_KEY}",
        "ZOOM_CONNECTED_ACCOUNT_ID": "${ZOOM_CONNECTED_ACCOUNT_ID}"
      }
    }
  }
}
```

Or fetch credentials from AWS Secrets Manager at runtime.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_meetings` | List upcoming/scheduled/live meetings |
| `create_meeting` | Create a new meeting |
| `get_meeting` | Get meeting details by ID |
| `update_meeting` | Update meeting settings |
| `add_registrant` | Add a meeting registrant |
| `list_recordings` | List cloud recordings in date range |
| `get_recording` | Get recording details and download URLs |
| `get_participants` | Get past meeting participants |
| `get_meeting_summary` | Get AI-generated meeting summary |
| `get_daily_usage` | Get daily usage report |

## Usage Examples

### List Meetings

```
List my upcoming Zoom meetings
```

### Create Meeting

```
Create a Zoom meeting with John on Friday at 2pm for 30 minutes about project review
```

### Get Recording

```
Get the recording from my last meeting with Delphine
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run server directly
python server.py
```

## Credentials Storage

Credentials stored in AWS Secrets Manager:

| Secret | Keys |
|--------|------|
| `composio/api-key` | `api_key`, `zoom_connected_account_id` |

## License

MIT
