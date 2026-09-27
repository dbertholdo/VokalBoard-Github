"""P4 — Match-Rechnungen: rascunho criptografado, opcional, por Match.

Único módulo autorizado a fazer SELECT/INSERT/UPDATE/DELETE direto em
`invoice_match_drafts` (mesmo princípio do app/match_evaluations.py pro
P3.F: uma tabela sensível, um único ponto de acesso).

Fluxo (decisões já registradas em AI_CHANGELOG.md/PLANO_EXECUTIVO):
- issuer_user_id = quem presta o serviço (job_matches.artist_user_id) —
  emite a Rechnung. contractor_user_id = quem contratou/publicou o
  anúncio (job_matches.contractor_user_id) — revisa e confirma.
- Qualquer lado pode iniciar: `request_invoice()` (só um "toque" pedindo
  que o emissor preencha) ou `save_issuer_form()` (o emissor já manda o
  formulário preenchido direto).
- Só existe UM rascunho aberto por Match (`uq_open_invoice_match_draft`
  no schema) — pedir de novo com um já aberto não faz nada.
- Ao confirmar (`confirm_and_send`), o PDF é gerado em memória, mandado
  por e-mail pras duas partes, e o rascunho é APAGADO — nada fica
  gravado, nem o número de série (esse é só um contador em
  invoice_number_sequences, sem conteúdo).
"""
from datetime import date, datetime, timezone

from sqlalchemy import text

from app.database import engine, fetch_all, fetch_one
from app.email import send_email
from app.email_localization import (
    match_invoice_confirmed_email,
    match_invoice_ready_for_review_email,
    match_invoice_requested_email,
)
from app.invoice_deadlines import can_request_match_invoice, match_draft_expiry
from app.invoice_pdf import InvoiceDocument, InvoiceValidationError, render_invoice_pdf
from app.invoice_security import decrypt_invoice_draft, encrypt_invoice_draft
from app.invoice_service import InvoiceCreditUnavailable, consume_invoice_generation, record_invoice_number

# Same names as app.invoice_pdf.InvoiceDocument's fields on purpose — the
# route resolves the tax radios (app.invoice_tax_presets.resolve_tax) into
# plain tax_rate/tax_note BEFORE calling save_issuer_form, so the encrypted
# payload here can build an InvoiceDocument with no extra mapping step.
FORM_FIELDS = (
    "number", "issue_date", "service_date", "issuer_name", "issuer_address", "issuer_tax_id",
    "recipient_name", "recipient_address", "service_description", "net_amount", "currency",
    "tax_rate", "tax_note", "payment_terms", "iban", "bic",
    "expense_travel_amount", "expense_lodging_amount",
)
# Stored with the (encrypted) draft only so the form can re-open with the same
# tax choice; not an InvoiceDocument field.
EXTRA_FIELDS = ("tax_preset",)


class InvoiceDraftNotFound(ValueError):
    pass


class InvoiceDraftNotAllowed(ValueError):
    """Wrong participant, wrong status, or the request window is closed."""


def get_drafts(match_ids: list[int]) -> dict[int, dict]:
    """get_draft() for a whole page of Matches in one query (CLAUDE.md §4)."""
    if not match_ids:
        return {}
    rows = fetch_all(
        """
        SELECT id, match_id, requested_by_user_id, issuer_user_id, contractor_user_id,
               status, expires_at, created_at, updated_at
        FROM invoice_match_drafts
        WHERE match_id = ANY(:ids) AND status IN ('awaiting_issuer', 'awaiting_contractor')
        """,
        {"ids": list(match_ids)},
    )
    return {r["match_id"]: dict(r) for r in rows}


def get_draft(match_id: int) -> dict | None:
    row = fetch_one(
        """
        SELECT id, match_id, requested_by_user_id, issuer_user_id, contractor_user_id,
               status, expires_at, created_at, updated_at
        FROM invoice_match_drafts
        WHERE match_id = :match_id AND status IN ('awaiting_issuer', 'awaiting_contractor')
        """,
        {"match_id": match_id},
    )
    return dict(row) if row else None


