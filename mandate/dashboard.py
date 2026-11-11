"""Human dashboard: approval queue, payments, audit log.

Approve and reject exist ONLY here. The AI agent and the MCP gateway have no way to call them.
By default the dashboard listens on localhost only and reads the same SQLite database as the gateway.
On a public server (see mandate/hosting.py) it runs in offline demo mode and limits POST requests.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from mandate import service, store
from mandate.hosting import load_env_unless_public, public_mode
from mandate.payouts import PayoutError, fake_payouts_enabled, get_payout_status
from mandate.policy import PaymentRequest
from mandate.seed import seed

load_env_unless_public()

DB_PATH = store.DB_FILE
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Mandate dashboard")


# ---- abuse guard, only on a public server: limit POST requests per visitor per minute ----------
# A simple in-memory counter. It is a guard for a demo, not real security: a visitor who sends a
# fake X-Forwarded-For header can get around it.

POSTS_PER_MINUTE = 30
_recent_posts: dict[str, deque] = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")  # a proxy such as Render's puts the visitor here
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@app.middleware("http")
async def limit_posts(request: Request, call_next):
    if request.method == "POST" and public_mode():
        ip, now = client_ip(request), time.monotonic()
        recent = _recent_posts.setdefault(ip, deque())
        while recent and now - recent[0] > 60:
            recent.popleft()
        if len(recent) >= POSTS_PER_MINUTE:
            return JSONResponse(
                {"detail": f"Too many requests. This demo allows {POSTS_PER_MINUTE} actions per minute "
                           "per visitor. Please wait a minute and try again."},
                status_code=429, headers={"Retry-After": "60"})
        recent.append(now)
        if len(_recent_posts) > 5000:  # keep the memory use bounded
            for key in [k for k, q in _recent_posts.items() if not q or now - q[-1] > 60]:
                del _recent_posts[key]
    return await call_next(request)


@contextmanager
def db():
    """One short-lived database connection per request."""
    conn = store.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


# ---- hide the middle of email addresses (done on the server, so full emails never leave it) ----

_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+")


def _mask_match(match: re.Match) -> str:
    local, domain = match.group(0).split("@", 1)
    local = local[0] + "***" if len(local) <= 4 else local[:2] + "***" + local[-1]
    return f"{local}@{domain}"


def mask(text: str | None) -> str | None:
    return _EMAIL.sub(_mask_match, text) if text else text


def outcome_text(text: str | None) -> str | None:
    """A simulated payout (batch id FAKE-...) is described as simulated, never as a PayPal one.
    It goes by the batch id, so a real payout's text is never changed."""
    if text and "batch FAKE-" in text:
        text = text.replace("payout accepted", "simulated payout accepted").replace("PayPal status", "payout status")
    return mask(text)


def _result(r: service.Result) -> dict:
    out = asdict(r)
    out["reasons"] = [mask(x) for x in r.reasons]
    out["outcome"] = outcome_text(r.outcome)
    return out


# ---- read endpoints --------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/mandate")
def get_mandate():
    with db() as conn:
        try:
            m = store.load_mandate(conn)
        except RuntimeError as err:
            raise HTTPException(503, str(err))
        spent = store.spent_so_far(conn)
        return {
            "currency": m.currency,
            "total_budget": str(m.total_budget),
            "spent": str(spent),
            "remaining_budget": str(m.total_budget - spent),
            "per_payment_cap": str(m.per_payment_cap),
            "approval_threshold": str(m.approval_threshold),
            "expires_at": m.expires_at.isoformat(),
            "fake_payouts": fake_payouts_enabled(),  # True in offline demo mode (the page shows a banner)
        }


@app.get("/api/payments")
def list_payments():
    with db() as conn:
        rows = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchall()
    return [{**dict(r), "payee_email": mask(r["payee_email"])} for r in rows]


@app.get("/api/audit")
def list_audit():
    with db() as conn:
        rows = store.list_audit_log(conn)
    return [{
        "id": r["id"], "time": r["time"], "invoice_id": r["invoice_id"], "decision": r["decision"],
        "reasons": [mask(x) for x in json.loads(r["reasons"])],
        "checks": json.loads(r["checks"]),
        "outcome": outcome_text(r["outcome"]),
    } for r in reversed(rows)]


# ---- human decisions -------------------------------------------------------

@app.post("/api/payments/{payment_id}/approve")
def approve(payment_id: int):
    with db() as conn:
        try:
            return _result(service.approve_payment(conn, payment_id))
        except ValueError as err:
            raise HTTPException(409, str(err))


@app.post("/api/payments/{payment_id}/reject")
def reject(payment_id: int):
    with db() as conn:
        try:
            return _result(service.reject_payment(conn, payment_id))
        except ValueError as err:
            raise HTTPException(409, str(err))


