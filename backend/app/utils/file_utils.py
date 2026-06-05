"""File handling utilities."""
import os
import uuid
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile, HTTPException
from loguru import logger

from app.config import settings


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
}


async def save_upload(file: UploadFile, dest_dir: str) -> dict:
    """Save an uploaded file securely and return metadata."""
    # Validate extension
    original_name = file.filename or "unknown.pdf"
    ext = Path(original_name).suffix.lower()
    if ext not in (".pdf",):
        raise HTTPException(status_code=400, detail=f"Only PDF files are accepted (got {ext})")

    # Generate secure filename
    unique_id = str(uuid.uuid4())
    safe_filename = f"{unique_id}{ext}"
    dest_path = os.path.join(dest_dir, safe_filename)

    os.makedirs(dest_dir, exist_ok=True)

    # Stream file to disk and compute hash simultaneously
    hasher = hashlib.sha256()
    total_bytes = 0

    async with aiofiles.open(dest_path, "wb") as f:
        while chunk := await file.read(65536):
            if total_bytes + len(chunk) > settings.max_file_size_bytes:
                os.unlink(dest_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB}MB"
                )
            await f.write(chunk)
            hasher.update(chunk)
            total_bytes += len(chunk)

    if total_bytes == 0:
        os.unlink(dest_path)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Verify it's actually a PDF by checking magic bytes
    with open(dest_path, "rb") as f:
        header = f.read(5)
    if not header.startswith(b"%PDF-"):
        os.unlink(dest_path)
        raise HTTPException(status_code=400, detail="File does not appear to be a valid PDF")

    return {
        "filename": safe_filename,
        "original_filename": original_name,
        "file_path": dest_path,
        "file_size": total_bytes,
        "file_hash": hasher.hexdigest(),
    }


def safe_delete(file_path: str):
    """Safely delete a file, logging errors."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning(f"Could not delete {file_path}: {e}")


def get_file_size_human(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