def request_invoice(match_id: int, requester_id: int, issuer_id: int, contractor_id: int, event_date, today: date | None = None) -> str:
    """Either side "pings" the other. Returns 'created' or 'already_open'."""
    if requester_id not in (issuer_id, contractor_id):
        raise InvoiceDraftNotAllowed("Only a Match participant can request an invoice")
    today = today or date.today()
    existing = get_draft(match_id)
    if existing:
        return "already_open"
    if not can_request_match_invoice(event_date, today):
        raise InvoiceDraftNotAllowed("The 7-day request window for this Match has closed")
    now = datetime.now(timezone.utc)
    # A placeholder is stored (empty form) waiting for the ISSUER to fill
    # it in — encrypted_payload can never be NULL, so an empty dict is
    # encrypted rather than leaving the column unset.
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO invoice_match_drafts
                    (match_id, requested_by_user_id, issuer_user_id, contractor_user_id,
                     encrypted_payload, status, expires_at)
                VALUES (:match_id, :requester_id, :issuer_id, :contractor_id, :payload, 'awaiting_issuer', :expires_at)
                """
            ),
            {
                "match_id": match_id, "requester_id": requester_id, "issuer_id": issuer_id,
                "contractor_id": contractor_id, "payload": encrypt_invoice_draft({}),
                "expires_at": match_draft_expiry(event_date, now),
            },
        )
    return "created"


def save_issuer_form(match_id: int, issuer_id: int, contractor_id: int, payload: dict, event_date, today: date | None = None) -> None:
    """The issuer submits (or revises) the filled form. Creates the draft
    if none is open yet, or updates the existing one — the expiry never
    shortens/extends on an edit once set."""
    today = today or date.today()
    now = datetime.now(timezone.utc)
    existing = get_draft(match_id)
    encrypted = encrypt_invoice_draft({key: payload.get(key, "") for key in FORM_FIELDS + EXTRA_FIELDS})
    with engine.begin() as conn:
        if existing:
            if issuer_id != existing["issuer_user_id"]:
                raise InvoiceDraftNotAllowed("Only the issuer can fill this Match's invoice")
            conn.execute(
                text(
                    """
                    UPDATE invoice_match_drafts
                    SET encrypted_payload = :payload, status = 'awaiting_contractor', updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"payload": encrypted, "id": existing["id"]},
            )
        else:
            if not can_request_match_invoice(event_date, today):
                raise InvoiceDraftNotAllowed("The 7-day request window for this Match has closed")
            conn.execute(
                text(
                    """
                    INSERT INTO invoice_match_drafts
                        (match_id, requested_by_user_id, issuer_user_id, contractor_user_id,
                         encrypted_payload, status, expires_at)
                    VALUES (:match_id, :issuer_id, :issuer_id, :contractor_id, :payload, 'awaiting_contractor', :expires_at)
                    """
                ),
                {
                    "match_id": match_id, "issuer_id": issuer_id, "contractor_id": contractor_id,
                    "payload": encrypted, "expires_at": match_draft_expiry(event_date, now),
                },
            )


def get_form_for_issuer(match_id: int, issuer_id: int) -> dict:
    """Decrypted payload for the issuer to re-open/edit their own draft —
    empty dict if there's only a request placeholder or no draft yet."""
    draft = get_draft(match_id)
    if not draft or draft["issuer_user_id"] != issuer_id:
        return {}
    row = fetch_one("SELECT encrypted_payload FROM invoice_match_drafts WHERE id = :id", {"id": draft["id"]})
    payload = decrypt_invoice_draft(row["encrypted_payload"])
    return {key: payload.get(key, "") for key in FORM_FIELDS + EXTRA_FIELDS}


def get_preview(match_id: int, viewer_id: int) -> dict | None:
    """Either participant can preview the CURRENT draft content — used
    by the contractor to review before confirming, and by the issuer to
    see their own submission. Returns None if there's no filled draft
    yet (only a request placeholder, or nothing at all)."""
    draft = get_draft(match_id)
    if not draft or viewer_id not in (draft["issuer_user_id"], draft["contractor_user_id"]):
        return None
    if draft["status"] != "awaiting_contractor":
        return None
    row = fetch_one("SELECT encrypted_payload FROM invoice_match_drafts WHERE id = :id", {"id": draft["id"]})
    payload = decrypt_invoice_draft(row["encrypted_payload"])
    if not payload.get("number"):
        return None
    return {key: payload.get(key, "") for key in FORM_FIELDS}


def cancel_draft(match_id: int, canceling_user_id: int) -> None:
    draft = get_draft(match_id)
    if not draft or canceling_user_id not in (draft["issuer_user_id"], draft["contractor_user_id"]):
        return
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM invoice_match_drafts WHERE id = :id"), {"id": draft["id"]})


def count_pending_actions(user_id: int) -> int:
    """Etapa 3 do P4 (18/09/2026) — badge de navegação: rascunhos onde é
    a vez desta pessoa agir agora. O Daniel pediu que o número conte
    "ambos" (pedido novo recebido + rascunho aguardando minha ação) —
    as duas coisas colapsam numa só contagem naturalmente: um pedido
    recém-criado já fica em 'awaiting_issuer' esperando o emissor, o que
    já é simultaneamente "chegou um pedido novo" E "está na minha mão"
    pra quem é o emissor."""
    row = fetch_one(
        """
        SELECT count(*) AS n FROM invoice_match_drafts
        WHERE (status = 'awaiting_issuer' AND issuer_user_id = :id)
           OR (status = 'awaiting_contractor' AND contractor_user_id = :id)
        """,
        {"id": user_id},
    )
    return row["n"] if row else 0


