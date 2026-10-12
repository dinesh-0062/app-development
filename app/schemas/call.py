from typing import Optional, List
from pydantic import BaseModel


class CallInitiateRequest(BaseModel):
    channel_name: str
    call_type: str = "video"  # "video" or "audio"
    recipient_ids: List[str]  # targeted user IDs or [] for group/channel
    class_id: Optional[str] = None


class AgoraTokenResponse(BaseModel):
    token: str
    channel_name: str
    uid: int


class CallLogResponse(BaseModel):
    id: str
    channel_name: str
    call_type: str
    caller_id: str
    caller_name: str
    participants: List[str]
    class_id: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: Optional[int] = 0
