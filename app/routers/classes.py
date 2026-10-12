from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.schemas.class_schema import (
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    RSVPCreate,
    FeedbackCreate,
    TopicSuggestionCreate,
    TopicSuggestionResponse
)

router = APIRouter(prefix="/classes", tags=["Classes & Schedule"])


async def check_class_conflict(date: str, start_time: str, duration_minutes: int, db: AsyncIOMotorDatabase, exclude_id: str = None) -> bool:
    """
    Checks if a proposed class time overlaps with an existing class on the same date.
    Returns True if conflict exists.
    """
    existing_classes = await db.classes.find({"date": date}).to_list(100)

    try:
        sh, sm = map(int, start_time.split(":"))
        new_start = sh * 60 + sm
        new_end = new_start + duration_minutes

        for cls in existing_classes:
            if exclude_id and str(cls["_id"]) == exclude_id:
                continue
            e_st = cls.get("start_time", "00:00")
            e_dur = cls.get("duration_minutes", 60)
            eh, em = map(int, e_st.split(":"))
            e_start = eh * 60 + em
            e_end = e_start + e_dur

            # Check overlap: (new_start < e_end) and (new_end > e_start)
            if new_start < e_end and new_end > e_start:
                return True
    except Exception:
        pass
    return False


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_in: ClassCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    # Conflict check
    has_conflict = await check_class_conflict(class_in.date, class_in.start_time, class_in.duration_minutes, db)
    if has_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Class conflict detected! Another class is scheduled during this time slot."
        )

    doc = class_in.model_dump()
    doc["summary_notes"] = ""
    doc["rsvps"] = []
    doc["feedbacks"] = []
    doc["created_at"] = datetime.now(timezone.utc).isoformat()

    res = await db.classes.insert_one(doc)
    doc["id"] = str(res.inserted_id)

    # Also automatically create a dedicated chat room for this class!
    chat_doc = {
        "name": f"Chat: {class_in.topic}",
        "type": "class",
        "members": [current_user["id"]],
        "class_id": doc["id"],
        "last_message": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat_doc)

    return doc


@router.get("", response_model=List[ClassResponse])
async def list_classes(
    date: Optional[str] = Query(None, description="Filter by YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date for range filter"),
    end_date: Optional[str] = Query(None, description="End date for range filter"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    query = {}
    if date:
        query["date"] = date
    elif start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}

    classes = await db.classes.find(query).sort("date", 1).to_list(200)
    res = []
    for c in classes:
        c["id"] = str(c["_id"])
        res.append(c)
    return res


@router.get("/today", response_model=List[ClassResponse])
async def get_today_classes(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    classes = await db.classes.find({"date": today_str}).sort("start_time", 1).to_list(50)
    res = []
    for c in classes:
        c["id"] = str(c["_id"])
        res.append(c)
    return res


@router.get("/rota")
async def get_weekly_rota(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Returns weekly rota summary: list of teachers and their class assignments for the current week.
    """
    classes = await db.classes.find().sort("date", -1).limit(50).to_list(50)
    users = await db.users.find({"is_active": True}).to_list(100)

    user_map = {str(u["_id"]): u["full_name"] for u in users}
    turn_stats = {uid: 0 for uid in user_map}

    for c in classes:
        tid = c.get("teacher_id")
        if tid in turn_stats:
            turn_stats[tid] += 1

    rota_list = [
        {"user_id": uid, "user_name": user_map[uid], "total_classes_taught": count}
        for uid, count in turn_stats.items()
    ]
    return rota_list


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class_details(
    class_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    cls = await db.classes.find_one({"_id": ObjectId(class_id)})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    cls["id"] = str(cls["_id"])
    return cls


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: str,
    class_in: ClassUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    cls = await db.classes.find_one({"_id": ObjectId(class_id)})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    update_dict = {k: v for k, v in class_in.model_dump().items() if v is not None}

    # Conflict check if date or time changed
    new_date = update_dict.get("date", cls.get("date"))
    new_time = update_dict.get("start_time", cls.get("start_time"))
    new_dur = update_dict.get("duration_minutes", cls.get("duration_minutes", 60))

    if "date" in update_dict or "start_time" in update_dict:
        conflict = await check_class_conflict(new_date, new_time, new_dur, db, exclude_id=class_id)
        if conflict:
            raise HTTPException(status_code=409, detail="Updated class time conflicts with an existing class!")

    if update_dict:
        await db.classes.update_one({"_id": ObjectId(class_id)}, {"$set": update_dict})

    updated = await db.classes.find_one({"_id": ObjectId(class_id)})
    updated["id"] = str(updated["_id"])
    return updated


@router.delete("/{class_id}")
async def delete_class(
    class_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    res = await db.classes.delete_one({"_id": ObjectId(class_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Class not found")
    return {"message": "Class deleted successfully"}


@router.post("/{class_id}/rsvp")
async def rsvp_class(
    class_id: str,
    rsvp: RSVPCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    cls = await db.classes.find_one({"_id": ObjectId(class_id)})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    rsvps = cls.get("rsvps", [])
    # Remove existing RSVP from this user
    rsvps = [r for r in rsvps if r.get("user_id") != current_user["id"]]

    new_entry = {
        "user_id": current_user["id"],
        "user_name": current_user["full_name"],
        "user_avatar": current_user.get("avatar_url"),
        "status": rsvp.status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    rsvps.append(new_entry)

    await db.classes.update_one({"_id": ObjectId(class_id)}, {"$set": {"rsvps": rsvps}})
    return {"message": "RSVP updated successfully", "rsvps": rsvps}


@router.post("/{class_id}/feedback")
async def add_class_feedback(
    class_id: str,
    feedback: FeedbackCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    cls = await db.classes.find_one({"_id": ObjectId(class_id)})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    feedbacks = cls.get("feedbacks", [])
    entry = {
        "user_id": current_user["id"],
        "user_name": current_user["full_name"],
        "rating": feedback.rating,
        "comment": feedback.comment or "",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    feedbacks.append(entry)

    await db.classes.update_one({"_id": ObjectId(class_id)}, {"$set": {"feedbacks": feedbacks}})
    return {"message": "Feedback submitted", "feedbacks": feedbacks}


# Topic Backlog & Suggestion Board
@router.post("/topics/suggest", response_model=TopicSuggestionResponse)
async def suggest_topic(
    sug: TopicSuggestionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    doc = {
        "topic": sug.topic,
        "description": sug.description or "",
        "suggested_by_id": current_user["id"],
        "suggested_by_name": current_user["full_name"],
        "upvotes": [current_user["id"]],
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    res = await db.topic_suggestions.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    return doc


@router.get("/topics/backlog", response_model=List[TopicSuggestionResponse])
async def list_topic_backlog(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    topics = await db.topic_suggestions.find().sort("created_at", -1).to_list(100)
    res = []
    for t in topics:
        t["id"] = str(t["_id"])
        res.append(t)
    return res


@router.post("/topics/{topic_id}/upvote")
async def upvote_topic(
    topic_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    t = await db.topic_suggestions.find_one({"_id": ObjectId(topic_id)})
    if not t:
        raise HTTPException(status_code=404, detail="Topic suggestion not found")

    upvotes = t.get("upvotes", [])
    uid = current_user["id"]
    if uid in upvotes:
        upvotes.remove(uid)
    else:
        upvotes.append(uid)

    await db.topic_suggestions.update_one({"_id": ObjectId(topic_id)}, {"$set": {"upvotes": upvotes}})
    return {"message": "Upvote toggled", "upvotes_count": len(upvotes)}
