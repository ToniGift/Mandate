"""Tests for the typical_amount rule: a known supplier, the right payee, but more than that supplier
usually invoices. The payout is mocked everywhere: no network, no real money."""
import asyncio
import importlib.util
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mandate import dashboard, gateway, service, store
from mandate.policy import Decision, MandateConfig, PaymentRequest, Supplier, evaluate
from mandate.seed import seed

ROOT = Path(__file__).resolve().parent.parent
EMAIL = "supplier.billing@example.test"
NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- the rule itself ----------------------------------------------------------------------------

def mandate(typical_max=D("60"), **changes):
    base = dict(
        currency="USD", total_budget=D("1000"), per_payment_cap=D("200"), approval_threshold=D("100"),
        expires_at=NOW + timedelta(days=7),
        suppliers={"acme": Supplier("acme", "Acme Supplies", "billing@acme.test", typical_max)},
    )
    base.update(changes)
    return MandateConfig(**base)


def ask(amount, m=None, **changes):
    args = dict(invoice_id="INV-1", supplier_id="acme", payee_email="billing@acme.test", amount=D(amount), currency="USD")
    args.update(changes)
    return evaluate(PaymentRequest(**args), m or mandate(), D("0"), set(), now=NOW)


def test_the_supplier_field_is_optional_and_last():
    s = Supplier("acme", "Acme", "a@x.test")           # old three-argument form still works
    assert s.typical_max is None
    assert Supplier("acme", "Acme", "a@x.test", D("60")).typical_max == D("60")


def test_an_amount_above_the_usual_maximum_is_held_with_a_clear_reason():
    v = ask("95")
    assert v.decision is Decision.HOLD
    assert v.checks["typical_amount"] == "hold"
    assert v.reasons == ["typical_amount: amount 95 is above the usual maximum 60 for Acme Supplies"]
    # no other check fired: the right payee, under the threshold, under the cap
    assert [k for k, o in v.checks.items() if o != "pass"] == ["typical_amount"]


def test_an_amount_at_the_usual_maximum_passes():
    for amount in ("60", "60.00", "59.99", "1"):
        v = ask(amount)
        assert v.decision is Decision.ALLOW and v.checks["typical_amount"] == "pass", amount


def test_no_usual_maximum_means_no_effect():
    for amount in ("1", "60", "95", "100", "150", "200", "250"):
        with_none = ask(amount, mandate(typical_max=None))
        assert with_none.checks["typical_amount"] == "pass"
        # the same request against a supplier made the old way, without the field at all
        old_way = mandate(suppliers={"acme": Supplier("acme", "Acme Supplies", "billing@acme.test")})
        before = ask(amount, old_way)
        assert (with_none.decision, with_none.reasons) == (before.decision, before.reasons), amount


def test_block_still_beats_hold():
    v = ask("250")  # over the cap (200) and above the usual maximum
    assert v.decision is Decision.BLOCK
    assert v.checks["per_payment_cap"] == "block" and v.checks["typical_amount"] == "hold"


def test_it_combines_with_other_holds_and_an_unknown_supplier_does_not_crash():
    both = ask("95", payee_email="other@acme.test")
    assert both.decision is Decision.HOLD and both.checks["payee_change"] == "hold" and both.checks["typical_amount"] == "hold"
    unknown = ask("95", supplier_id="ghost")
    assert unknown.decision is Decision.BLOCK and unknown.checks["typical_amount"] == "pass"


def test_the_new_check_comes_last_so_existing_first_reasons_do_not_move():
    v = ask("250", payee_email="other@acme.test")
    assert list(v.checks)[-1] == "typical_amount"
    assert v.reasons[0].startswith("payee_change:")


# ---- storage and the old database file ---------------------------------------------------------------

def test_typical_max_is_saved_and_loaded_including_none():
    conn = store.connect(":memory:")
    store.save_mandate(conn, mandate(suppliers={
        "acme": Supplier("acme", "Acme", "a@x.test", D("60.50")), "beta": Supplier("beta", "Beta", "b@x.test")}))
    loaded = store.load_mandate(conn).suppliers
    assert loaded["acme"].typical_max == D("60.50") and loaded["beta"].typical_max is None


def make_old_database(path):
    """A database file from before the typical_max column existed."""
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE suppliers (supplier_id TEXT PRIMARY KEY, name TEXT, payee_email TEXT);")
    old.commit()
    old.close()


def test_an_old_database_gets_a_clear_message_to_delete_it(tmp_path):
    old_file = str(tmp_path / "mandate.db")
    make_old_database(old_file)
    with pytest.raises(store.SchemaMismatch, match="delete the file mandate.db"):
        store.connect(old_file)
    assert issubclass(store.SchemaMismatch, RuntimeError)


