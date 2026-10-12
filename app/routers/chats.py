from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.core.websocket_manager import manager
from app.schemas.chat import (
    ChatCreate,
    ChatResponse,
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    ReactionCreate
)

router = APIRouter(prefix="/chats", tags=["Chats & Messaging"])


@router.post("", response_model=ChatResponse)
async def create_or_get_chat(
    chat_in: ChatCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    members = list(set(chat_in.members + [current_user["id"]]))

    # If direct chat, check if one already exists
    if chat_in.type == "direct" and len(members) == 2:
        existing = await db.chats.find_one({
            "type": "direct",
            "members": {"$all": members, "$size": 2}
        })
        if existing:
            existing["id"] = str(existing["_id"])
            return existing

    doc = {
        "name": chat_in.name or ("Direct Chat" if chat_in.type == "direct" else "Group Chat"),
        "type": chat_in.type,
        "members": members,
        "class_id": chat_in.class_id,
        "last_message": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    res = await db.chats.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    return doc


@router.get("", response_model=List[ChatResponse])
async def list_user_chats(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    # Ensure default main group chat exists
    default_chat = await db.chats.find_one({"type": "group", "name": "TeachSync Team General"})
    if not default_chat:
        all_users = await db.users.find({"is_active": True}).to_list(100)
        uids = [str(u["_id"]) for u in all_users]
        await db.chats.insert_one({
            "name": "TeachSync Team General",
            "type": "group",
            "members": uids,
            "class_id": None,
            "last_message": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    chats = await db.chats.find({"members": current_user["id"]}).sort("created_at", -1).to_list(100)
    res = []
    for c in chats:
        c["id"] = str(c["_id"])
        res.append(c)
    return res


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    chat_id: str,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    messages = await db.messages.find({"chat_id": chat_id}).sort("created_at", 1).limit(limit).to_list(limit)
    res = []
    for m in messages:
        m["id"] = str(m["_id"])
        res.append(m)
    return res


@router.post("/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    chat_id: str,
    msg_in: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    chat = await db.chats.find_one({"_id": ObjectId(chat_id)})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    msg_doc = {
        "chat_id": chat_id,
        "sender_id": current_user["id"],
        "sender_name": current_user["full_name"],
        "sender_avatar": current_user.get("avatar_url"),
        "content": msg_in.content,
        "message_type": msg_in.message_type,
        "file_url": msg_in.file_url,
        "file_name": msg_in.file_name,
        "reply_to_id": msg_in.reply_to_id,
        "reactions": [],
        "is_pinned": False,
        "is_edited": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    res = await db.messages.insert_one(msg_doc)
    msg_doc["id"] = str(res.inserted_id)

    # Update chat last_message
    last_msg = {
        "content": msg_in.content,
        "sender_name": current_user["full_name"],
        "created_at": msg_doc["created_at"]
    }
    await db.chats.update_one({"_id": ObjectId(chat_id)}, {"$set": {"last_message": last_msg}})

    # Broadcast via WebSocket to all chat members
    ws_event = {
        "type": "new_message",
        "payload": msg_doc
    }
    await manager.broadcast_to_users(ws_event, chat.get("members", []))

    return msg_doc


@router.put("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: str,
    msg_in: MessageUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    msg = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["sender_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Cannot edit someone else's message")

    await db.messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"content": msg_in.content, "is_edited": True}}
    )

    updated = await db.messages.find_one({"_id": ObjectId(message_id)})
    updated["id"] = str(updated["_id"])

    # WS broadcast
    chat = await db.chats.find_one({"_id": ObjectId(msg["chat_id"])})
    if chat:
        await manager.broadcast_to_users({"type": "message_edited", "payload": updated}, chat.get("members", []))

    return updated


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    msg = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["sender_id"] != current_user["id"] and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete this message")

    await db.messages.delete_one({"_id": ObjectId(message_id)})

    chat = await db.chats.find_one({"_id": ObjectId(msg["chat_id"])})
    if chat:
        await manager.broadcast_to_users(
            {"type": "message_deleted", "payload": {"message_id": message_id, "chat_id": msg["chat_id"]}},
            chat.get("members", [])
        )

    return {"message": "Message deleted"}


@router.post("/messages/{message_id}/reactions")
async def toggle_reaction(
    message_id: str,
    reaction_in: ReactionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    msg = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    reactions = msg.get("reactions", [])
    emoji = reaction_in.emoji
    uid = current_user["id"]

    # Find existing emoji reaction entry
    target_reaction = next((r for r in reactions if r["emoji"] == emoji), None)
    if target_reaction:
        if uid in target_reaction["users"]:
            target_reaction["users"].remove(uid)
            if not target_reaction["users"]:
                reactions.remove(target_reaction)
        else:
            target_reaction["users"].append(uid)
    else:
        reactions.append({"emoji": emoji, "users": [uid]})

    await db.messages.update_one({"_id": ObjectId(message_id)}, {"$set": {"reactions": reactions}})

    updated = await db.messages.find_one({"_id": ObjectId(message_id)})
    updated["id"] = str(updated["_id"])

    chat = await db.chats.find_one({"_id": ObjectId(msg["chat_id"])})
    if chat:
        await manager.broadcast_to_users({"type": "reaction_updated", "payload": updated}, chat.get("members", []))

    return updated


@router.post("/messages/{message_id}/pin")
async def toggle_pin_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    msg = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    new_pin = not msg.get("is_pinned", False)
    await db.messages.update_one({"_id": ObjectId(message_id)}, {"$set": {"is_pinned": new_pin}})
    return {"message": "Pin status updated", "is_pinned": new_pin}


@router.get("/search/query")
async def search_messages(
    q: str = Query(..., min_length=2),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    user_chats = await db.chats.find({"members": current_user["id"]}).to_list(100)
    chat_ids = [str(c["_id"]) for c in user_chats]

    matches = await db.messages.find({
        "chat_id": {"$in": chat_ids},
        "content": {"$regex": q, "$options": "i"}
    }).limit(50).to_list(50)

    res = []
    for m in matches:
        m["id"] = str(m["_id"])
        res.append(m)
    return res
