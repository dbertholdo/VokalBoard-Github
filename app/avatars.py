"""
Upload de foto de perfil.

O arquivo é salvo em disco, em AVATAR_DIR (por padrão app/static/avatars/,
mas configurável pela variável de ambiente AVATAR_DIR — ver nota abaixo).
As fotos são servidas por uma rota própria (GET /avatars/{arquivo} em
app/main.py), não pelo StaticFiles — assim AVATAR_DIR pode apontar pra
qualquer pasta, inclusive uma fora de app/static.

Ponto de atenção sobre onde isso é gravado: em plataformas como
Railway/Render, o disco do container é *efêmero* por padrão — um novo
deploy apaga tudo que foi gravado aqui, e a pessoa precisaria reenviar
a foto. A correção é configurar um "Volume" (disco persistente) na
plataforma de deploy e apontar AVATAR_DIR pra ele — ver README, seção
"Fotos de perfil".

Toda imagem enviada passa por processamento antes de ser salva:
- reorientação automática (corrige fotos de celular que vêm "deitadas",
  usando o metadado EXIF, e depois o removemos — então nenhum dado de
  localização/aparelho da foto original fica salvo);
- redimensionamento (nenhuma foto de perfil salva passa de
  MAX_AVATAR_DIMENSION pixels no lado maior — um avatar não precisa de
  mais resolução que isso, e economiza espaço/banda sem perda visível);
- conversão pra WEBP (formato bem mais leve que JPEG/PNG pra essa
  qualidade, com suporte a transparência).
"""
import io
import os

from fastapi import UploadFile
from PIL import Image, ImageOps

AVATAR_DIR = os.getenv("AVATAR_DIR", os.path.join("app", "static", "avatars"))

# Limite do arquivo ORIGINAL enviado, antes de qualquer compressão —
# generoso o bastante pra aceitar uma foto de celular sem editar (essas
# facilmente passam de 5-10 MB), mas evita que alguém suba um arquivo
# absurdamente grande só pra sobrecarregar o servidor.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

MAX_AVATAR_DIMENSION = 512  # lado maior da imagem já processada, em pixels
AVATAR_QUALITY = 82  # qualidade WEBP (0-100) — acima disso o ganho visual é imperceptível

# Content-Type aceito no upload. A extensão final salva em disco é
# sempre .webp (ver STORAGE_EXTENSION) — convertemos tudo, independente
# do formato original enviado.
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
STORAGE_EXTENSION = ".webp"

# Extensões que este projeto já salvou em versões anteriores (antes da
# conversão automática pra webp) — mantidas aqui só pra remove_existing_avatar
# conseguir limpar uma foto antiga com extensão diferente, se existir.
_LEGACY_EXTENSIONS = {".jpg", ".png", ".webp"}


def avatar_path_for(user_id: int) -> str:
    return os.path.join(AVATAR_DIR, f"{user_id}{STORAGE_EXTENSION}")


def remove_existing_avatar(user_id: int) -> None:
    """Remove qualquer avatar anterior desse usuário, seja qual for a extensão."""
    for ext in _LEGACY_EXTENSIONS:
        path = os.path.join(AVATAR_DIR, f"{user_id}{ext}")
        if os.path.exists(path):
            os.remove(path)


async def save_avatar(user_id: int, upload: UploadFile) -> str | None:
    """
    Processa e salva o upload, devolvendo a URL pública (ex:
    "/avatars/42.webp"), ou None se o arquivo for inválido (tipo não
    suportado, maior que MAX_UPLOAD_BYTES, ou não for uma imagem de
    verdade) — nesse caso, nada é gravado e o chamador decide o que
    fazer (ex: ignorar e manter a foto antiga).
    """
    if not upload or not upload.filename:
        return None

    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        return None

    content = await upload.read()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        return None

    try:
        # .verify() detecta arquivo corrompido ou que não é realmente uma
        # imagem (mesmo tendo vindo com um Content-Type de imagem — o
        # navegador pode mentir esse header). Ele "consome" o objeto, por
        # isso reabrimos em seguida pra processar de verdade.
        Image.open(io.BytesIO(content)).verify()
        image = Image.open(io.BytesIO(content))
    except Exception:
        return None

    image = ImageOps.exif_transpose(image)  # corrige orientação e descarta o EXIF original

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "transparency" in image.info or image.mode == "P" else "RGB")

    image.thumbnail((MAX_AVATAR_DIMENSION, MAX_AVATAR_DIMENSION), Image.LANCZOS)

    os.makedirs(AVATAR_DIR, exist_ok=True)
    remove_existing_avatar(user_id)

    image.save(avatar_path_for(user_id), format="WEBP", quality=AVATAR_QUALITY, method=6)

    return f"/avatars/{user_id}{STORAGE_EXTENSION}"
