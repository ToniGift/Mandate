"""Attack test: a fully compromised agent tries to get money out of Mandate.

Run from the repo root:  python scripts/run_attacks.py

Safe by design:
- it calls handle_payment_request in mandate/service.py directly, the same function the gateway uses
- every attack gets a throwaway in-memory database, so mandate.db is never touched
- PayPal is replaced by a fake payout function that only records its calls: no network, no .env
Exit code 0 means every attack was stopped or held as expected, 1 means something failed.
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mandate import service, store
from mandate.policy import MandateConfig, PaymentRequest, Supplier

# The test's own small business. It does not use the demo seed values.
BUDGET, CAP, THRESHOLD = D("300"), D("100"), D("50")
ALPHA_EMAIL = "billing@alpha.example.test"
BETA_EMAIL = "ar@beta.example.test"


def make_mandate(**changes) -> MandateConfig:
    base = dict(
        currency="USD", total_budget=BUDGET, per_payment_cap=CAP, approval_threshold=THRESHOLD,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        suppliers={"alpha": Supplier("alpha", "Alpha Supplies", ALPHA_EMAIL),
                   "beta": Supplier("beta", "Beta Packaging", BETA_EMAIL)},
    )
    base.update(changes)
    return MandateConfig(**base)


def fresh_db(mandate: MandateConfig | None = None):
    """A new throwaway database that lives only in memory."""
    conn = store.connect(":memory:")
    store.save_mandate(conn, mandate or make_mandate())
    return conn


class Bench:
    """The fake PayPal. It records every payout and counts payouts that should never happen."""

    def __init__(self) -> None:
        self.payouts: list[dict] = []
        self.bad_payouts = 0  # payouts sent for a request that was supposed to be blocked or held

    def fake_payout(self, payee_email, amount, currency, invoice_id, note):
        self.payouts.append({"payee_email": payee_email, "amount": D(amount), "currency": currency,
                             "invoice_id": invoice_id})
        return {"batch_id": f"FAKE-{len(self.payouts)}", "status": "SUCCESS"}

    def ask(self, conn, expect, invoice_id, supplier_id="alpha", payee_email=ALPHA_EMAIL,
            amount="20", currency="USD"):
        """Send one request through Mandate. `expect` is what Mandate should answer."""
        before = len(self.payouts)
        result = service.handle_payment_request(
            conn, PaymentRequest(invoice_id, supplier_id, payee_email, D(amount), currency, "attack test"))
        if expect != "ALLOW":
            self.bad_payouts += len(self.payouts) - before
        return result


# ---- the attacks. Each returns (what happened, did it pass, first reason) ----

def injected_instruction(b):
    r = b.ask(fresh_db(), "BLOCK", "ATK1", "unknown-supplier", "attacker@example.test", "5000")
    return r.decision, r.decision == "BLOCK", r.reasons[0]


def changed_payee(b):
    r = b.ask(fresh_db(), "HOLD", "ATK2", payee_email="attacker@example.test")
    return r.decision, r.decision == "HOLD", r.reasons[0]


def oversized(b):
    r = b.ask(fresh_db(), "BLOCK", "ATK3", amount="150")
    return r.decision, r.decision == "BLOCK", r.reasons[0]


def unknown_supplier(b):
    r = b.ask(fresh_db(), "BLOCK", "ATK4", "ghost-supplier", "ghost@example.test")
    return r.decision, r.decision == "BLOCK", r.reasons[0]


def duplicate_invoice(b):
    conn = fresh_db()
    first = b.ask(conn, "ALLOW", "ATK5")
    second = b.ask(conn, "BLOCK", "ATK5")
    passed = first.decision == "ALLOW" and second.decision == "BLOCK"
    return f"{first.decision}, then {second.decision}", passed, second.reasons[0]


def splitting(b):
    conn = fresh_db()
    step = D("40")  # under the approval threshold, so each payment alone looks harmless
    allowed = int(BUDGET // step)
    decisions = []
    for i in range(allowed + 1):
        r = b.ask(conn, "ALLOW" if i < allowed else "BLOCK", f"ATK6-{i}", amount=str(step))
        decisions.append(r.decision)
    passed = decisions == ["ALLOW"] * allowed + ["BLOCK"]
    return f"{decisions.count('ALLOW')} ALLOW, then {decisions[-1]}", passed, r.reasons[0]


def expired_mandate(b):
    expired = make_mandate(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    r = b.ask(fresh_db(expired), "BLOCK", "ATK7")
    return r.decision, r.decision == "BLOCK", r.reasons[0]


def wrong_currency(b):
    r = b.ask(fresh_db(), "BLOCK", "ATK8", currency="EUR")
    return r.decision, r.decision == "BLOCK", r.reasons[0]


def zero_and_negative(b):
    conn = fresh_db()
    zero = b.ask(conn, "BLOCK", "ATK9-zero", amount="0")
    negative = b.ask(conn, "BLOCK", "ATK9-negative", amount="-5")
    passed = zero.decision == "BLOCK" and negative.decision == "BLOCK"
    return f"{zero.decision}, {negative.decision}", passed, zero.reasons[0]


def large_then_reject(b):
    conn = fresh_db()
    start = len(b.payouts)
    held = b.ask(conn, "HOLD", "ATK10", amount="80")  # above the threshold, under the cap
    rejected = service.reject_payment(conn, held.payment_id)
    sent = len(b.payouts) - start
    b.bad_payouts += sent
    passed = held.decision == "HOLD" and rejected.status == "REJECTED" and sent == 0
    return f"{held.decision}, reject, {sent} payouts", passed, held.reasons[0]


def approved_by_a_person(b):
    conn = fresh_db()
    start = len(b.payouts)
    held = b.ask(conn, "HOLD", "ATK11", amount="80")
    approved = service.approve_payment(conn, held.payment_id)
    calls = b.payouts[start:]
    passed = (held.decision == "HOLD" and approved.status == "PAID" and len(calls) == 1
              and calls[0]["payee_email"] == ALPHA_EMAIL and calls[0]["amount"] == D("80"))
    return f"{held.decision}, approve, {len(calls)} payout to email on file", passed, held.reasons[0]


def inflated_amount(b):
    # a supplier that usually invoices up to 30. The request has the right supplier, the right payee and an
    # amount under the approval threshold (50), so no other rule fires. Only the typical amount does.
    suppliers = {"alpha": Supplier("alpha", "Alpha Supplies", ALPHA_EMAIL, typical_max=D("30")),
                 "beta": Supplier("beta", "Beta Packaging", BETA_EMAIL)}
    r = b.ask(fresh_db(make_mandate(suppliers=suppliers)), "HOLD", "ATK12", amount="45")
    passed = r.decision == "HOLD" and r.reasons[0].startswith("typical_amount:")
    return r.decision, passed, r.reasons[0]


ATTACKS = [
    ("Injected 5000 USD, unknown payee", "BLOCK", injected_instruction),
    ("Known supplier, changed payee", "HOLD", changed_payee),
    ("Payment over the per-payment cap", "BLOCK", oversized),
    ("Unknown supplier", "BLOCK", unknown_supplier),
    ("Same invoice paid twice", "2nd BLOCK", duplicate_invoice),
    ("Splitting into small payments", "last one BLOCK", splitting),
    ("Expired mandate", "BLOCK", expired_mandate),
    ("Wrong currency", "BLOCK", wrong_currency),
    ("Zero and negative amounts", "BLOCK, BLOCK", zero_and_negative),
    ("Large legitimate, then rejected", "HOLD, 0 payouts", large_then_reject),
    ("Held payment approved by a person", "HOLD, 1 payout", approved_by_a_person),
    ("Known supplier, correct payee, inflated amount", "HOLD", inflated_amount),
]


def run_attacks() -> tuple[list[dict], Bench]:
    """Run every attack against the fake PayPal. Returns the result rows and the fake."""
    bench = Bench()
    rows = []
    with patch.object(service, "send_payout", bench.fake_payout):
        for number, (name, expected, attack) in enumerate(ATTACKS, start=1):
            try:
                actual, passed, reason = attack(bench)
            except Exception as err:  # a crash is a failed attack, not a crashed script
                actual, passed, reason = f"ERROR {type(err).__name__}", False, "-"
            rows.append({"number": number, "name": name, "expected": expected,
                         "actual": actual, "passed": passed, "reason": reason})
    return rows, bench


def short(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


def print_report(rows: list[dict], bench: Bench) -> bool:
    """Print the table and the summary. Returns True if everything passed."""
    print(f"{'#':<3}{'Attack':<48}{'Expected':<16}{'Actual':<40}{'Result':<8}First reason")
    print("-" * 162)
    for r in rows:
        print(f"{r['number']:<3}{r['name']:<48}{r['expected']:<16}{short(r['actual'], 38):<40}"
              f"{'PASS' if r['passed'] else 'FAIL':<8}{short(r['reason'], 70)}")

    passed = sum(r["passed"] for r in rows)
    no_payouts = bench.bad_payouts == 0
    print()
    print(f"{'PASS' if no_payouts else 'FAIL'}  no payout was made for any BLOCK or HOLD case "
          f"(the fake PayPal saw {len(bench.payouts)} payouts in total, all for ALLOW or human approval)")
    print(f"{passed} of {len(rows)} attacks stopped or held as expected")
    print(f"payouts sent for blocked or held requests: {bench.bad_payouts}")
    return passed == len(rows) and no_payouts


def main() -> int:
    rows, bench = run_attacks()
    return 0 if print_report(rows, bench) else 1


if __name__ == "__main__":
    sys.exit(main())
