import os
from fastapi import UploadFile
import cloudinary
import cloudinary.uploader

_cloudinary_configured = False


def _ensure_cloudinary_config():
    global _cloudinary_configured
    if _cloudinary_configured:
        return
    cloud_name = os.getenv("CLOUD_NAME")
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError("Cloudinary env vars missing: CLOUD_NAME, API_KEY, API_SECRET")
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _cloudinary_configured = True


def save_upload_file(upload: UploadFile) -> str:
    _ensure_cloudinary_config()
    upload.file.seek(0)
    result = cloudinary.uploader.upload(
        upload.file,
        resource_type="auto",
        filename=upload.filename or None,
        use_filename=True,
        unique_filename=True,
    )
    secure_url = result.get("secure_url")
    if not secure_url:
        raise RuntimeError("Cloudinary upload failed: missing secure_url")
    return secure_url
