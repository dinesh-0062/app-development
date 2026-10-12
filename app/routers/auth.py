from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.schemas.auth import (
    Token,
    LoginRequest,
    SignUpRequest,
    RefreshTokenRequest,
    ForgotPasswordRequest
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    existing = await db.users.find_one({"email": request.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    user_doc = {
        "email": request.email.lower(),
        "password_hash": get_password_hash(request.password),
        "full_name": request.full_name,
        "role": request.role if request.role in ["admin", "member"] else "member",
        "avatar_url": None,
        "bio": "",
        "fcm_token": None,
        "is_active": True,
        "notification_settings": {
            "class_reminders": True,
            "new_messages": True,
            "incoming_calls": True,
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00"
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    user_response = {
        "id": user_id,
        "email": user_doc["email"],
        "full_name": user_doc["full_name"],
        "role": user_doc["role"],
        "avatar_url": user_doc["avatar_url"],
        "bio": user_doc["bio"],
        "is_active": True
    }

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_response
    }


@router.post("/login", response_model=Token)
async def login(request: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    user = await db.users.find_one({"email": request.email.lower()})
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is deactivated."
        )

    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    user_response = {
        "id": user_id,
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "avatar_url": user.get("avatar_url"),
        "bio": user.get("bio", ""),
        "fcm_token": user.get("fcm_token"),
        "is_active": user.get("is_active", True)
    }

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_response
    }


@router.post("/refresh", response_model=dict)
async def refresh_token(request: RefreshTokenRequest):
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )

    user_id = payload.get("sub")
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    user = await db.users.find_one({"email": request.email.lower()})
    if user:
        # In production, send a password reset email link
        return {"message": "If this email is registered, a password reset link has been sent."}
    return {"message": "If this email is registered, a password reset link has been sent."}
