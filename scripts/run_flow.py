"""Run the whole flow once: seed the database, send six requests through Mandate,
approve the held 150.00 payment.

Run from the repo root:  python scripts/run_flow.py
WARNING: this makes REAL payments in the PayPal SANDBOX (25.00 and 150.00 USD)
and wipes mandate.db when it seeds.
"""
import sys
import time
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mandate import service, store
from mandate.policy import PaymentRequest
from mandate.seed import seed


def show(label: str, result: service.Result) -> None:
    reason = result.reasons[0]
    print(f"{label:<28}{result.decision:<9}{result.status:<9}{reason}")
    for extra in result.reasons[1:]:
        print(f"{'':<46}{extra}")
    print(f"{'':<46}-> {result.outcome}\n")


def main() -> None:
    try:
        conn = store.connect()
    except store.SchemaMismatch as err:  # an old mandate.db: say what to do, not a traceback
        print(err, file=sys.stderr)
        raise SystemExit(1)
    mandate = seed(conn)
    supplier_email = mandate.suppliers["acme"].payee_email
    run = str(int(time.time()))  # fresh invoice ids on every run

    first_id = f"INV-{run}-1"
    requests_to_send = [
        ("Legitimate 25.00", PaymentRequest(first_id, "acme", supplier_email, D("25.00"), "USD", "Office paper")),
        ("Changed payee", PaymentRequest(f"INV-{run}-2", "acme", "new-account@example.test", D("25.00"), "USD")),
        ("Above threshold 150.00", PaymentRequest(f"INV-{run}-3", "northwind", supplier_email, D("150.00"), "USD")),
        ("Over cap 250.00", PaymentRequest(f"INV-{run}-4", "globex", supplier_email, D("250.00"), "USD")),
        ("Unknown supplier", PaymentRequest(f"INV-{run}-5", "shadyco", "x@example.test", D("25.00"), "USD")),
        ("Repeat of first invoice", PaymentRequest(first_id, "acme", supplier_email, D("25.00"), "USD")),
    ]

    print(f"{'REQUEST':<28}{'DECISION':<9}{'STATUS':<9}REASON")
    print("-" * 100)
    held_150 = None
    for label, req in requests_to_send:
        result = service.handle_payment_request(conn, req)
        show(label, result)
        if label.startswith("Above threshold"):
            held_150 = result.payment_id

    print("Human approves the held 150.00 payment:")
    show("Approve 150.00", service.approve_payment(conn, held_150))

    print(f"Spent so far: {store.spent_so_far(conn)} of {mandate.total_budget} {mandate.currency}")
    print(f"Audit log rows: {len(store.list_audit_log(conn))}")


if __name__ == "__main__":
    main()
