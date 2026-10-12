from typing import Optional, List, Dict
from pydantic import BaseModel


class ReactionCreate(BaseModel):
    emoji: str


class ReactionItem(BaseModel):
    emoji: str
    users: List[str]  # list of user_ids


class MessageCreate(BaseModel):
    chat_id: str
    content: str
    message_type: str = "text"  # "text", "file", "image", "audio", "system"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    reply_to_id: Optional[str] = None


class MessageUpdate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    sender_name: str
    sender_avatar: Optional[str] = None
    content: str
    message_type: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    reply_to_id: Optional[str] = None
    reactions: List[ReactionItem] = []
    is_pinned: bool = False
    is_edited: bool = False
    created_at: str


class ChatCreate(BaseModel):
    name: Optional[str] = None
    type: str  # "direct", "group", "class"
    members: List[str]  # user_ids
    class_id: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    name: Optional[str] = None
    type: str
    members: List[str]
    class_id: Optional[str] = None
    last_message: Optional[dict] = None
    created_at: str
