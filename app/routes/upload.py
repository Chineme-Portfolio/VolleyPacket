import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from app.models import UploadResponse
from app.services.document_parser import parse_file
from app.services.storage import store
from app.dependencies import get_current_user
from app.database import UserRow
from app import config

router = APIRouter()

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".html", ".htm", ".txt")
ALLOWED_EXTENSIONS = DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS


@router.post("", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), user: UserRow = Depends(get_current_user)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    save_path = os.path.join(config.UPLOAD_FOLDER, f"{file_id}{ext}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
        )
    with open(save_path, "wb") as f:
        f.write(content)
    store.save_local_file(save_path)

    if ext in IMAGE_EXTENSIONS:
        # For images, we don't extract text — the AI will see the image directly
        import base64

        # Detect actual image type from magic bytes (file extension can lie)
        def _detect_media_type(data: bytes, fallback_ext: str) -> str:
            if data[:8] == b'\x89PNG\r\n\x1a\n':
                return "image/png"
            if data[:2] == b'\xff\xd8':
                return "image/jpeg"
            if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                return "image/webp"
            ext_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
            return ext_map.get(fallback_ext, "image/png")

        media_type = _detect_media_type(content, ext)

        image_b64 = base64.b64encode(content).decode("utf-8")
        return UploadResponse(
            file_id=file_id,
            filename=file.filename,
            raw_text="[Image uploaded — AI will analyze visually]",
            detected_fields={
                "is_image": True,
                "image_data": image_b64,
                "image_media_type": media_type,
            },
        )

    try:
        result = parse_file(save_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {e}")

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        raw_text=result["raw_text"],
        detected_fields=result["detected_fields"],
    )
