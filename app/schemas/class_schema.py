from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class RSVPCreate(BaseModel):
    status: str  # "accepted", "declined", "maybe"


class RSVPResponse(BaseModel):
    user_id: str
    user_name: str
    user_avatar: Optional[str] = None
    status: str
    updated_at: str


class FeedbackCreate(BaseModel):
    rating: int  # 1 to 5
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    user_id: str
    user_name: str
    rating: int
    comment: Optional[str] = None
    created_at: str


class ClassBase(BaseModel):
    topic: str
    description: Optional[str] = ""
    teacher_id: str
    teacher_name: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM (e.g. 15:00)
    duration_minutes: int = 60
    attendees: List[str] = []  # user_ids or ["everyone"]
    is_recurring: bool = False
    recurring_days: List[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    topic: Optional[str] = None
    description: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    attendees: Optional[List[str]] = None
    summary_notes: Optional[str] = None


class ClassResponse(ClassBase):
    id: str
    summary_notes: Optional[str] = ""
    rsvps: List[RSVPResponse] = []
    feedbacks: List[FeedbackResponse] = []
    created_at: str

    class Config:
        from_attributes = True


class TopicSuggestionCreate(BaseModel):
    topic: str
    description: Optional[str] = ""


class TopicSuggestionResponse(BaseModel):
    id: str
    topic: str
    description: str
    suggested_by_id: str
    suggested_by_name: str
    upvotes: List[str] = []
    status: str = "pending"  # "pending", "scheduled", "completed"
    created_at: str
