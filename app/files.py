import os
import uuid
from pathlib import Path
from fastapi import UploadFile
import shutil

UPLOAD_DIR = Path("uploads")

def ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_upload_file(upload: UploadFile) -> str:
    ensure_upload_dir()
    suffix = Path(upload.filename).suffix if upload.filename else ""
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest_path = UPLOAD_DIR / filename
    with dest_path.open("wb") as out_file:
        shutil.copyfileobj(upload.file, out_file)
    return f"/uploads/{filename}"
