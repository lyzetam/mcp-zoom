#!/usr/bin/env python3
"""CLI for Zoom operations.

Usage:
    zoom list [--type TYPE]
    zoom create --topic TOPIC --datetime DATETIME [--duration MIN] [--agenda TEXT]
    zoom get MEETING_ID
    zoom update MEETING_ID [--topic TOPIC] [--datetime DATETIME]
    zoom recordings --from DATE [--to DATE]
    zoom recording MEETING_ID
    zoom participants MEETING_ID
    zoom summary MEETING_ID
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

from src.zoom import ZoomClient
from src.zoom.models import MeetingCreate


def format_meeting(m) -> str:
    """Format meeting for display."""
    dt = m.start_time
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    formatted = dt.strftime("%a, %b %d %Y at %I:%M %p")

    lines = [
        f"  Topic:      {m.topic}",
        f"  Date/Time:  {formatted} {m.timezone}",
        f"  Duration:   {m.duration} min",
        f"  Meeting ID: {m.id}",
    ]
    if m.password:
        lines.append(f"  Password:   {m.password}")
    if m.join_url:
        lines.append(f"  Join URL:   {m.join_url}")

    return "\n".join(lines)


async def cmd_list(args):
    """List meetings."""
    async with ZoomClient.from_env() as client:
        meetings = await client.list_meetings(args.type)

    if not meetings:
        print("No meetings found.")
        return

    for m in meetings:
        print(format_meeting(m))
        print()


async def cmd_create(args):
    """Create a meeting."""
    async with ZoomClient.from_env() as client:
        meeting = await client.create_meeting(MeetingCreate(
            topic=args.topic,
            start_time=args.datetime,
            duration=args.duration,
            timezone=args.timezone,
            agenda=args.agenda,
        ))

    print("Meeting created:\n")
    print(format_meeting(meeting))


async def cmd_get(args):
    """Get meeting details."""
    async with ZoomClient.from_env() as client:
        meeting = await client.get_meeting(args.meeting_id)

    print(format_meeting(meeting))


async def cmd_update(args):
    """Update a meeting."""
    async with ZoomClient.from_env() as client:
        await client.update_meeting(
            args.meeting_id,
            topic=args.topic,
            start_time=args.datetime,
            duration=args.duration,
            agenda=args.agenda,
        )

    print(f"Meeting {args.meeting_id} updated.")


async def cmd_recordings(args):
    """List recordings."""
    async with ZoomClient.from_env() as client:
        recordings = await client.list_recordings(args.from_date, args.to_date)

    if not recordings:
        print("No recordings found.")
        return

    for r in recordings:
        dt = r.start_time
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        print(f"  {r.topic}")
        print(f"    Date: {dt.strftime('%b %d, %Y')}, Duration: {r.duration} min")
        print(f"    Meeting ID: {r.meeting_id}")
        print()


async def cmd_recording(args):
    """Get recording details."""
    async with ZoomClient.from_env() as client:
        recording = await client.get_recording(args.meeting_id)

    print(f"Recording: {recording.topic}")
    print(f"  Share URL: {recording.share_url}")
    if recording.password:
        print(f"  Password:  {recording.password}")
    print(f"  Files:")
    for f in recording.files:
        print(f"    - {f.file_type}: {f.file_size // 1024 // 1024}MB")
        if f.download_url:
            print(f"      Download: {f.download_url}")


async def cmd_participants(args):
    """Get meeting participants."""
    async with ZoomClient.from_env() as client:
        participants = await client.get_participants(args.meeting_id)

    if not participants:
        print("No participants found.")
        return

    print("Participants:")
    for p in participants:
        duration = f"{p.duration // 60}m" if p.duration else "?"
        print(f"  - {p.name or 'Unknown'} ({p.email or 'no email'}) - {duration}")


async def cmd_summary(args):
    """Get meeting summary."""
    async with ZoomClient.from_env() as client:
        summary = await client.get_meeting_summary(args.meeting_id)

    if summary.summary:
        print("Summary:")
        print(f"  {summary.summary}")
    if summary.next_steps:
        print("\nNext Steps:")
        for step in summary.next_steps:
            print(f"  - {step}")
    if summary.topics:
        print("\nTopics:")
        for topic in summary.topics:
            print(f"  - {topic}")


def main():
    parser = argparse.ArgumentParser(description="Zoom CLI")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = subparsers.add_parser("list", help="List meetings")
    list_p.add_argument("--type", "-t", default="upcoming",
                        choices=["upcoming", "scheduled", "live", "pending"])

    # create
    create_p = subparsers.add_parser("create", help="Create meeting")
    create_p.add_argument("--topic", "-t", required=True)
    create_p.add_argument("--datetime", "-d", required=True)
    create_p.add_argument("--duration", "-l", type=int, default=45)
    create_p.add_argument("--timezone", "-z", default="America/New_York")
    create_p.add_argument("--agenda", "-a")

    # get
    get_p = subparsers.add_parser("get", help="Get meeting")
    get_p.add_argument("meeting_id", type=int)

    # update
    update_p = subparsers.add_parser("update", help="Update meeting")
    update_p.add_argument("meeting_id", type=int)
    update_p.add_argument("--topic", "-t")
    update_p.add_argument("--datetime", "-d")
    update_p.add_argument("--duration", "-l", type=int)
    update_p.add_argument("--agenda", "-a")

    # recordings
    rec_p = subparsers.add_parser("recordings", help="List recordings")
    rec_p.add_argument("--from", dest="from_date", required=True)
    rec_p.add_argument("--to", dest="to_date")

    # recording
    rec_get_p = subparsers.add_parser("recording", help="Get recording")
    rec_get_p.add_argument("meeting_id", type=int)

    # participants
    part_p = subparsers.add_parser("participants", help="Get participants")
    part_p.add_argument("meeting_id", type=int)

    # summary
    sum_p = subparsers.add_parser("summary", help="Get meeting summary")
    sum_p.add_argument("meeting_id", type=int)

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "create": cmd_create,
        "get": cmd_get,
        "update": cmd_update,
        "recordings": cmd_recordings,
        "recording": cmd_recording,
        "participants": cmd_participants,
        "summary": cmd_summary,
    }

    try:
        asyncio.run(commands[args.command](args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
