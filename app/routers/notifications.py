from typing import List
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
async def list_user_notifications(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    notifs = await db.notifications.find({"user_id": current_user["id"]}).sort("created_at", -1).to_list(100)
    res = []
    for n in notifs:
        n["id"] = str(n["_id"])
        res.append(n)
    return res


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": current_user["id"]},
        {"$set": {"is_read": True}}
    )
    return {"message": "Notification marked as read"}


@router.put("/read-all")
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    await db.notifications.update_many(
        {"user_id": current_user["id"], "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"message": "All notifications marked as read"}
