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


# ---- texts that depend on the mode (offline demo or real PayPal sandbox) ---------------------------------

REAL_NOTE = "The legitimate invoice makes a real PayPal sandbox payment."
OFFLINE_NOTE = "Offline demo: this payment is simulated, PayPal is not contacted."
REAL_FOOTER = "Payments run on the PayPal sandbox, so no real money moves."
OFFLINE_FOOTER = "Offline demo: payouts are simulated and PayPal is not contacted. No real money moves."


def test_the_page_has_both_versions_of_each_mode_dependent_text_and_shows_neither_until_the_mode_is_known(client):
    html = client.get("/").text
    for text, mode in ((REAL_NOTE, "real"), (OFFLINE_NOTE, "offline"), (REAL_FOOTER, "real"), (OFFLINE_FOOTER, "offline")):
        assert f'<span data-mode="{mode}" hidden>{text}</span>' in html, text
    # the script shows the matching version, from the same field that drives the banner
    assert 'el.dataset.mode !== (offline ? "offline" : "real")' in html
    assert "applyMode(!!m.fake_payouts)" in html
    assert "Payouts here are simulated, so there is nothing to undo at PayPal." in html
    assert "Payments already sent to the PayPal sandbox are not undone." in html  # real mode text is unchanged


def test_no_real_paypal_claim_is_left_unconditional_in_the_page(client):
    """Every sentence that says money really goes through PayPal sits inside a data-mode="real" element."""
    html = client.get("/").text
    for claim in (REAL_NOTE, REAL_FOOTER):
        assert html.count(claim) == 1  # said once, and only in its real-mode element
        assert html.split(claim)[0].endswith('<span data-mode="real" hidden>'), claim


def test_real_mode_outcome_text_is_unchanged(client, payout):
    r = post(client, "/api/demo/legitimate").json()
    assert r["outcome"] == "payout accepted, batch BATCH-1, PayPal status PENDING"
    audit = client.get("/api/audit").json()
    assert audit[0]["outcome"] == "payout accepted, batch BATCH-1, PayPal status PENDING"
    assert client.get("/api/mandate").json()["fake_payouts"] is False


def test_offline_mode_outcome_text_says_simulated_not_paypal(client, monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")

    def no_network(*args, **kwargs):
        raise AssertionError("offline mode must not contact PayPal")

    with patch("mandate.payouts.PayPalClient", no_network), patch("requests.post", no_network), \
            patch("requests.request", no_network):
        paid = post(client, "/api/demo/legitimate").json()
        held = post(client, "/api/demo/large").json()
        approved = post(client, f"/api/payments/{held['payment_id']}/approve").json()
    for r in (paid, approved):
        assert "simulated payout accepted, batch FAKE-" in r["outcome"]
        assert "payout status SUCCESS" in r["outcome"] and "PayPal" not in r["outcome"]
    outcomes = [row["outcome"] for row in client.get("/api/audit").json()]
    assert any("simulated payout accepted" in o for o in outcomes)
    assert not any("PayPal status" in o for o in outcomes if "FAKE-" in o)


def test_a_real_payout_is_never_reworded_even_in_offline_mode(client, monkeypatch, payout):
    post(client, "/api/demo/legitimate")  # a real-mode payment (the payout is mocked), batch BATCH-1
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    assert client.get("/api/audit").json()[0]["outcome"] == "payout accepted, batch BATCH-1, PayPal status PENDING"


# ---- offline demo mode ----------------------------------------------------------------------------

def test_real_mode_is_the_default_and_the_api_says_so(client):
    assert client.get("/api/mandate").json()["fake_payouts"] is False


def test_offline_mode_shows_in_the_api_and_the_page_has_the_banner(client, monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    assert client.get("/api/mandate").json()["fake_payouts"] is True
    html = client.get("/").text
    assert "Offline demo: payouts are simulated, PayPal is not contacted." in html
    assert 'id="demo-banner"' in html and "m.fake_payouts" in html  # shown or hidden from this API field


def test_offline_mode_pays_and_approves_with_no_mock_and_no_network(client, monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    for name in ("PAYPAL_PERSONAL_EMAIL", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("offline mode must not contact PayPal")

    with patch("mandate.payouts.PayPalClient", no_network), patch("requests.post", no_network), \
            patch("requests.request", no_network):
        paid = post(client, "/api/demo/legitimate").json()
        held = post(client, "/api/demo/large").json()
        approved = post(client, f"/api/payments/{held['payment_id']}/approve").json()
        refreshed = post(client, "/api/refresh").json()
        reset = post(client, "/api/reset").json()

    assert (paid["decision"], paid["status"]) == ("ALLOW", "PAID") and "FAKE-" in paid["outcome"]
    assert approved["status"] == "PAID" and "FAKE-" in approved["outcome"]
    assert refreshed == {"checked": 0, "updated": 0, "failed": 0}  # simulated payouts are already complete
    assert reset == {"reset": True}


def test_gateway_still_exposes_exactly_two_tools_and_no_approval():
    names = {t.name for t in asyncio.run(gateway.mcp.list_tools())}
    assert names == {"request_payment", "get_mandate"}
    source = inspect.getsource(gateway)
    assert "approve_payment" not in source and "reject_payment" not in source
    assert "dashboard" not in source
