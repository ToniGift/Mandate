"""Send money with the PayPal Payouts API (sandbox)."""
from __future__ import annotations

import os
from decimal import Decimal

from mandate.paypal_client import PayPalClient

_client: PayPalClient | None = None
FAKE_PREFIX = "FAKE-"


class PayoutError(Exception):
    """PayPal refused the payout. The message is PayPal's error text (never a secret)."""


def fake_payouts_enabled() -> bool:
    """Offline demo mode. MANDATE_FAKE_PAYOUTS=1 simulates payouts and never contacts PayPal.
    The default is off, which means real PayPal sandbox payouts."""
    return os.environ.get("MANDATE_FAKE_PAYOUTS", "").strip().lower() in ("1", "true", "yes", "on")


def _get_client() -> PayPalClient:
    global _client
    if _client is None:
        _client = PayPalClient()
    return _client


def _error_text(resp) -> str:
    try:
        body = resp.json()
        text = body.get("message") or body.get("name") or ""
        issues = [d.get("issue", "") for d in body.get("details", [])]
        return f"HTTP {resp.status_code}: {text} {' '.join(issues)}".strip()
    except ValueError:
        return f"HTTP {resp.status_code}"


def send_payout(payee_email: str, amount: Decimal, currency: str, invoice_id: str, note: str,
                client: PayPalClient | None = None) -> dict:
    """Pay one invoice. Returns {"batch_id": ..., "status": ...}.

    The batch id is built from the invoice id. If the same invoice is sent twice,
    PayPal rejects the second request (duplicate batch id), so it cannot be paid twice.

    In offline demo mode nothing is sent: the result is simulated (no network, no credentials).
    """
    if fake_payouts_enabled():
        return {"batch_id": f"{FAKE_PREFIX}{invoice_id}", "status": "SUCCESS"}
    client = client or _get_client()
    resp = client.request("POST", "/v1/payments/payouts", {
        "sender_batch_header": {
            "sender_batch_id": f"mandate-{invoice_id}",
            "email_subject": "Payment from Mandate",
        },
        "items": [{
            "recipient_type": "EMAIL",
            "receiver": payee_email,
            "amount": {"value": f"{Decimal(amount):.2f}", "currency": currency},
            "note": note or f"Invoice {invoice_id}",
            "sender_item_id": invoice_id,
        }],
    })
    if resp.status_code != 201:  # 201 means PayPal accepted the batch
        raise PayoutError(_error_text(resp))
    header = resp.json()["batch_header"]
    return {"batch_id": header["payout_batch_id"], "status": header["batch_status"]}


def get_payout_status(batch_id: str, client: PayPalClient | None = None) -> str:
    if fake_payouts_enabled():
        if batch_id.startswith(FAKE_PREFIX):
            return "SUCCESS"
        raise PayoutError("offline demo mode: a real PayPal batch cannot be looked up")
    client = client or _get_client()
    resp = client.request("GET", f"/v1/payments/payouts/{batch_id}")
    if resp.status_code != 200:
        raise PayoutError(_error_text(resp))
    return resp.json()["batch_header"]["batch_status"]
