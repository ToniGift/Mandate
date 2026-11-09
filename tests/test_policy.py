from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from mandate.policy import Decision, MandateConfig, PaymentRequest, Supplier, evaluate

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def make_mandate(**kw):
    base = dict(
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
    base.update(kw)
    return MandateConfig(**base)


def req(**kw):
    base = dict(invoice_id="INV-1", supplier_id="acme", payee_email="billing@acme-supplies.test",
                amount=D("250"), currency="USD")
    base.update(kw)
    return PaymentRequest(**base)


def run(r, m=None, spent="0", paid=()):
    return evaluate(r, m or make_mandate(), D(spent), set(paid), now=NOW)


def test_legitimate_invoice_is_allowed():
    v = run(req())
    assert v.decision is Decision.ALLOW


def test_changed_payee_is_held_and_flagged():  # the BEC attack
    v = run(req(payee_email="billing@acme-suppl1es.test"))
    assert v.decision is Decision.HOLD
    assert v.checks["payee_change"] == "hold"
    assert any("changed" in r for r in v.reasons)


def test_unknown_supplier_is_blocked():
    assert run(req(supplier_id="mallory")).decision is Decision.BLOCK


def test_over_cap_is_blocked():
    assert run(req(amount=D("2500"))).decision is Decision.BLOCK


def test_above_threshold_is_held():
    v = run(req(amount=D("1500")))
    assert v.decision is Decision.HOLD
    assert v.checks["approval_threshold"] == "hold"


def test_splitting_attack_hits_budget():
    v = run(req(amount=D("900")), spent="4500")
    assert v.decision is Decision.BLOCK
    assert v.checks["budget"] == "block"


def test_expired_mandate_is_blocked():
    m = make_mandate(expires_at=NOW - timedelta(seconds=1))
    assert run(req(), m).decision is Decision.BLOCK


def test_duplicate_invoice_is_blocked():
    assert run(req(), paid={"INV-1"}).decision is Decision.BLOCK


def test_wrong_currency_and_non_positive_amounts_are_blocked():
    assert run(req(currency="EUR")).decision is Decision.BLOCK
    assert run(req(amount=D("0"))).decision is Decision.BLOCK
    assert run(req(amount=D("-5"))).decision is Decision.BLOCK


def test_block_beats_hold():
    v = run(req(payee_email="x@evil.test", amount=D("2500")))
    assert v.decision is Decision.BLOCK
    assert v.checks["payee_change"] == "hold" and v.checks["per_payment_cap"] == "block"


def test_payee_email_case_and_spaces_do_not_trigger_false_hold():
    assert run(req(payee_email="  Billing@Acme-Supplies.TEST ")).decision is Decision.ALLOW
