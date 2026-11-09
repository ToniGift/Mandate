"""Offline demo of the policy engine. No network, no PayPal.

Run from the repo root:  python scripts/demo_policy.py
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

# Let the script find the "mandate" package when run as a file.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mandate.policy import MandateConfig, PaymentRequest, Supplier, evaluate

NOW = datetime.now(timezone.utc)

# The sample mandate: what the business has allowed the agent to do.
MANDATE = MandateConfig(
    currency="USD",
    total_budget=D("5000"),
    per_payment_cap=D("2000"),
    approval_threshold=D("1000"),
    expires_at=NOW + timedelta(days=7),
    suppliers={
        "acme": Supplier("acme", "Acme Supplies", "billing@acme-supplies.test"),
        "northwind": Supplier("northwind", "Northwind Packaging", "ar@northwind.test"),
    },
)

ACME_EMAIL = "billing@acme-supplies.test"
ALREADY_PAID = {"INV-100"}  # invoices paid earlier

# (label, request, money spent so far)
SCENARIOS = [
    ("Legitimate invoice",
     PaymentRequest("INV-001", "acme", ACME_EMAIL, D("250"), "USD"), D("0")),
    ("Changed payee",
     PaymentRequest("INV-002", "acme", "pay-me@evil.test", D("250"), "USD"), D("0")),
    ("Unknown supplier",
     PaymentRequest("INV-003", "shadyco", "x@shady.test", D("250"), "USD"), D("0")),
    ("Oversized payment",
     PaymentRequest("INV-004", "acme", ACME_EMAIL, D("2500"), "USD"), D("0")),
    ("Above approval threshold",
     PaymentRequest("INV-005", "acme", ACME_EMAIL, D("1500"), "USD"), D("0")),
    ("Duplicate invoice",
     PaymentRequest("INV-100", "acme", ACME_EMAIL, D("250"), "USD"), D("0")),
    ("Breaks total budget",
     PaymentRequest("INV-006", "acme", ACME_EMAIL, D("250"), "USD"), D("4900")),
]


def main() -> None:
    print(f"Mandate: budget {MANDATE.total_budget}, cap {MANDATE.per_payment_cap}, "
          f"approval above {MANDATE.approval_threshold} {MANDATE.currency}\n")
    print(f"{'REQUEST':<26}{'AMOUNT':>8}  {'DECISION':<9}REASONS")
    print("-" * 100)
    for label, request, spent in SCENARIOS:
        verdict = evaluate(request, MANDATE, spent, ALREADY_PAID, now=NOW)
        first, *rest = verdict.reasons
        print(f"{label:<26}{request.amount:>8}  {verdict.decision.value:<9}{first}")
        for reason in rest:
            print(f"{'':<45}{reason}")
        print()


if __name__ == "__main__":
    main()
