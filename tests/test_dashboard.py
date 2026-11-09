"""Tests for the dashboard API. PayPal calls are mocked: no network, no real money."""
import asyncio
import inspect
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mandate import dashboard, gateway, service, store
from mandate.payouts import PayoutError
from mandate.seed import seed

EMAIL = "supplier.billing@example.test"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", EMAIL)
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(dashboard, "DB_PATH", db_file)
    conn = store.connect(db_file)
    seed(conn)
    conn.close()
    return TestClient(dashboard.app)


@pytest.fixture
def payout():
    with patch.object(service, "send_payout",
                      return_value={"batch_id": "BATCH-1", "status": "PENDING"}) as mock:
        yield mock


def post(client, path):
    return client.post(path)


def test_index_page_is_served_with_labels_and_pinned_ag_grid(client):
    html = client.get("/").text
    assert "Simulated attack, no AI involved" in html
    assert "Simulated compromised agent" in html
    assert "ag-grid-community@32.3.3" in html  # exact version, not "latest"


def test_mandate_summary(client):
    m = client.get("/api/mandate").json()
    assert (m["currency"], m["per_payment_cap"], m["approval_threshold"]) == ("USD", "200", "100")
    assert m["remaining_budget"] == "1000"
    assert "@" not in str(m)


def test_demo_legitimate_is_paid(client, payout):
    r = post(client, "/api/demo/legitimate").json()
    assert (r["decision"], r["status"]) == ("ALLOW", "PAID")
    payout.assert_called_once()
    assert client.get("/api/mandate").json()["remaining_budget"] == "975.00"


def test_demo_changed_payee_and_large_are_held(client, payout):
    assert post(client, "/api/demo/changed_payee").json()["decision"] == "HOLD"
    assert post(client, "/api/demo/large").json()["decision"] == "HOLD"
    payout.assert_not_called()
    held = [p for p in client.get("/api/payments").json() if p["status"] == "HELD"]
    assert len(held) == 2


def test_demo_uses_fresh_invoice_ids(client, payout):
    a = post(client, "/api/demo/large").json()["payment_id"]
    b = post(client, "/api/demo/large").json()["payment_id"]
    invoices = {p["invoice_id"] for p in client.get("/api/payments").json()}
    assert a != b and len(invoices) == 2


def test_unknown_demo_or_attack_name_is_404(client, payout):
    assert post(client, "/api/demo/nope").status_code == 404
    assert post(client, "/api/attack/nope").status_code == 404


def test_all_three_attacks_are_not_allowed(client, payout):
    results = {name: post(client, f"/api/attack/{name}").json() for name in ("injected", "changed_payee", "over_cap")}
    assert results["injected"]["decision"] == "BLOCK"
    assert results["changed_payee"]["decision"] == "HOLD"
    assert results["over_cap"]["decision"] == "BLOCK"
    assert all(r["decision"] != "ALLOW" for r in results.values())
    payout.assert_not_called()
    assert store.spent_so_far(store.connect(dashboard.DB_PATH)) == 0


def test_attack_result_has_reasons_and_hides_emails(client, payout):
    r = post(client, "/api/attack/changed_payee").json()
    assert any("payee_change" in x for x in r["reasons"])
    assert "attacker@example.test" not in str(r) and EMAIL not in str(r)


def test_approve_pays_a_held_payment(client, payout):
    pid = post(client, "/api/demo/large").json()["payment_id"]
    r = post(client, f"/api/payments/{pid}/approve").json()
    assert (r["decision"], r["status"]) == ("APPROVE", "PAID")
    payout.assert_called_once()
    payments = client.get("/api/payments").json()
    assert [p["status"] for p in payments if p["id"] == pid] == ["PAID"]
    # cannot be approved twice
    assert post(client, f"/api/payments/{pid}/approve").status_code == 409


def test_reject_does_not_pay(client, payout):
    pid = post(client, "/api/demo/large").json()["payment_id"]
    r = post(client, f"/api/payments/{pid}/reject").json()
    assert r["status"] == "REJECTED"
    payout.assert_not_called()
    assert post(client, f"/api/payments/{pid}/reject").status_code == 409


def test_approve_or_reject_unknown_payment_is_409(client, payout):
    assert post(client, "/api/payments/999/approve").status_code == 409
    assert post(client, "/api/payments/999/reject").status_code == 409


def test_payments_and_audit_mask_emails(client, payout):
    post(client, "/api/demo/legitimate")
    post(client, "/api/attack/changed_payee")
    payments = client.get("/api/payments")
    audit = client.get("/api/audit")
    for text in (payments.text, audit.text):
        assert EMAIL not in text and "attacker@example.test" not in text
    assert "***" in payments.text
    rows = audit.json()
    assert rows[0]["decision"] == "HOLD" and isinstance(rows[0]["reasons"], list)  # newest first
    assert isinstance(rows[0]["checks"], dict)


