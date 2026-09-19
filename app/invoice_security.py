"""Proteção dos rascunhos temporários de Rechnung por Match.

O formulário pode conter IBAN, endereço e identificadores fiscais. Por isso o
conteúdo é cifrado antes de chegar ao PostgreSQL. A chave vem somente do
ambiente de execução: não há geração automática nem valor-padrão, para que uma
configuração incompleta falhe de forma segura em vez de gravar dados sensíveis
sem proteção.
"""
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class InvoiceDraftSecurityError(RuntimeError):
    """A chave ausente, inválida ou um rascunho corrompido nunca é exposto."""


def _fernet() -> Fernet:
    key = os.getenv("INVOICE_DRAFT_ENCRYPTION_KEY")
    if not key:
        raise InvoiceDraftSecurityError("Invoice draft encryption is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise InvoiceDraftSecurityError("Invoice draft encryption configuration is invalid") from exc


def encrypt_invoice_draft(payload: dict[str, Any]) -> bytes:
    """Serialize and encrypt a validated form without logging any value."""
    try:
        plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvoiceDraftSecurityError("Invoice draft cannot be serialized") from exc
    return _fernet().encrypt(plaintext)


def decrypt_invoice_draft(encrypted_payload: bytes) -> dict[str, Any]:
    """Decrypt a draft only after the Match authorization check in the route.

    Accepts a `memoryview` too: psycopg2/SQLAlchemy return BYTEA columns as
    `memoryview`, which `Fernet.decrypt` doesn't accept directly."""
    try:
        decoded = _fernet().decrypt(bytes(encrypted_payload))
        payload = json.loads(decoded.decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvoiceDraftSecurityError("Invoice draft cannot be decrypted") from exc
    if not isinstance(payload, dict):
        raise InvoiceDraftSecurityError("Invoice draft has an invalid shape")
    return payload
