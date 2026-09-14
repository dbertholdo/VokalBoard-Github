"""
Image upload inside a post (WordPress-style editor — see
app/static/js/post-editor.js and the POST /admin/posts/upload-image
route in app/routers/admin_routes.py).

Same pattern as app/avatars.py (re-orients via EXIF, resizes,
converts to WEBP), with two differences: here there can be SEVERAL
images per post (not one per user_id), so the filename is a random
token instead of the id; and the max-side limit is much bigger (an
image inside a long text can be much larger than a neat little
512px avatar).

The ephemeral-disk warning (Railway/Render) is the same as in
app/avatars.py — see the README, "Profile photos" section.
"""
import io
import os
import secrets

from fastapi import UploadFile
from PIL import Image, ImageOps

POST_IMAGE_DIR = os.getenv("POST_IMAGE_DIR", os.path.join("app", "static", "post_images"))

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB, same as the avatar — an unedited phone photo
MAX_IMAGE_DIMENSION = 1600  # max side — much bigger than an avatar, this is a "reading" image
IMAGE_QUALITY = 85

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
STORAGE_EXTENSION = ".webp"


async def save_post_image(upload: UploadFile) -> str | None:
    """
    Processes and saves the upload, returning the public URL (e.g.
    "/post-images/AbC123xyz.webp"), or None if invalid — in that
    case nothing is written.
    """
    if not upload or not upload.filename:
        return None
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        return None

    content = await upload.read()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        return None

    try:
        Image.open(io.BytesIO(content)).verify()
        image = Image.open(io.BytesIO(content))
    except Exception:
        return None

    image = ImageOps.exif_transpose(image)

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "transparency" in image.info or image.mode == "P" else "RGB")

    image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)

    os.makedirs(POST_IMAGE_DIR, exist_ok=True)
    filename = secrets.token_urlsafe(16).replace("_", "").replace("-", "") + STORAGE_EXTENSION
    image.save(os.path.join(POST_IMAGE_DIR, filename), format="WEBP", quality=IMAGE_QUALITY, method=6)

    return f"/post-images/{filename}"
