from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.core.deps import get_current_user
from app.services.file_service import upload_file_to_storage
from app.schemas.file import FileResponse

router = APIRouter(prefix="/files", tags=["Files & Documents"])


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    class_id: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 20MB limit.")

    file_url, file_type = await upload_file_to_storage(
        content,
        file.filename,
        file.content_type or "application/octet-stream"
    )

    doc = {
        "file_name": file.filename,
        "file_url": file_url,
        "file_type": file_type,
        "size_bytes": len(content),
        "uploader_id": current_user["id"],
        "uploader_name": current_user["full_name"],
        "class_id": class_id,
        "topic": topic or "",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    res = await db.files.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    return doc


@router.get("", response_model=List[FileResponse])
async def list_files(
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    query = {}
    if class_id:
        query["class_id"] = class_id

    files = await db.files.find(query).sort("created_at", -1).to_list(100)
    res = []
    for f in files:
        f["id"] = str(f["_id"])
        res.append(f)
    return res


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    f = await db.files.find_one({"_id": ObjectId(file_id)})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    if f["uploader_id"] != current_user["id"] and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete this file")

    await db.files.delete_one({"_id": ObjectId(file_id)})
    return {"message": "File deleted successfully"}
