import os

import pytest
from cryptography.fernet import Fernet

from app.invoice_security import (
    InvoiceDraftSecurityError,
    decrypt_invoice_draft,
    encrypt_invoice_draft,
)


def test_match_invoice_draft_is_encrypted_and_round_trips(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    payload = {"iban": "DE89370400440532013000", "amount": "120.00"}

    encrypted = encrypt_invoice_draft(payload)

    assert payload["iban"].encode("utf-8") not in encrypted
    assert decrypt_invoice_draft(encrypted) == payload


def test_match_invoice_draft_fails_closed_without_a_key(monkeypatch):
    monkeypatch.delenv("INVOICE_DRAFT_ENCRYPTION_KEY", raising=False)

    with pytest.raises(InvoiceDraftSecurityError):
        encrypt_invoice_draft({"iban": "DE89370400440532013000"})


def test_match_invoice_draft_rejects_tampering(monkeypatch):
    monkeypatch.setenv("INVOICE_DRAFT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    encrypted = bytearray(encrypt_invoice_draft({"amount": "120.00"}))
    encrypted[-1] ^= 1

    with pytest.raises(InvoiceDraftSecurityError):
        decrypt_invoice_draft(bytes(encrypted))
