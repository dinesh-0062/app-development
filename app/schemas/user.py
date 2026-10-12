from typing import Optional, List
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "member"
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    fcm_token: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    fcm_token: Optional[str] = None


class UserNotificationSettings(BaseModel):
    class_reminders: bool = True
    new_messages: bool = True
    incoming_calls: bool = True
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = "22:00"
    quiet_hours_end: Optional[str] = "08:00"


class UserResponse(UserBase):
    id: str
    is_active: bool = True
    notification_settings: Optional[UserNotificationSettings] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
