"""SQLite storage: mandate, suppliers, payments and the audit log."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from mandate.policy import MandateConfig, PaymentRequest, Supplier

DB_FILE = "mandate.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mandate (
    id INTEGER PRIMARY KEY CHECK (id = 1),   -- only one mandate
    currency TEXT, total_budget TEXT, per_payment_cap TEXT,
    approval_threshold TEXT, expires_at TEXT
);
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id TEXT PRIMARY KEY, name TEXT, payee_email TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT, supplier_id TEXT, payee_email TEXT,
    amount TEXT, currency TEXT, memo TEXT,
    status TEXT,              -- PAID, HELD, BLOCKED, REJECTED or FAILED
    paypal_batch_id TEXT, paypal_status TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT, invoice_id TEXT, decision TEXT,
    reasons TEXT, checks TEXT, outcome TEXT
);
"""


def connect(path: str = DB_FILE) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- mandate and suppliers -------------------------------------------------

def clear_all(conn: sqlite3.Connection) -> None:
    for table in ("mandate", "suppliers", "payments", "audit_log"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def save_mandate(conn: sqlite3.Connection, m: MandateConfig) -> None:
    conn.execute("DELETE FROM mandate")
    conn.execute("DELETE FROM suppliers")
    conn.execute("INSERT INTO mandate VALUES (1, ?, ?, ?, ?, ?)",
                 (m.currency, str(m.total_budget), str(m.per_payment_cap),
                  str(m.approval_threshold), m.expires_at.isoformat()))
    for s in m.suppliers.values():
        conn.execute("INSERT INTO suppliers VALUES (?, ?, ?)", (s.supplier_id, s.name, s.payee_email))
    conn.commit()


def load_mandate(conn: sqlite3.Connection) -> MandateConfig:
    row = conn.execute("SELECT * FROM mandate WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("No mandate in the database. Run the seed first.")
    suppliers = {r["supplier_id"]: Supplier(r["supplier_id"], r["name"], r["payee_email"])
                 for r in conn.execute("SELECT * FROM suppliers")}
    return MandateConfig(
        currency=row["currency"],
        total_budget=Decimal(row["total_budget"]),
        per_payment_cap=Decimal(row["per_payment_cap"]),
        approval_threshold=Decimal(row["approval_threshold"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        suppliers=suppliers,
    )


# ---- payments --------------------------------------------------------------

def add_payment(conn: sqlite3.Connection, req: PaymentRequest, status: str) -> int:
    cur = conn.execute(
        "INSERT INTO payments (invoice_id, supplier_id, payee_email, amount, currency, memo, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (req.invoice_id, req.supplier_id, req.payee_email, str(req.amount), req.currency,
         req.memo, status, _now()))
    conn.commit()
    return cur.lastrowid


def update_payment(conn: sqlite3.Connection, payment_id: int, status: str,
                   batch_id: str | None = None, paypal_status: str | None = None) -> None:
    conn.execute("UPDATE payments SET status = ?, paypal_batch_id = ?, paypal_status = ? WHERE id = ?",
                 (status, batch_id, paypal_status, payment_id))
    conn.commit()


def get_payment(conn: sqlite3.Connection, payment_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()


def spent_so_far(conn: sqlite3.Connection) -> Decimal:
    rows = conn.execute("SELECT amount FROM payments WHERE status = 'PAID'")
    return sum((Decimal(r["amount"]) for r in rows), Decimal("0"))


def paid_invoice_ids(conn: sqlite3.Connection) -> set[str]:
    return {r["invoice_id"] for r in conn.execute("SELECT invoice_id FROM payments WHERE status = 'PAID'")}


def pending_approvals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM payments WHERE status = 'HELD' ORDER BY id").fetchall()


# ---- audit log -------------------------------------------------------------

def add_audit(conn: sqlite3.Connection, invoice_id: str, decision: str,
              reasons: list[str], checks: dict[str, str], outcome: str) -> None:
    conn.execute("INSERT INTO audit_log (time, invoice_id, decision, reasons, checks, outcome)"
                 " VALUES (?, ?, ?, ?, ?, ?)",
                 (_now(), invoice_id, decision, json.dumps(reasons), json.dumps(checks), outcome))
    conn.commit()


def list_audit_log(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
