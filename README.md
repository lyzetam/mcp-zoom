# mcp-zoom

Zoom client library with MCP server and CLI interfaces. Uses Composio as the OAuth/API layer.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        mcp-zoom                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   src/zoom/           ← Core library (importable)           │
│   ├── client.py       ← ZoomClient class                    │
│   └── models.py       ← Pydantic models                     │
│                                                              │
│   server.py           ← MCP interface (Claude Code)         │
│   cli.py              ← CLI interface (terminal)            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Composio     │  ← OAuth management
                    │   (API layer)   │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Zoom API     │
                    └─────────────────┘
```

## Installation

```bash
cd ~/dev/mcp-zoom
uv venv && source .venv/bin/activate
uv pip install -e ".[aws]"  # Include boto3 for AWS Secrets Manager
```

## Configuration

Set credentials via environment or AWS Secrets Manager:

```bash
# Environment variables
export COMPOSIO_API_KEY="ak_xxx"
export ZOOM_CONNECTED_ACCOUNT_ID="xxx"

# Or store in AWS Secrets Manager at 'composio/api-key'
# with keys: api_key, zoom_connected_account_id
```

## Usage

### As a Library (for zI or other integrations)

```python
from zoom import ZoomClient
from zoom.models import MeetingCreate

# Create client
client = ZoomClient.from_env()  # From env/AWS
# or
client = ZoomClient(composio_api_key="...", connected_account_id="...")

# List meetings
meetings = await client.list_meetings()

# Create meeting
meeting = await client.create_meeting(MeetingCreate(
    topic="Demo Call",
    start_time="2026-02-15T10:00:00",
    duration=45,
))
print(meeting.join_url)

# Get recording
recording = await client.get_recording(meeting_id)
```

### As CLI

```bash
# List meetings
zoom list

# Create meeting
zoom create --topic "Demo" --datetime "2026-02-15T10:00:00" --duration 30

# Get meeting details
zoom get 83331079684

# List recordings
zoom recordings --from 2026-01-01 --to 2026-02-09

# Get participants
zoom participants 83331079684
```

### As MCP Server (Claude Code)

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "zoom": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/zz/dev/mcp-zoom", "python", "server.py"],
      "env": {
        "COMPOSIO_API_KEY": "...",
        "ZOOM_CONNECTED_ACCOUNT_ID": "..."
      }
    }
  }
}
```

Then use in Claude Code:
```
List my upcoming Zoom meetings
Create a meeting with John on Friday at 2pm
```

## Available Operations

| Operation | Client Method | CLI Command | MCP Tool |
|-----------|--------------|-------------|----------|
| List meetings | `list_meetings()` | `zoom list` | `list_meetings` |
| Create meeting | `create_meeting()` | `zoom create` | `create_meeting` |
| Get meeting | `get_meeting()` | `zoom get ID` | `get_meeting` |
| Update meeting | `update_meeting()` | `zoom update ID` | `update_meeting` |
| Add registrant | `add_registrant()` | - | `add_registrant` |
| List recordings | `list_recordings()` | `zoom recordings` | `list_recordings` |
| Get recording | `get_recording()` | `zoom recording ID` | `get_recording` |
| Get participants | `get_participants()` | `zoom participants ID` | `get_participants` |
| Get summary | `get_meeting_summary()` | `zoom summary ID` | `get_meeting_summary` |

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run MCP server directly
python server.py

# Run CLI directly
python cli.py list
```

## License

MIT
