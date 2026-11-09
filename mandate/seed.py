"""Seed a small demo business. Small amounts, so the sandbox balance is never a problem."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dotenv import load_dotenv

from mandate import store
from mandate.policy import MandateConfig, Supplier


def seed(conn: sqlite3.Connection) -> MandateConfig:
    """Wipe the database and create the demo mandate and suppliers.

    Every supplier is paid at PAYPAL_PERSONAL_EMAIL, so all demo payments land in
    the developer's own sandbox personal account.
    """
    load_dotenv()
    email = os.environ.get("PAYPAL_PERSONAL_EMAIL", "")
    if not email:
        raise RuntimeError("PAYPAL_PERSONAL_EMAIL must be set in .env")

    mandate = MandateConfig(
        currency="USD",
        total_budget=Decimal("500"),
        per_payment_cap=Decimal("200"),
        approval_threshold=Decimal("100"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        suppliers={
            "acme": Supplier("acme", "Acme Office Supplies", email),
            "northwind": Supplier("northwind", "Northwind Packaging", email),
            "globex": Supplier("globex", "Globex Cleaning Services", email),
        },
    )
    store.clear_all(conn)
    store.save_mandate(conn, mandate)
    return mandate
