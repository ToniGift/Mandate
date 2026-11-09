"""Probe which PayPal sandbox APIs work for this account: Payouts, Invoicing, Orders.

Run from the repo root:  python scripts/probe_paypal.py
Creates a 1.00 USD payout, a draft invoice and an order in the SANDBOX only.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from mandate.paypal_client import PayPalClient


def error_message(resp) -> str:
    """Pull PayPal's error text out of a failed response."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    text = body.get("message") or body.get("error_description") or body.get("name") or ""
    details = body.get("details") or []
    if details:
        text += " | " + "; ".join(d.get("issue") or d.get("description", "") for d in details)
    return text or str(body)[:300]


def try_call(name: str, client: PayPalClient, method: str, path: str, payload: dict) -> bool:
    resp = client.request(method, path, payload)
    ok = resp.status_code in (200, 201)
    print(f"{name}: HTTP {resp.status_code} {'OK' if ok else 'FAILED'}")
    if not ok:
        print(f"  error: {error_message(resp)}")
    return ok


def main() -> None:
    load_dotenv()
    client = PayPalClient()

    client.get_token()
    print(f"token OK, expires in {client.token_seconds_left()} seconds")

    personal_email = os.environ.get("PAYPAL_PERSONAL_EMAIL", "")
    run_id = str(int(time.time()))  # makes each probe run unique
    results = {}

    # a. Payout of 1.00 USD
    if personal_email:
        results["Payouts"] = try_call("Payout", client, "POST", "/v1/payments/payouts", {
            "sender_batch_header": {
                "sender_batch_id": f"probe-{run_id}",
                "email_subject": "Mandate probe payout",
            },
            "items": [{
                "recipient_type": "EMAIL",
                "receiver": personal_email,
                "amount": {"value": "1.00", "currency": "USD"},
                "sender_item_id": f"probe-item-{run_id}",
            }],
        })
    else:
        print("Payout: skipped, PAYPAL_PERSONAL_EMAIL is not set")
        results["Payouts"] = False

    # b. Draft invoice (the invoicer is the account behind the app, so no email is needed)
    results["Invoicing"] = try_call("Invoice", client, "POST", "/v2/invoicing/invoices", {
        "detail": {
            "currency_code": "USD",
            "invoice_number": f"PROBE-{run_id}",
        },
        "primary_recipients": [{
            "billing_info": {"email_address": personal_email or "buyer@example.com"},
        }],
        "items": [{
            "name": "Mandate probe item",
            "quantity": "1",
            "unit_amount": {"currency_code": "USD", "value": "1.00"},
        }],
    })

    # c. Order
    results["Orders"] = try_call("Order", client, "POST", "/v2/checkout/orders", {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": "USD", "value": "1.00"}}],
    })

    worked = [name for name, ok in results.items() if ok]
    failed = [name for name, ok in results.items() if not ok]
    print(f"\nSUMMARY: worked: {', '.join(worked) or 'none'} | failed: {', '.join(failed) or 'none'}")


if __name__ == "__main__":
    main()
