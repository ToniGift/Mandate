"""Tests for the gateway tool functions. The payout is mocked: no network, no real money."""
import asyncio
from unittest.mock import patch

import pytest

from mandate import gateway, service, store
from mandate.seed import seed

EMAIL = "demo@example.test"


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", EMAIL)
    c = store.connect(":memory:")
    seed(c)
    monkeypatch.setattr(gateway, "_conn", c)
    return c


@pytest.fixture
def payout():
    with patch.object(service, "send_payout",
                      return_value={"batch_id": "BATCH-1", "status": "PENDING"}) as mock:
        yield mock


def pay(**kw):
    args = dict(invoice_id="INV-1", supplier_id="acme", payee_email=EMAIL, amount="25.00", currency="USD")
    args.update(kw)
    return gateway.request_payment(**args)


def test_only_two_tools_are_exposed():
    names = {t.name for t in asyncio.run(gateway.mcp.list_tools())}
    assert names == {"request_payment", "get_mandate"}


def test_allow_returns_batch_id(conn, payout):
    r = pay()
    assert (r["decision"], r["status"], r["paypal_batch_id"]) == ("ALLOW", "PAID", "BATCH-1")
    payout.assert_called_once()


def test_hold_for_changed_payee_hides_the_email_on_file(conn, payout):
    r = pay(payee_email="other@example.test")
    assert (r["decision"], r["status"], r["paypal_batch_id"]) == ("HOLD", "HELD", None)
    payout.assert_not_called()
    assert EMAIL not in str(r)
    # the audit log still has the full reason
    assert EMAIL in store.list_audit_log(conn)[0]["reasons"]


def test_block_for_unknown_supplier(conn, payout):
    r = pay(supplier_id="shadyco")
    assert (r["decision"], r["status"]) == ("BLOCK", "BLOCKED")
    payout.assert_not_called()


def test_amount_accepts_number_and_text(conn, payout):
    assert pay(invoice_id="A", amount=25)["decision"] == "ALLOW"
    assert pay(invoice_id="B", amount=25.5)["decision"] == "ALLOW"
    assert pay(invoice_id="C", amount="25.50")["decision"] == "ALLOW"


@pytest.mark.parametrize("bad", [
    ("amount", "abc"), ("amount", "NaN"), ("amount", "Infinity"), ("amount", "10.123"),
    ("amount", True), ("amount", None), ("amount", ""), ("amount", [1]),
    ("currency", ""), ("currency", "US"), ("currency", "USDX"), ("currency", "12$"), ("currency", None),
    ("invoice_id", ""), ("invoice_id", "   "), ("invoice_id", None), ("invoice_id", "x" * 101),
    ("payee_email", "not-an-email"), ("payee_email", ""), ("payee_email", None),
    ("supplier_id", ""),
])
def test_bad_input_gives_clear_error_and_pays_nothing(conn, payout, bad):
    field, value = bad
    with pytest.raises(ValueError):
        pay(**{field: value})
    payout.assert_not_called()
    assert store.list_audit_log(conn) == []  # rejected before it reached the policy engine


def test_zero_and_negative_amounts_are_blocked_by_policy(conn, payout):
    assert pay(invoice_id="Z", amount="0")["decision"] == "BLOCK"
    assert pay(invoice_id="N", amount="-5")["decision"] == "BLOCK"
    payout.assert_not_called()


def test_get_mandate_has_no_emails_and_tracks_budget(conn, payout):
    before = gateway.get_mandate()
    assert before["remaining_budget"] == "500"
    assert before["currency"] == "USD" and before["per_payment_cap"] == "200"
    assert before["approval_threshold"] == "100"
    assert {s["supplier_id"] for s in before["suppliers"]} == {"acme", "northwind", "globex"}
    assert "@" not in str(before)

    pay()  # pays 25.00
    assert gateway.get_mandate()["remaining_budget"] == "475.00"