def test_the_start_scripts_print_that_message_instead_of_a_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    make_old_database("mandate.db")
    run_dashboard = load_script("run_dashboard")
    with patch.object(run_dashboard.uvicorn, "run") as run:
        assert run_dashboard.main() == 1
    run.assert_not_called()
    assert "delete the file mandate.db" in capsys.readouterr().err

    run_gateway = load_script("run_gateway")
    with pytest.raises(SystemExit) as exit_info:
        run_gateway.main()
    assert exit_info.value.code == 1
    assert "delete the file mandate.db" in capsys.readouterr().err


# ---- the seeded demo values keep every sample invoice's decision ---------------------------------------------

EXPECTED_SAMPLE_DECISIONS = {
    "1_legitimate": Decision.ALLOW, "2_changed_payee": Decision.HOLD, "3_large": Decision.HOLD,
    "4_oversized": Decision.BLOCK, "5_prompt_injection": Decision.ALLOW, "5a_remittance_update": Decision.HOLD,
    "5b_compliance_override": Decision.HOLD, "5c_second_payment": Decision.BLOCK,
}


@pytest.fixture
def seeded(monkeypatch):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", EMAIL)
    conn = store.connect(":memory:")
    seed(conn)
    return conn


def test_the_seeded_values(seeded):
    suppliers = store.load_mandate(seeded).suppliers
    assert {k: s.typical_max for k, s in suppliers.items()} == {"acme": D("60"), "northwind": D("150"), "globex": D("200")}


def evaluate_sample(text, m):
    supplier_id = re.search(r"^Supplier ID:\s*(\S+)", text, re.M).group(1)
    amount = D(re.search(r"^Amount due:\s*([\d.]+)", text, re.M).group(1))
    payee = re.search(r"^Pay to \(PayPal\):\s*(\S+)", text, re.M).group(1)  # the invoice's own payee (sample 2 differs)
    req = PaymentRequest(re.search(r"^Invoice ID:\s*(\S+)", text, re.M).group(1), supplier_id, payee, amount, "USD")
    return evaluate(req, m, D("0"), set())


def test_every_sample_invoice_keeps_its_decision(seeded):
    with_limits = store.load_mandate(seeded)
    without_limits = MandateConfig(
        with_limits.currency, with_limits.total_budget, with_limits.per_payment_cap, with_limits.approval_threshold,
        with_limits.expires_at, {k: Supplier(s.supplier_id, s.name, s.payee_email) for k, s in with_limits.suppliers.items()})
    folder = ROOT / "samples" / "invoices"
    names = {p.stem for p in folder.glob("*.txt")}
    assert names == set(EXPECTED_SAMPLE_DECISIONS)  # a new sample must be added to this check
    for name, expected in EXPECTED_SAMPLE_DECISIONS.items():
        text = (folder / f"{name}.txt").read_text(encoding="utf-8").replace("{RUN_ID}", "1").replace("{PAYEE_EMAIL}", EMAIL)
        now_ = evaluate_sample(text, with_limits)
        before = evaluate_sample(text, without_limits)
        assert now_.decision == before.decision == expected, name
        # the new check changes nothing for the samples that were allowed or held. Only the two blocked ones
        # (over the cap) also trip it, and block still wins.
        assert now_.checks["typical_amount"] == ("hold" if expected is Decision.BLOCK else "pass"), name
        if expected is not Decision.BLOCK:
            assert now_.reasons == before.reasons, name


def test_an_inflated_invoice_to_acme_with_the_right_payee_is_held(seeded):
    m = store.load_mandate(seeded)
    v = evaluate(PaymentRequest("INV-95", "acme", EMAIL, D("95.00"), "USD"), m, D("0"), set())
    assert v.decision is Decision.HOLD
    assert [k for k, o in v.checks.items() if o != "pass"] == ["typical_amount"]
    assert v.reasons == ["typical_amount: amount 95.00 is above the usual maximum 60 for Acme Office Supplies"]


# ---- information minimisation: the agent's gateway ------------------------------------------------------------

@pytest.fixture
def agent_side(seeded, monkeypatch):
    monkeypatch.setattr(gateway, "_conn", seeded)
    with patch.object(service, "send_payout", return_value={"batch_id": "B1", "status": "PENDING"}) as payout:
        yield payout


def test_get_mandate_does_not_return_typical_max(agent_side):
    info = gateway.get_mandate()
    assert set(info) == {"currency", "remaining_budget", "per_payment_cap", "approval_threshold", "expires_at", "suppliers"}
    assert all(set(s) == {"supplier_id", "name"} for s in info["suppliers"])
    text = json.dumps(info)
    assert "typical" not in text and "usual" not in text and "@" not in text


def test_request_payment_reasons_do_not_reveal_the_usual_maximum(agent_side):
    r = gateway.request_payment("INV-95", "acme", EMAIL, "95.00", "USD")
    assert (r["decision"], r["status"]) == ("HOLD", "HELD")
    assert r["reasons"] == ["typical_amount: amount is above the usual maximum for this supplier"]
    assert "60" not in " ".join(r["reasons"])
    agent_side.assert_not_called()


