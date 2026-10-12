from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.schemas.meeting import MeetingCreate, MeetingUpdate, MeetingResponse

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    meeting_in: MeetingCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = meeting_in.model_dump()
    doc["creator_id"] = current_user["id"]
    doc["creator_name"] = current_user["full_name"]
    doc["notes"] = ""
    doc["action_items"] = []
    doc["created_at"] = datetime.now(timezone.utc).isoformat()

    if not doc.get("call_room_id"):
        doc["call_room_id"] = f"meeting_room_{int(datetime.now().timestamp())}"

    res = await db.meetings.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    return doc


@router.get("", response_model=List[MeetingResponse])
async def list_meetings(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    meetings = await db.meetings.find().sort("start_time", 1).to_list(100)
    res = []
    for m in meetings:
        m["id"] = str(m["_id"])
        res.append(m)
    return res


@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: str,
    meeting_in: MeetingUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    m = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")

    update_dict = {k: v for k, v in meeting_in.model_dump().items() if v is not None}
    if update_dict:
        await db.meetings.update_one({"_id": ObjectId(meeting_id)}, {"$set": update_dict})

    updated = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
    updated["id"] = str(updated["_id"])
    return updated


@router.delete("/{meeting_id}")
async def delete_meeting(
    meeting_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    res = await db.meetings.delete_one({"_id": ObjectId(meeting_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"message": "Meeting deleted"}
