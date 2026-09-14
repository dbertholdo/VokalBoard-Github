"""
Upload de comprovante de despesa (painel financeiro / Zona Vermelha).

Mesmo espírito de app/avatars.py (arquivo em disco, servido por rota
própria, não pelo StaticFiles direto — ver /financeiro/receipts/{arquivo}
em app/routers/financial_routes.py), mas sem processamento de imagem:
um comprovante pode ser PDF ou foto, e queremos guardar o arquivo
original, não recomprimir.
"""
import os
import secrets

from fastapi import UploadFile

RECEIPT_DIR = os.getenv("RECEIPT_DIR", os.path.join("app", "static", "receipts"))

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB — PDFs escaneados podem ser grandes

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def save_receipt(upload: UploadFile) -> str | None:
    """Salva o comprovante e devolve a URL pública, ou None se inválido.

    O nome do arquivo salvo é aleatório (não o nome original enviado) —
    evita colisão entre despesas e não expõe nenhum dado do nome
    original do arquivo da pessoa.
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