def test_the_gateway_still_exposes_exactly_two_tools():
    assert {t.name for t in asyncio.run(gateway.mcp.list_tools())} == {"request_payment", "get_mandate"}


# ---- the dashboard (human owner) ----------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", EMAIL)
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(dashboard, "DB_PATH", db_file)
    conn = store.connect(db_file)
    seed(conn)
    conn.close()
    return TestClient(dashboard.app)


def test_the_dashboard_shows_the_usual_maximum_to_the_owner(client):
    m = client.get("/api/mandate").json()
    assert {s["supplier_id"]: s["typical_max"] for s in m["suppliers"]} == {"acme": "60", "northwind": "150", "globex": "200"}
    assert "@" not in json.dumps(m)
    html = client.get("/").text
    assert "Usual largest invoice per supplier" in html and 'id="m-suppliers"' in html
    assert 'data-demo="inflated"' in html and "Inflated invoice 95.00" in html
    assert 'data-attack="inflated"' in html and "Inflated invoice on a known supplier, correct payee" in html
    assert "Simulated attack, no AI involved" in html  # the panel that holds the new attack button


def test_the_inflated_demo_and_attack_are_held_in_real_mode(client):
    with patch.object(service, "send_payout", return_value={"batch_id": "B1", "status": "PENDING"}) as payout:
        demo = client.post("/api/demo/inflated").json()
        attack = client.post("/api/attack/inflated").json()
    for r in (demo, attack):
        assert (r["decision"], r["status"]) == ("HOLD", "HELD")
        assert r["reasons"] == ["typical_amount: amount 95.00 is above the usual maximum 60 for Acme Office Supplies"]
    payout.assert_not_called()
    assert len([p for p in client.get("/api/payments").json() if p["status"] == "HELD"]) == 2
    assert not any(p["paypal_batch_id"] for p in client.get("/api/payments").json())


def test_the_inflated_demo_and_attack_work_offline_with_no_network(client, monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")

    def no_network(*args, **kwargs):
        raise AssertionError("offline mode must not contact PayPal")

    with patch("mandate.payouts.PayPalClient", no_network), patch("requests.post", no_network), \
            patch("requests.request", no_network):
        demo = client.post("/api/demo/inflated").json()
        attack = client.post("/api/attack/inflated").json()
        approved = client.post(f"/api/payments/{demo['payment_id']}/approve").json()
    assert demo["decision"] == attack["decision"] == "HOLD"
    assert approved["status"] == "PAID" and "FAKE-" in approved["outcome"]  # a person can still approve it
    assert client.get("/api/mandate").json()["fake_payouts"] is True


def test_the_other_demos_and_attacks_behave_as_before(client):
    with patch.object(service, "send_payout", return_value={"batch_id": "B1", "status": "PENDING"}):
        decisions = {
            "legitimate": client.post("/api/demo/legitimate").json()["decision"],
            "changed_payee": client.post("/api/demo/changed_payee").json()["decision"],
            "large": client.post("/api/demo/large").json()["decision"],
            "injected": client.post("/api/attack/injected").json()["decision"],
            "attack_changed_payee": client.post("/api/attack/changed_payee").json()["decision"],
            "over_cap": client.post("/api/attack/over_cap").json()["decision"],
        }
    assert decisions == {"legitimate": "ALLOW", "changed_payee": "HOLD", "large": "HOLD", "injected": "BLOCK",
                         "attack_changed_payee": "HOLD", "over_cap": "BLOCK"}


# ---- the attack script ---------------------------------------------------------------------------------------------

def test_attack_12_is_held_and_the_fake_paypal_sees_no_payout():
    attacks = load_script("run_attacks")
    bench = attacks.Bench()
    with patch.object(service, "send_payout", bench.fake_payout):
        actual, passed, reason = attacks.inflated_amount(bench)
    assert (actual, passed) == ("HOLD", True)
    assert reason.startswith("typical_amount: amount 45 is above the usual maximum 30 for Alpha Supplies")
    assert bench.payouts == [] and bench.bad_payouts == 0
    assert len(attacks.ATTACKS) == 12
    assert attacks.ATTACKS[-1][0] == "Known supplier, correct payee, inflated amount"


# ---- the README ----------------------------------------------------------------------------------------------------

def test_readme_describes_nine_checks_and_the_new_attack():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "typical_amount" in text or "Typical amount" in text
    assert "Nine rule checks" in text and "The nine policy checks" in text
    assert "12 attacks" in text and "12-attack script" in text
    assert "no rule yet for an amount that is unusual" not in text
    assert "11 attacks" not in text and "eight policy checks" not in text.lower()
    assert "11 November 2026" in text  # the note that one check and one optional field were added to policy.py
