from typing import Optional, Dict
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    type: str  # "message", "incoming_call", "class_reminder", "class_update", "file_shared", "rsvp_update"
    data: Optional[Dict[str, str]] = {}
    is_read: bool = False
    created_at: str