# ---- canned requests (no LLM, no MCP: they call handle_payment_request directly) ----

# name -> (supplier_id, payee email or None for "the email on file", amount, memo)
DEMOS = {
    "legitimate": ("acme", None, "25.00", "Demo: legitimate invoice"),
    "changed_payee": ("acme", "new-account@example.test", "40.00", "Demo: payee changed"),
    "large": ("northwind", None, "150.00", "Demo: large invoice"),
}
ATTACKS = {
    "injected": ("unknown-supplier", "attacker@example.test", "5000", "Simulated attack: injected payment"),
    "changed_payee": ("acme", "attacker@example.test", "60.00", "Simulated attack: changed payee"),
    "over_cap": ("acme", None, "250.00", "Simulated attack: payment over the cap"),
}


def _fresh_id(prefix: str) -> str:
    """A new invoice id each time. The random tail keeps two requests in the same millisecond apart."""
    return f"{prefix}-{int(time.time() * 1000)}-{secrets.token_hex(2)}"


def _submit(table: dict, name: str, prefix: str) -> dict:
    if name not in table:
        raise HTTPException(404, f"unknown name '{name}'")
    supplier_id, email, amount, memo = table[name]
    with db() as conn:
        mandate = store.load_mandate(conn)
        if email is None:
            email = mandate.suppliers[supplier_id].payee_email
        req = PaymentRequest(
            invoice_id=_fresh_id(f"{prefix}-{name}"),  # fresh id every click
            supplier_id=supplier_id, payee_email=email, amount=Decimal(amount),
            currency=mandate.currency, memo=memo)
        return _result(service.handle_payment_request(conn, req))


@app.post("/api/demo/{name}")
def demo(name: str):
    return _submit(DEMOS, name, "DEMO")


@app.post("/api/attack/{name}")
def attack(name: str):
    """Simulated compromised agent: a hand-written bad request, no AI involved."""
    return _submit(ATTACKS, name, "ATTACK")


# ---- "Try your own request": pick a supplier and an amount ------------------

class OwnRequest(BaseModel):
    supplier_id: str
    amount: str


@app.get("/api/suppliers")
def list_suppliers():
    """Supplier ids and names for the dropdown. Never the payee emails."""
    with db() as conn:
        try:
            mandate = store.load_mandate(conn)
        except RuntimeError as err:
            raise HTTPException(503, str(err))
    return [{"supplier_id": s.supplier_id, "name": s.name} for s in mandate.suppliers.values()]


@app.post("/api/request")
def own_request(body: OwnRequest):
    """The user picks the supplier and the amount. The payee is always the address on file for that
    supplier. Like the other canned requests, this calls handle_payment_request directly: no LLM."""
    try:
        amount = Decimal(body.amount.strip())
        if not amount.is_finite() or abs(amount) > 1_000_000 or amount != amount.quantize(Decimal("0.01")):
            raise InvalidOperation
    except InvalidOperation:
        raise HTTPException(422, "amount must be a number with at most 2 decimal places")

    with db() as conn:
        try:
            mandate = store.load_mandate(conn)
        except RuntimeError as err:
            raise HTTPException(503, str(err))
        supplier = mandate.suppliers.get(body.supplier_id)
        if supplier is None:
            raise HTTPException(404, "unknown supplier")
        req = PaymentRequest(
            invoice_id=_fresh_id("OWN"),  # fresh id every time
            supplier_id=supplier.supplier_id, payee_email=supplier.payee_email, amount=amount,
            currency=mandate.currency, memo="Your own request")
        return _result(service.handle_payment_request(conn, req))


# ---- start the demo again --------------------------------------------------

@app.post("/api/reset")
def reset():
    """Delete all payments and the audit log and restore the demo mandate and budget.
    Payouts already sent to the PayPal sandbox are not undone."""
    with db() as conn:
        try:
            seed(conn)
        except RuntimeError as err:
            raise HTTPException(500, str(err))
    return {"reset": True}


# ---- payout status ---------------------------------------------------------

@app.post("/api/refresh")
def refresh():
    """For PAID payments whose payout is still PENDING, ask PayPal for the current status."""
    checked = updated = failed = 0
    with db() as conn:
        rows = conn.execute("SELECT * FROM payments WHERE status = 'PAID' AND paypal_status = 'PENDING'").fetchall()
        for p in rows:
            checked += 1
            try:
                new_status = get_payout_status(p["paypal_batch_id"])
            except (PayoutError, requests.RequestException):
                failed += 1
                continue
            if new_status != p["paypal_status"]:
                store.update_payment(conn, p["id"], "PAID", p["paypal_batch_id"], new_status)
                updated += 1
    return {"checked": checked, "updated": updated, "failed": failed}
