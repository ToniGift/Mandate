"""Deterministic policy engine. No LLM in here, on purpose.

The agent can be fooled by what it reads. This code cannot be talked out of its rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    HOLD = "HOLD"      # a human must approve first
    BLOCK = "BLOCK"    # rule broken, nothing is sent


_SEVERITY = {Decision.ALLOW: 0, Decision.HOLD: 1, Decision.BLOCK: 2}


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    name: str
    payee_email: str  # the PayPal account this supplier is known to be paid at


@dataclass(frozen=True)
class MandateConfig:
    currency: str
    total_budget: Decimal
    per_payment_cap: Decimal
    approval_threshold: Decimal
    expires_at: datetime
    suppliers: dict[str, Supplier] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentRequest:
    invoice_id: str
    supplier_id: str
    payee_email: str
    amount: Decimal
    currency: str
    memo: str = ""


@dataclass
class Verdict:
    decision: Decision
    reasons: list[str]
    checks: dict[str, str]  # check name -> "pass" | "hold" | "block"


def _norm(email: str) -> str:
    return email.strip().lower()


def evaluate(
    req: PaymentRequest,
    mandate: MandateConfig,
    spent_so_far: Decimal,
    paid_invoice_ids: set[str],
    now: datetime | None = None,
) -> Verdict:
    now = now or datetime.now(timezone.utc)
    checks: dict[str, str] = {}
    reasons: list[str] = []
    worst = Decision.ALLOW

    def record(name: str, outcome: Decision | None, reason: str = "") -> None:
        nonlocal worst
        if outcome is None:
            checks[name] = "pass"
            return
        checks[name] = outcome.value.lower()
        reasons.append(f"{name}: {reason}")
        if _SEVERITY[outcome] > _SEVERITY[worst]:
            worst = outcome

    # 1. expiry
    if now >= mandate.expires_at:
        record("expiry", Decision.BLOCK, "mandate has expired")
    else:
        record("expiry", None)

    # 2. amount must be positive and in the mandate currency
    if req.amount <= 0:
        record("amount_valid", Decision.BLOCK, "amount must be greater than zero")
    elif req.currency.upper() != mandate.currency.upper():
        record("amount_valid", Decision.BLOCK,
               f"currency {req.currency} does not match mandate currency {mandate.currency}")
    else:
        record("amount_valid", None)

    # 3. payee allow-list
    supplier = mandate.suppliers.get(req.supplier_id)
    if supplier is None:
        record("payee_allow_list", Decision.BLOCK, f"supplier '{req.supplier_id}' is not on the allow-list")
    else:
        record("payee_allow_list", None)

    # 4. payee change detection (known supplier, different payee account)
    if supplier is not None:
        if _norm(req.payee_email) != _norm(supplier.payee_email):
            record("payee_change", Decision.HOLD,
                   f"payee for {supplier.name} changed from {supplier.payee_email} to {req.payee_email}")
        else:
            record("payee_change", None)

    # 5. duplicate invoice
    if req.invoice_id in paid_invoice_ids:
        record("duplicate_invoice", Decision.BLOCK, f"invoice {req.invoice_id} was already paid")
    else:
        record("duplicate_invoice", None)

    # 6. per-payment cap
    if req.amount > mandate.per_payment_cap:
        record("per_payment_cap", Decision.BLOCK,
               f"{req.amount} exceeds per-payment cap {mandate.per_payment_cap}")
    else:
        record("per_payment_cap", None)

    # 7. cumulative budget (blocks splitting one big payment into many small ones)
    if spent_so_far + req.amount > mandate.total_budget:
        record("budget", Decision.BLOCK,
               f"{spent_so_far} already spent + {req.amount} exceeds budget {mandate.total_budget}")
    else:
        record("budget", None)

    # 8. human approval threshold
    if req.amount > mandate.approval_threshold:
        record("approval_threshold", Decision.HOLD,
               f"{req.amount} is above approval threshold {mandate.approval_threshold}")
    else:
        record("approval_threshold", None)

    if worst is Decision.ALLOW:
        reasons.append("all checks passed")
    return Verdict(decision=worst, reasons=reasons, checks=checks)