def test_refresh_updates_pending_payouts(client, payout):
    post(client, "/api/demo/legitimate")  # PAID with PayPal status PENDING
    with patch.object(dashboard, "get_payout_status", return_value="SUCCESS") as status:
        r = post(client, "/api/refresh").json()
    status.assert_called_once_with("BATCH-1")
    assert r == {"checked": 1, "updated": 1, "failed": 0}
    assert client.get("/api/payments").json()[0]["paypal_status"] == "SUCCESS"
    # nothing pending any more, so a second refresh checks nothing
    with patch.object(dashboard, "get_payout_status") as status:
        assert post(client, "/api/refresh").json()["checked"] == 0
    status.assert_not_called()


def test_refresh_survives_a_paypal_error(client, payout):
    post(client, "/api/demo/legitimate")
    with patch.object(dashboard, "get_payout_status", side_effect=PayoutError("HTTP 500")):
        r = post(client, "/api/refresh").json()
    assert r == {"checked": 1, "updated": 0, "failed": 1}
    assert client.get("/api/payments").json()[0]["paypal_status"] == "PENDING"


def own(client, supplier_id="acme", amount="25.00"):
    return client.post("/api/request", json={"supplier_id": supplier_id, "amount": amount})


def test_page_has_the_own_request_form(client):
    html = client.get("/").text
    assert "Try your own request" in html and 'id="own-supplier"' in html and 'id="own-amount"' in html


def test_suppliers_list_has_names_and_no_emails(client):
    suppliers = client.get("/api/suppliers").json()
    assert {s["supplier_id"] for s in suppliers} == {"acme", "northwind", "globex"}
    assert all(set(s) == {"supplier_id", "name"} for s in suppliers)
    assert "@" not in str(suppliers)


def test_own_request_allowed_pays_the_email_on_file(client, payout):
    r = own(client, "northwind", "25.00").json()
    assert (r["decision"], r["status"]) == ("ALLOW", "PAID")
    assert payout.call_args.args[0] == EMAIL  # the payee is fixed: the address on file for the supplier
    assert EMAIL not in str(r)


def test_own_request_above_threshold_is_held(client, payout):
    r = own(client, "acme", "150.00").json()
    assert (r["decision"], r["status"]) == ("HOLD", "HELD")
    payout.assert_not_called()
    assert len([p for p in client.get("/api/payments").json() if p["status"] == "HELD"]) == 1


def test_own_request_over_the_cap_is_blocked(client, payout):
    r = own(client, "globex", "250.00").json()
    assert r["decision"] == "BLOCK" and any("per_payment_cap" in x for x in r["reasons"])
    payout.assert_not_called()


def test_own_request_zero_or_negative_is_blocked_by_the_rules(client, payout):
    assert own(client, amount="0").json()["decision"] == "BLOCK"
    assert own(client, amount="-5").json()["decision"] == "BLOCK"
    payout.assert_not_called()


def test_own_request_uses_fresh_invoice_ids_and_is_logged(client, payout):
    own(client, amount="150.00")
    own(client, amount="150.00")
    invoices = {p["invoice_id"] for p in client.get("/api/payments").json()}
    assert len(invoices) == 2 and all(i.startswith("OWN-") for i in invoices)
    assert len(client.get("/api/audit").json()) == 2


@pytest.mark.parametrize("bad", ["abc", "", "NaN", "Infinity", "10.123", "99999999999"])
def test_own_request_bad_amount_is_422_and_nothing_is_recorded(client, payout, bad):
    assert own(client, amount=bad).status_code == 422
    payout.assert_not_called()
    assert client.get("/api/audit").json() == []


def test_own_request_unknown_supplier_is_404_and_extra_fields_cannot_set_the_payee(client, payout):
    assert own(client, supplier_id="shadyco").status_code == 404
    r = client.post("/api/request", json={"supplier_id": "acme", "amount": "25.00",
                                          "payee_email": "attacker@example.test"})
    assert r.json()["decision"] == "ALLOW"
    assert payout.call_args.args[0] == EMAIL  # the extra field was ignored


def test_reset_clears_payments_and_audit_and_restores_budget(client, payout):
    post(client, "/api/demo/legitimate")
    post(client, "/api/demo/large")
    assert client.get("/api/mandate").json()["remaining_budget"] == "975.00"

    assert post(client, "/api/reset").json() == {"reset": True}
    assert client.get("/api/payments").json() == []
    assert client.get("/api/audit").json() == []
    assert client.get("/api/mandate").json()["remaining_budget"] == "1000"
    # the demo works again after a reset
    assert post(client, "/api/demo/large").json()["decision"] == "HOLD"


def test_gateway_still_exposes_exactly_two_tools_and_no_approval():
    names = {t.name for t in asyncio.run(gateway.mcp.list_tools())}
    assert names == {"request_payment", "get_mandate"}
    source = inspect.getsource(gateway)
    assert "approve_payment" not in source and "reject_payment" not in source
    assert "dashboard" not in source
