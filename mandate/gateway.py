"""MCP gateway: the only thing the AI agent can talk to.

The agent gets exactly two tools. It can ASK for a payment and read the mandate.
There is no tool to approve, reject or change anything: approval is for humans only.
"""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mandate import store
from mandate.policy import PaymentRequest
from mandate.service import handle_payment_request

load_dotenv()

mcp = FastMCP("mandate", host="127.0.0.1", port=int(os.environ.get("MANDATE_PORT", "8000")))

_conn = None  # opened on first use (tests put an in-memory database here)


def _get_conn():
    global _conn
    if _conn is None:
        _conn = store.connect()
    return _conn


# ---- input checking: bad input gives a clear error, never a crash ----------

def _text(name: str, value, max_len: int = 100) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty text value")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"{name} is too long (max {max_len} characters)")
    return value


def _to_amount(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("amount must be a number or a text number like '25.00'")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"amount '{value}' is not a valid number") from None
    if not amount.is_finite():
        raise ValueError("amount must be a finite number")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("amount can have at most 2 decimal places")
    if amount > Decimal("1000000"):
        raise ValueError("amount is unreasonably large")
    return amount


def _currency(value) -> str:
    code = _text("currency", value, 3).upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("currency must be a 3-letter code such as USD")
    return code


def _email(value) -> str:
    email = _text("payee_email", value, 254)
    if "@" not in email or " " in email:
        raise ValueError("payee_email must look like an email address")
    return email


# ---- the two tools ---------------------------------------------------------

def request_payment(invoice_id: str, supplier_id: str, payee_email: str,
                    amount: str | int | float, currency: str, memo: str = "") -> dict:
    """Ask Mandate to pay an invoice. Mandate decides ALLOW, HOLD (human must approve) or BLOCK."""
    req = PaymentRequest(
        invoice_id=_text("invoice_id", invoice_id),
        supplier_id=_text("supplier_id", supplier_id),
        payee_email=_email(payee_email),
        amount=_to_amount(amount),
        currency=_currency(currency),
        memo=memo.strip()[:200] if isinstance(memo, str) else "",
    )
    conn = _get_conn()
    result = handle_payment_request(conn, req)

    # Do not tell the agent which email is on file, or a supplier's usual maximum amount (a fooled agent
    # could repeat the email, or stay just under the limit). The full reasons stay in the audit log.
    generic = {
        "payee_change:": "payee_change: payee email does not match the one on file for this supplier",
        "typical_amount:": "typical_amount: amount is above the usual maximum for this supplier",
    }
    reasons = [next((text for prefix, text in generic.items() if r.startswith(prefix)), r) for r in result.reasons]
    return {
        "decision": result.decision,
        "status": result.status,
        "reasons": reasons,
        "paypal_batch_id": store.get_payment(conn, result.payment_id)["paypal_batch_id"],
    }


def get_mandate() -> dict:
    """Read-only summary of the mandate. Contains no payee emails."""
    conn = _get_conn()
    m = store.load_mandate(conn)
    return {
        "currency": m.currency,
        "remaining_budget": str(m.total_budget - store.spent_so_far(conn)),
        "per_payment_cap": str(m.per_payment_cap),
        "approval_threshold": str(m.approval_threshold),
        "expires_at": m.expires_at.isoformat(),
        "suppliers": [{"supplier_id": s.supplier_id, "name": s.name} for s in m.suppliers.values()],
    }


mcp.tool()(request_payment)
mcp.tool()(get_mandate)
