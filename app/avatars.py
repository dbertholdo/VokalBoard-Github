"""
Profile picture upload.

The file is saved to disk, in AVATAR_DIR (defaults to app/static/avatars/,
but configurable via the AVATAR_DIR environment variable — see note below).
Photos are served by a dedicated route (GET /avatars/{file} in
app/main.py), not by StaticFiles — this way AVATAR_DIR can point to
any folder, including one outside app/static.

A note on where this gets written: on platforms like
Railway/Render, the container's disk is *ephemeral* by default — a new
deploy wipes out anything written here, and the person would need to
re-upload their photo. The fix is to configure a "Volume" (persistent
disk) on the deploy platform and point AVATAR_DIR at it — see the README,
"Profile pictures" section.

Every uploaded image is processed before being saved:
- automatic reorientation (fixes phone photos that come out "sideways",
  using the EXIF metadata, which we then strip — so no
  location/device data from the original photo is retained);
- resizing (no saved profile picture exceeds MAX_AVATAR_DIMENSION
  pixels on its longer side — an avatar doesn't need more resolution
  than that, and it saves space/bandwidth with no visible loss);
- conversion to WEBP (a much lighter format than JPEG/PNG at this
  quality level, with transparency support).
"""
import io
import os

from fastapi import UploadFile
from PIL import Image, ImageOps

AVATAR_DIR = os.getenv("AVATAR_DIR", os.path.join("app", "static", "avatars"))

# Limit for the ORIGINAL uploaded file, before any compression —
# generous enough to accept an unedited phone photo (those easily
# exceed 5-10 MB), but prevents someone from uploading an absurdly
# large file just to overload the server.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

MAX_AVATAR_DIMENSION = 512  # longer side of the processed image, in pixels
AVATAR_QUALITY = 82  # WEBP quality (0-100) — beyond this the visual gain is imperceptible

# Content-Type accepted on upload. The extension finally saved to disk
# is always .webp (see STORAGE_EXTENSION) — we convert everything,
# regardless of the original format uploaded.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
STORAGE_EXTENSION = ".webp"

# Extensions this project saved in earlier versions (before the
# automatic conversion to webp) — kept here only so remove_existing_avatar
# can clean up an old photo with a different extension, if one exists.
_LEGACY_EXTENSIONS = {".jpg", ".png", ".webp"}


def avatar_path_for(user_id: int) -> str:
    return os.path.join(AVATAR_DIR, f"{user_id}{STORAGE_EXTENSION}")


def remove_existing_avatar(user_id: int) -> None:
    """Removes any previous avatar for this user, regardless of extension."""
    for ext in _LEGACY_EXTENSIONS:
        path = os.path.join(AVATAR_DIR, f"{user_id}{ext}")
        if os.path.exists(path):
            os.remove(path)


async def save_avatar(user_id: int, upload: UploadFile) -> str | None:
    """
    Processes and saves the upload, returning the public URL (e.g.
    "/avatars/42.webp"), or None if the file is invalid (unsupported
    type, larger than MAX_UPLOAD_BYTES, or not actually a real image)
    — in that case, nothing is written and the caller decides what to
    do (e.g. ignore it and keep the old photo).
    """
    if not upload or not upload.filename:
        return None

    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        return None

    content = await upload.read()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        return None

    try:
        # .verify() detects a corrupted file or one that isn't actually
        # an image (even if it arrived with an image Content-Type — the
        # browser can lie about that header). It "consumes" the object,
        # so we reopen it right after to actually process it.
        Image.open(io.BytesIO(content)).verify()
        image = Image.open(io.BytesIO(content))
    except Exception:
        return None

    image = ImageOps.exif_transpose(image)  # fixes orientation and discards the original EXIF data

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "transparency" in image.info or image.mode == "P" else "RGB")

    image.thumbnail((MAX_AVATAR_DIMENSION, MAX_AVATAR_DIMENSION), Image.LANCZOS)

    os.makedirs(AVATAR_DIR, exist_ok=True)
    remove_existing_avatar(user_id)

    image.save(avatar_path_for(user_id), format="WEBP", quality=AVATAR_QUALITY, method=6)

    return f"/avatars/{user_id}{STORAGE_EXTENSION}"
