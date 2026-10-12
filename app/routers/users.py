from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.schemas.user import UserResponse, UserUpdate, UserNotificationSettings

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    user_id = current_user["id"]
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

    if update_dict:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_dict})

    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    updated_user["id"] = str(updated_user["_id"])
    return updated_user


@router.put("/me/notification-settings")
async def update_notification_settings(
    settings: UserNotificationSettings,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    user_id = current_user["id"]
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"notification_settings": settings.model_dump()}}
    )
    return {"message": "Notification settings updated successfully."}


@router.get("", response_model=List[UserResponse])
async def list_all_users(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    users = await db.users.find({"is_active": True}).to_list(100)
    res = []
    for u in users:
        u["id"] = str(u["_id"])
        res.append(u)
    return res
