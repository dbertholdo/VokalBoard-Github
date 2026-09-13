"""
Upload de foto de perfil.

De propósito, isso NÃO usa um serviço externo de armazenamento (tipo S3)
— o arquivo é salvo direto no disco, dentro de app/static/avatars/, que
já é servido publicamente pelo StaticFiles em app/main.py (/static/...).
É a opção mais simples pra um projeto de aprendizado.

Ponto de atenção pra quando for pra produção de verdade: em plataformas
como Railway/Render (free tier), o disco do container é *efêmero* — um
novo deploy apaga os arquivos gravados aqui. Pra um beta pequeno isso é
aceitável (o pior caso é a pessoa precisar reenviar a foto depois de um
deploy), mas se o projeto crescer, o próximo passo seria migrar isso
para um serviço de armazenamento de objetos (S3, Cloudflare R2, etc.) —
listado no README como próximo passo sugerido.
"""
import os

from fastapi import UploadFile

AVATAR_DIR = os.path.join("app", "static", "avatars")
MAX_AVATAR_BYTES = 3 * 1024 * 1024  # 3 MB

# Content-Type -> extensão de arquivo aceita. Checar o Content-Type
# enviado pelo navegador é uma validação simples (não é infalível —
# alguém poderia mentir o header — mas para um projeto de aprendizado,
# combinado com o limite de tamanho, já evita os casos comuns de abuso
# sem precisar de uma biblioteca de processamento de imagem).
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def avatar_path_for(user_id: int, extension: str) -> str:
    return os.path.join(AVATAR_DIR, f"{user_id}{extension}")


def remove_existing_avatar(user_id: int) -> None:
    """Remove qualquer avatar anterior desse usuário, seja qual for a extensão."""
    for ext in ALLOWED_CONTENT_TYPES.values():
        path = avatar_path_for(user_id, ext)
        if os.path.exists(path):
            os.remove(path)


async def save_avatar(user_id: int, upload: UploadFile) -> str | None:
    """
    Salva o upload em disco e devolve a URL pública (ex:
    "/static/avatars/42.jpg"), ou None se o arquivo for inválido
    (tipo não suportado ou maior que MAX_AVATAR_BYTES) — nesse caso,
    nada é gravado e o chamador decide o que fazer (ex: ignorar e
    manter a foto antiga).
    """
    if not upload or not upload.filename:
        return None

    extension = ALLOWED_CONTENT_TYPES.get(upload.content_type)
    if not extension:
        return None

    contents = await upload.read()
    if not contents or len(contents) > MAX_AVATAR_BYTES:
        return None

    os.makedirs(AVATAR_DIR, exist_ok=True)
    remove_existing_avatar(user_id)

    path = avatar_path_for(user_id, extension)
    with open(path, "wb") as f:
        f.write(contents)

    return f"/static/avatars/{user_id}{extension}"
