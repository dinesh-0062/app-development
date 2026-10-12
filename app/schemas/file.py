from typing import Optional
from pydantic import BaseModel


class FileResponse(BaseModel):
    id: str
    file_name: str
    file_url: str
    file_type: str  # "pdf", "image", "doc", "other"
    size_bytes: int
    uploader_id: str
    uploader_name: str
    class_id: Optional[str] = None
    topic: Optional[str] = None
    created_at: str
