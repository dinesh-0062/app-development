import os
import logging
from typing import Tuple
from app.config import settings

logger = logging.getLogger("teachsync.file")

_cloudinary_configured = False


def init_cloudinary():
    global _cloudinary_configured
    if _cloudinary_configured:
        return
    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        import cloudinary
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET
        )
        _cloudinary_configured = True


async def upload_file_to_storage(file_bytes: bytes, filename: str, content_type: str) -> Tuple[str, str]:
    """
    Uploads file to Cloudinary or fallback local directory.
    Returns tuple: (file_url, file_type)
    """
    init_cloudinary()

    # Determine type category
    file_type = "other"
    if content_type.startswith("image/"):
        file_type = "image"
    elif content_type == "application/pdf":
        file_type = "pdf"
    elif "word" in content_type or "document" in content_type or filename.endswith(('.doc', '.docx', '.txt')):
        file_type = "doc"

    if _cloudinary_configured:
        try:
            import cloudinary.uploader
            res = cloudinary.uploader.upload(
                file_bytes,
                folder="teachsync_uploads",
                resource_type="auto",
                public_id=filename.rsplit('.', 1)[0]
            )
            return res.get("secure_url"), file_type
        except Exception as e:
            logger.error(f"Cloudinary upload error: {e}, falling back to local file storage")

    # Local fallback storage
    upload_dir = "static_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    file_url = f"/static_uploads/{filename}"
    return file_url, file_type
