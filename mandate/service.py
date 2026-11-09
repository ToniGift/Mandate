"""Glue code: policy check, then pay / hold / block, and always write the audit log."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal

import requests

from mandate import store
from mandate.payouts import PayoutError, send_payout
from mandate.policy import Decision, PaymentRequest, evaluate


@dataclass
class Result:
    payment_id: int
    decision: str       # what the policy said: ALLOW, HOLD or BLOCK
    reasons: list[str]
    status: str         # payment status after handling: PAID, HELD, BLOCKED or FAILED
    outcome: str        # plain-words summary of what happened


def _pay(conn, payment_id, payee_email, amount, currency, invoice_id, memo) -> tuple[str, str]:
    """Send the payout. Returns (payment status, outcome text)."""
    try:
        payout = send_payout(payee_email, amount, currency, invoice_id, memo)
    except (PayoutError, requests.RequestException) as err:
        store.update_payment(conn, payment_id, "FAILED")
        return "FAILED", f"payout failed: {err}"
    store.update_payment(conn, payment_id, "PAID", payout["batch_id"], payout["status"])
    return "PAID", f"payout accepted, batch {payout['batch_id']}, PayPal status {payout['status']}"


def handle_payment_request(conn: sqlite3.Connection, req: PaymentRequest) -> Result:
    mandate = store.load_mandate(conn)
    verdict = evaluate(req, mandate, store.spent_so_far(conn), store.paid_invoice_ids(conn))

    if verdict.decision is Decision.ALLOW:
        payment_id = store.add_payment(conn, req, "FAILED")  # becomes PAID only if the payout works
        status, outcome = _pay(conn, payment_id, req.payee_email, req.amount, req.currency,
                               req.invoice_id, req.memo)
    elif verdict.decision is Decision.HOLD:
        payment_id = store.add_payment(conn, req, "HELD")
        status, outcome = "HELD", "waiting for human approval"
    else:
        payment_id = store.add_payment(conn, req, "BLOCKED")
        status, outcome = "BLOCKED", "nothing was sent"

    store.add_audit(conn, req.invoice_id, verdict.decision.value, verdict.reasons, verdict.checks, outcome)
    return Result(payment_id, verdict.decision.value, verdict.reasons, status, outcome)


def approve_payment(conn: sqlite3.Connection, payment_id: int) -> Result:
    """A human approved a held payment: send the payout."""
    p = _get_held(conn, payment_id)
    status, outcome = _pay(conn, payment_id, p["payee_email"], Decimal(p["amount"]), p["currency"],
                           p["invoice_id"], p["memo"])
    outcome = "approved by human, " + outcome
    store.add_audit(conn, p["invoice_id"], "APPROVE", ["human approved the held payment"], {}, outcome)
    return Result(payment_id, "APPROVE", ["human approved the held payment"], status, outcome)


def reject_payment(conn: sqlite3.Connection, payment_id: int) -> Result:
    """A human rejected a held payment: nothing is sent."""
    p = _get_held(conn, payment_id)
    store.update_payment(conn, payment_id, "REJECTED")
    outcome = "rejected by human, nothing was sent"
    store.add_audit(conn, p["invoice_id"], "REJECT", ["human rejected the held payment"], {}, outcome)
    return Result(payment_id, "REJECT", ["human rejected the held payment"], "REJECTED", outcome)


def _get_held(conn: sqlite3.Connection, payment_id: int) -> sqlite3.Row:
    p = store.get_payment(conn, payment_id)
    if p is None or p["status"] != "HELD":
        raise ValueError(f"payment {payment_id} is not waiting for approval")
    return p
