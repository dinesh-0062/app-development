from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.core.websocket_manager import manager
from app.services.agora_service import generate_agora_rtc_token
from app.services.fcm_service import send_fcm_notification
from app.schemas.call import (
    CallInitiateRequest,
    AgoraTokenResponse,
    CallLogResponse
)

router = APIRouter(prefix="/calls", tags=["Calls & Signaling"])


@router.get("/token", response_model=AgoraTokenResponse)
async def get_agora_token(
    channel_name: str = Query(...),
    uid: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    token = generate_agora_rtc_token(channel_name=channel_name, uid=uid)
    return {
        "token": token,
        "channel_name": channel_name,
        "uid": uid
    }


@router.post("/initiate")
async def initiate_call(
    req: CallInitiateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    channel_name = req.channel_name
    call_type = req.call_type

    # Create call log entry
    call_log = {
        "channel_name": channel_name,
        "call_type": call_type,
        "caller_id": current_user["id"],
        "caller_name": current_user["full_name"],
        "caller_avatar": current_user.get("avatar_url"),
        "participants": [current_user["id"]],
        "class_id": req.class_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "duration_seconds": 0
    }
    res = await db.call_logs.insert_one(call_log)
    call_id = str(res.inserted_id)

    # Signal payload
    signal_data = {
        "type": "incoming_call",
        "payload": {
            "call_id": call_id,
            "channel_name": channel_name,
            "call_type": call_type,
            "caller_id": current_user["id"],
            "caller_name": current_user["full_name"],
            "caller_avatar": current_user.get("avatar_url"),
            "class_id": req.class_id
        }
    }

    # Recipients: if list provided, send to those user_ids; if empty, find active team members
    recipients = req.recipient_ids
    if not recipients:
        all_u = await db.users.find({"is_active": True, "_id": {"$ne": ObjectId(current_user["id"])}}).to_list(100)
        recipients = [str(u["_id"]) for u in all_u]

    # 1. Send WebSocket signal
    await manager.broadcast_to_users(signal_data, recipients)

    # 2. Send FCM Push Notification for high priority ringing
    for r_id in recipients:
        r_user = await db.users.find_one({"_id": ObjectId(r_id)})
        if r_user and r_user.get("fcm_token"):
            await send_fcm_notification(
                fcm_token=r_user["fcm_token"],
                title=f"Incoming {call_type.capitalize()} Call",
                body=f"{current_user['full_name']} is calling you...",
                data={
                    "type": "incoming_call",
                    "channel_name": channel_name,
                    "caller_name": current_user["full_name"],
                    "call_type": call_type
                }
            )

    return {
        "message": "Call initiated and signaling dispatched",
        "call_id": call_id,
        "channel_name": channel_name
    }


@router.post("/end/{call_id}")
async def end_call(
    call_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    c = await db.call_logs.find_one({"_id": ObjectId(call_id)})
    if not c:
        raise HTTPException(status_code=404, detail="Call log not found")

    ended_at = datetime.now(timezone.utc).isoformat()
    await db.call_logs.update_one({"_id": ObjectId(call_id)}, {"$set": {"ended_at": ended_at}})

    return {"message": "Call ended"}


@router.get("/logs", response_model=List[CallLogResponse])
async def get_call_logs(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    logs = await db.call_logs.find({"participants": current_user["id"]}).sort("started_at", -1).to_list(50)
    res = []
    for l in logs:
        l["id"] = str(l["_id"])
        res.append(l)
    return res
