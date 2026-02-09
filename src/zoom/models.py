"""Pydantic models for Zoom data."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Meeting(BaseModel):
    """Zoom meeting."""
    id: int
    topic: str
    start_time: datetime
    duration: int
    timezone: str = "America/New_York"
    join_url: Optional[str] = None
    start_url: Optional[str] = None
    password: Optional[str] = None
    agenda: Optional[str] = None
    status: Optional[str] = None
    host_email: Optional[str] = None


class MeetingCreate(BaseModel):
    """Input for creating a meeting."""
    topic: str
    start_time: str  # ISO format
    duration: int = 45
    timezone: str = "America/New_York"
    agenda: Optional[str] = None
    waiting_room: bool = True
    auto_recording: str = "cloud"  # cloud, local, none


class Registrant(BaseModel):
    """Meeting registrant."""
    registrant_id: Optional[str] = None
    email: str
    first_name: str
    last_name: str = ""
    join_url: Optional[str] = None


class RecordingFile(BaseModel):
    """Recording file."""
    id: str
    file_type: str
    file_size: int
    download_url: Optional[str] = None
    play_url: Optional[str] = None
    status: Optional[str] = None


class Recording(BaseModel):
    """Meeting recording."""
    meeting_id: int
    topic: str
    start_time: datetime
    duration: int
    share_url: Optional[str] = None
    password: Optional[str] = None
    files: list[RecordingFile] = Field(default_factory=list)


class Participant(BaseModel):
    """Meeting participant."""
    name: Optional[str] = None
    email: Optional[str] = None
    join_time: Optional[datetime] = None
    leave_time: Optional[datetime] = None
    duration: Optional[int] = None


class MeetingSummary(BaseModel):
    """AI-generated meeting summary."""
    meeting_id: int
    summary: Optional[str] = None
    next_steps: Optional[list[str]] = None
    topics: Optional[list[str]] = None
