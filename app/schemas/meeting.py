from typing import Optional, List
from pydantic import BaseModel


class ActionItem(BaseModel):
    id: str
    task: str
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    completed: bool = False


class MeetingBase(BaseModel):
    title: str
    agenda: Optional[str] = ""
    start_time: str  # ISO timestamp or YYYY-MM-DD HH:MM
    duration_minutes: int = 30
    attendees: List[str] = []
    call_room_id: Optional[str] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    agenda: Optional[str] = None
    start_time: Optional[str] = None
    notes: Optional[str] = None
    action_items: Optional[List[ActionItem]] = None


class MeetingResponse(MeetingBase):
    id: str
    creator_id: str
    creator_name: str
    notes: Optional[str] = ""
    action_items: List[ActionItem] = []
    created_at: str