def list_invoice_matches_for_user(user_id: int, today: date | None = None) -> list[dict]:
    """Matches deste usuário com algo relevante de Rechnung pra mostrar
    na aba "Match-Rechnungen" de /rechnungmaker (Etapa 3) — rascunho
    aberto, ainda dentro da janela pra pedir, ou já enviada. Uma única
    query com LEFT JOIN (nunca um SELECT por Match dentro de um loop —
    CLAUDE.md Seção 4.2). Só o status do rascunho é lido aqui, nunca o
    conteúdo criptografado (isso continua exclusivo de get_preview/
    get_form_for_issuer, chamados só quando a pessoa abre aquele Match
    especificamente)."""
    today = today or date.today()
    rows = fetch_all(
        """
        SELECT m.id AS match_id, m.artist_user_id, m.contractor_user_id, m.invoice_sent_at,
               COALESCE(m.listing_snapshot->>'title', l.title) AS title,
               COALESCE((m.listing_snapshot->>'event_date')::date, l.event_date) AS event_date,
               d.status AS draft_status
        FROM job_matches m
        LEFT JOIN listings l ON l.id = m.listing_id
        LEFT JOIN invoice_match_drafts d
               ON d.match_id = m.id AND d.status IN ('awaiting_issuer', 'awaiting_contractor')
        WHERE (m.artist_user_id = :user_id OR m.contractor_user_id = :user_id)
          AND m.status != 'cancelled'
        ORDER BY m.created_at DESC
        LIMIT 100
        """,
        {"user_id": user_id},
    )
    result = []
    for row in rows:
        has_draft = row["draft_status"] is not None
        can_request = (
            not has_draft
            and not row["invoice_sent_at"]
            and can_request_match_invoice(row["event_date"], today)
        )
        if not has_draft and not can_request and not row["invoice_sent_at"]:
            continue  # nada de Rechnung pra mostrar nesse Match — não polui a lista.
        result.append({
            "match_id": row["match_id"],
            "title": row["title"],
            "is_issuer": row["artist_user_id"] == user_id,
            "invoice_sent_at": row["invoice_sent_at"],
            "draft_status": row["draft_status"],
            "can_request_invoice": can_request,
        })
    return result


def notify_requested(recipient_email: str, recipient_name: str, recipient_lang: str, requester_first_name: str, production_title: str, url: str) -> None:
    subject, html = match_invoice_requested_email(recipient_lang, recipient_name, requester_first_name, production_title, url)
    send_email(recipient_email, subject, html)


def notify_ready_for_review(recipient_email: str, recipient_name: str, recipient_lang: str, issuer_first_name: str, production_title: str, url: str) -> None:
    subject, html = match_invoice_ready_for_review_email(recipient_lang, recipient_name, issuer_first_name, production_title, url)
    send_email(recipient_email, subject, html)


def confirm_and_send(
    match_id: int, confirming_user_id: int, today: date | None = None,
    *, issuer_email: str, issuer_name: str, issuer_lang: str | None,
    contractor_email: str, contractor_name: str, contractor_lang: str | None,
    production_title: str,
) -> None:
    """Only the contractor (who reviews) can confirm. Builds the PDF in
    memory, e-mails BOTH sides (PDF attached, never stored), consumes one
    invoice generation from the ISSUER's franchise/credits, records the
    issuer's invoice number, marks job_matches.invoice_sent_at, and
    deletes the draft — nothing about this Rechnung is retained."""
    today = today or date.today()
    draft = get_draft(match_id)
    if not draft or confirming_user_id != draft["contractor_user_id"]:
        raise InvoiceDraftNotAllowed("Only the contractor can confirm this Match's invoice")
    if draft["status"] != "awaiting_contractor":
        raise InvoiceDraftNotAllowed("This draft is not ready for confirmation yet")

    row = fetch_one("SELECT encrypted_payload FROM invoice_match_drafts WHERE id = :id", {"id": draft["id"]})
    payload = decrypt_invoice_draft(row["encrypted_payload"])
    try:
        document = InvoiceDocument(**{key: payload.get(key, "") for key in FORM_FIELDS})
        pdf_bytes = render_invoice_pdf(document)
    except (InvoiceValidationError, TypeError) as exc:
        raise InvoiceDraftNotAllowed("The stored draft is incomplete or invalid") from exc

    filename = f"Rechnung-{document.number}.pdf"
    issuer_subject, issuer_html = match_invoice_confirmed_email(issuer_lang, issuer_name, production_title)
    contractor_subject, contractor_html = match_invoice_confirmed_email(contractor_lang, contractor_name, production_title)
    send_email(issuer_email, issuer_subject, issuer_html, attachments=[{"filename": filename, "content": pdf_bytes}])
    send_email(contractor_email, contractor_subject, contractor_html, attachments=[{"filename": filename, "content": pdf_bytes}])

    try:
        consume_invoice_generation(draft["issuer_user_id"], today)
    except InvoiceCreditUnavailable:
        # The issuer already used their franchise/credits elsewhere between
        # filling the form and the contractor confirming — the PDF was
        # still delivered (already promised, already sent); we simply
        # don't double-charge or block delivery over an accounting edge
        # case that reaching this point means was already accepted.
        pass
    record_invoice_number(draft["issuer_user_id"], document.number)
    with engine.begin() as conn:
        conn.execute(text("UPDATE job_matches SET invoice_sent_at = now() WHERE id = :id"), {"id": match_id})
        conn.execute(text("DELETE FROM invoice_match_drafts WHERE id = :id"), {"id": draft["id"]})
