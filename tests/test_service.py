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
    # budget is 1000, cap 200, and Acme's usual maximum is 60: pay 60 sixteen times (960), then 60 more is blocked
    for i in range(16):
        assert service.handle_payment_request(conn, req(invoice_id=f"INV-{i}", amount="60")).status == "PAID"
    assert store.spent_so_far(conn) == D("960")
    r = service.handle_payment_request(conn, req(invoice_id="INV-X", amount="60"))
    assert r.status == "BLOCKED" and any("budget" in x for x in r.reasons)
    assert store.paid_invoice_ids(conn) == {f"INV-{i}" for i in range(16)}


def test_held_and_blocked_payments_do_not_count_as_spent(conn, payout):
    service.handle_payment_request(conn, req(invoice_id="INV-H", amount="150.00"))
    service.handle_payment_request(conn, req(invoice_id="INV-B", amount="250.00"))
    assert store.spent_so_far(conn) == 0


# ---- offline demo mode (MANDATE_FAKE_PAYOUTS=1): the real send_payout runs, but it is simulated ----

@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    for name in ("PAYPAL_PERSONAL_EMAIL", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)  # no PayPal values of any kind

    def no_network(*args, **kwargs):
        raise AssertionError("offline mode must not contact PayPal")

    with patch("mandate.hosting.load_dotenv"), patch("mandate.payouts.PayPalClient", no_network), \
            patch("requests.post", no_network), patch("requests.request", no_network):  # load_dotenv: ignore a real .env
        yield


def test_offline_mode_seed_needs_no_paypal_email(offline):
    c = store.connect(":memory:")
    m = seed(c)
    assert {s.payee_email for s in m.suppliers.values()} == {"demo-owner@example.test"}


def test_real_mode_seed_still_requires_the_email(monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "0")
    monkeypatch.delenv("PAYPAL_PERSONAL_EMAIL", raising=False)
    with patch("mandate.hosting.load_dotenv"):  # do not read a real .env
        with pytest.raises(RuntimeError, match="PAYPAL_PERSONAL_EMAIL"):
            seed(store.connect(":memory:"))


def test_offline_mode_full_flow_with_the_real_payout_function(offline):
    c = store.connect(":memory:")
    seed(c)
    paid = service.handle_payment_request(c, req(email="demo-owner@example.test"))
    assert (paid.decision, paid.status) == ("ALLOW", "PAID")
    p = store.get_payment(c, paid.payment_id)
    assert p["paypal_batch_id"] == "FAKE-INV-1" and p["paypal_status"] == "SUCCESS"
    assert "FAKE-INV-1" in store.list_audit_log(c)[0]["outcome"]

    held = service.handle_payment_request(c, req("INV-2", amount="150.00", email="demo-owner@example.test"))
    assert held.status == "HELD"
    approved = service.approve_payment(c, held.payment_id)
    assert approved.status == "PAID"
    assert store.get_payment(c, held.payment_id)["paypal_batch_id"] == "FAKE-INV-2"
    assert store.spent_so_far(c) == D("175.00")

    blocked = service.handle_payment_request(c, req("INV-3", amount="250.00", email="demo-owner@example.test"))
    assert blocked.status == "BLOCKED"  # the rules are the same in offline mode
