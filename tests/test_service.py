"""Tests for store + service. The PayPal payout is mocked: no network, no real money."""
from decimal import Decimal as D
from unittest.mock import patch

import pytest

from mandate import service, store
from mandate.payouts import PayoutError
from mandate.policy import PaymentRequest
from mandate.seed import seed

EMAIL = "demo@example.test"


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", EMAIL)
    c = store.connect(":memory:")
    seed(c)
    return c


@pytest.fixture
def payout():
    with patch.object(service, "send_payout",
                      return_value={"batch_id": "BATCH-1", "status": "PENDING"}) as mock:
        yield mock


def req(invoice_id="INV-1", supplier_id="acme", email=EMAIL, amount="25.00"):
    return PaymentRequest(invoice_id, supplier_id, email, D(amount), "USD")


def test_seed_uses_personal_email_for_every_supplier(conn):
    m = store.load_mandate(conn)
    assert len(m.suppliers) == 3
    assert {s.payee_email for s in m.suppliers.values()} == {EMAIL}
    assert (m.total_budget, m.per_payment_cap, m.approval_threshold) == (D("1000"), D("200"), D("100"))


def test_allow_pays_and_records(conn, payout):
    r = service.handle_payment_request(conn, req())
    assert (r.decision, r.status) == ("ALLOW", "PAID")
    payout.assert_called_once()
    p = store.get_payment(conn, r.payment_id)
    assert p["status"] == "PAID" and p["paypal_batch_id"] == "BATCH-1" and p["paypal_status"] == "PENDING"
    log = store.list_audit_log(conn)
    assert len(log) == 1 and log[0]["decision"] == "ALLOW" and "BATCH-1" in log[0]["outcome"]


def test_failed_payout_is_recorded_as_failed(conn):
    with patch.object(service, "send_payout", side_effect=PayoutError("HTTP 400: nope")):
        r = service.handle_payment_request(conn, req())
    assert r.status == "FAILED" and "nope" in r.outcome
    assert store.spent_so_far(conn) == 0  # a failed payout does not count as spent


def test_hold_queues_and_does_not_pay(conn, payout):
    r = service.handle_payment_request(conn, req(email="other@example.test"))
    assert (r.decision, r.status) == ("HOLD", "HELD")
    payout.assert_not_called()
    assert [p["id"] for p in store.pending_approvals(conn)] == [r.payment_id]


def test_block_logs_and_does_not_pay(conn, payout):
    r = service.handle_payment_request(conn, req(supplier_id="shadyco"))
    assert (r.decision, r.status) == ("BLOCK", "BLOCKED")
    payout.assert_not_called()
    log = store.list_audit_log(conn)
    assert log[0]["decision"] == "BLOCK" and "allow-list" in log[0]["reasons"]
    assert "payee_allow_list" in log[0]["checks"]


def test_duplicate_invoice_is_blocked(conn, payout):
    service.handle_payment_request(conn, req())
    r = service.handle_payment_request(conn, req())
    assert r.status == "BLOCKED" and payout.call_count == 1


def test_approve_sends_payout_and_marks_paid(conn, payout):
    held = service.handle_payment_request(conn, req(amount="150.00"))
    assert held.status == "HELD"
    result = service.approve_payment(conn, held.payment_id)
    assert result.status == "PAID"
    payout.assert_called_once()
    assert store.get_payment(conn, held.payment_id)["status"] == "PAID"
    assert store.pending_approvals(conn) == []
    assert store.list_audit_log(conn)[-1]["decision"] == "APPROVE"


def test_reject_does_not_pay(conn, payout):
    held = service.handle_payment_request(conn, req(amount="150.00"))
    result = service.reject_payment(conn, held.payment_id)
    assert result.status == "REJECTED"
    payout.assert_not_called()
    assert store.get_payment(conn, held.payment_id)["status"] == "REJECTED"
    assert store.list_audit_log(conn)[-1]["decision"] == "REJECT"


def test_cannot_approve_twice_or_approve_non_held(conn, payout):
    held = service.handle_payment_request(conn, req(amount="150.00"))
    service.approve_payment(conn, held.payment_id)
    with pytest.raises(ValueError):
        service.approve_payment(conn, held.payment_id)
    paid = service.handle_payment_request(conn, req(invoice_id="INV-2"))
    with pytest.raises(ValueError):
        service.reject_payment(conn, paid.payment_id)


def test_budget_tracking_blocks_when_exceeded(conn, payout):
    # budget is 1000 and cap 200: pay 90 eleven times (990), then 90 more must be blocked
    for i in range(11):
        assert service.handle_payment_request(conn, req(invoice_id=f"INV-{i}", amount="90")).status == "PAID"
    assert store.spent_so_far(conn) == D("990")
    r = service.handle_payment_request(conn, req(invoice_id="INV-X", amount="90"))
    assert r.status == "BLOCKED" and any("budget" in x for x in r.reasons)
    assert store.paid_invoice_ids(conn) == {f"INV-{i}" for i in range(11)}


def test_held_and_blocked_payments_do_not_count_as_spent(conn, payout):
    service.handle_payment_request(conn, req(invoice_id="INV-H", amount="150.00"))
    service.handle_payment_request(conn, req(invoice_id="INV-B", amount="250.00"))
    assert store.spent_so_far(conn) == 0
