"""
Expense receipt upload (financial panel / Red Zone).

Same spirit as app/avatars.py (a file on disk, served by its own
route, not directly by StaticFiles — see /financeiro/receipts/{file}
in app/routers/financial_routes.py), but without image processing:
a receipt can be a PDF or a photo, and we want to keep the original
file, not recompress it.
"""
import os
import secrets

from fastapi import UploadFile

RECEIPT_DIR = os.getenv("RECEIPT_DIR", os.path.join("app", "static", "receipts"))

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB — scanned PDFs can be large

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def save_receipt(upload: UploadFile) -> str | None:
    """Saves the receipt and returns the public URL, or None if invalid.

    The saved filename is random (not the original uploaded name) —
    this avoids collisions between expenses and doesn't expose any
    data from the person's original filename.
    """
    if not upload or not upload.filename:
        return None

    extension = ALLOWED_CONTENT_TYPES.get(upload.content_type)
    if not extension:
        return None

    content = await upload.read()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        return None

    os.makedirs(RECEIPT_DIR, exist_ok=True)
    filename = f"{secrets.token_urlsafe(16)}{extension}"
    with open(os.path.join(RECEIPT_DIR, filename), "wb") as f:
        f.write(content)

    return f"/financeiro/receipts/{filename}"
