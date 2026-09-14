"""
Upload de imagem dentro de um post (editor estilo WordPress — ver
app/static/js/post-editor.js e a rota POST /admin/posts/upload-image
em app/routers/admin_routes.py).

Mesmo padrão de app/avatars.py (reorienta via EXIF, redimensiona,
converte pra WEBP), com duas diferenças: aqui podem existir VÁRIAS
imagens por post (não uma por user_id), então o nome do arquivo é um
token aleatório em vez do id; e o limite de lado maior é bem maior
(uma imagem dentro de um texto longo pode ser bem mais que um avatar
redondinho de 512px).

Aviso de disco efêmero (Railway/Render) é o mesmo de app/avatars.py —
ver README, seção "Fotos de perfil".
"""
import io
import os
import secrets

from fastapi import UploadFile
from PIL import Image, ImageOps

POST_IMAGE_DIR = os.getenv("POST_IMAGE_DIR", os.path.join("app", "static", "post_images"))

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB, igual ao avatar — foto de celular sem editar
MAX_IMAGE_DIMENSION = 1600  # lado maior — bem mais que um avatar, é imagem "de leitura"
IMAGE_QUALITY = 85

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
STORAGE_EXTENSION = ".webp"


async def save_post_image(upload: UploadFile) -> str | None:
    """
    Processa e salva o upload, devolvendo a URL pública (ex:
    "/post-images/AbC123xyz.webp"), ou None se inválido — nesse caso
    nada é gravado.
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
