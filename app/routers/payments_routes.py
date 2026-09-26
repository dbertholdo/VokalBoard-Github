"""
Stripe webhook (Notas v2 — N5). Thin by design: signature check + hand-off
to app/notas_purchase.py, where every event type is handled idempotently.
Returns 400 for a bad signature (Stripe won't retry) and lets unexpected
errors surface as 500 so Stripe retries later.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.notas_purchase import handle_event, verify_event

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = verify_event(payload, request.headers.get("stripe-signature", ""))
    except ValueError:
        return JSONResponse({"error": "invalid signature"}, status_code=400)
    return JSONResponse({"status": handle_event(event)})
