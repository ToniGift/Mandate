"""Tests for scripts/run_attacks.py. Everything runs in memory with a fake PayPal: no network, no .env."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from mandate import service, store
from mandate.policy import Decision, Verdict

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_attacks.py"


@pytest.fixture(scope="module")
def attacks():
    spec = importlib.util.spec_from_file_location("run_attacks", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_attack_is_stopped_or_held(attacks):
    rows, bench = attacks.run_attacks()
    assert len(rows) == 11
    assert [r["number"] for r in rows] == list(range(1, 12))
    assert all(r["passed"] for r in rows), [r for r in rows if not r["passed"]]
    assert bench.bad_payouts == 0


def test_only_allowed_or_approved_requests_reach_the_fake_paypal(attacks):
    rows, bench = attacks.run_attacks()
    # attack 5: one payout, attack 6: seven payouts (300 // 40), attack 11: one approved payout
    assert len(bench.payouts) == 1 + 7 + 1
    assert all(p["payee_email"].endswith(".example.test") for p in bench.payouts)
    assert {p["invoice_id"] for p in bench.payouts if p["invoice_id"].startswith("ATK1-")} == set()


def test_main_prints_the_table_and_the_two_summary_lines(attacks, capsys):
    assert attacks.main() == 0
    out = capsys.readouterr().out
    assert "11 of 11 attacks stopped or held as expected" in out
    assert "payouts sent for blocked or held requests: 0" in out
    assert "PASS  no payout was made for any BLOCK or HOLD case" in out
    for column in ("Attack", "Expected", "Actual", "Result", "First reason"):
        assert column in out
    assert "FAIL" not in out


def test_runs_without_network_without_env_and_never_touches_mandate_db(attacks, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_PERSONAL_EMAIL", "NEBIUS_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("the attack script must never use the network")

    opened = []
    real_connect = store.connect
    monkeypatch.setattr(store, "connect", lambda path=store.DB_FILE: opened.append(path) or real_connect(path))
    with patch("requests.post", no_network), patch("requests.request", no_network), \
            patch("mandate.paypal_client.PayPalClient", no_network):
        rows, bench = attacks.run_attacks()

    assert all(r["passed"] for r in rows)
    assert set(opened) == {":memory:"}          # only throwaway in-memory databases
    assert not (tmp_path / "mandate.db").exists()
    assert list(tmp_path.iterdir()) == []       # nothing was written to disk at all


def test_script_fails_loudly_if_the_rules_are_broken(attacks, capsys):
    """If the rule engine let everything through, the script must report FAIL and exit non-zero."""
    allow_all = Verdict(Decision.ALLOW, ["all checks passed"], {})
    with patch.object(service, "evaluate", return_value=allow_all):
        code = attacks.main()
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL" in out
    assert "payouts sent for blocked or held requests: 0" not in out  # the fake saw payouts it should not


def test_an_attack_that_crashes_counts_as_a_failure_not_a_crash(attacks, capsys):
    with patch.object(service, "handle_payment_request", side_effect=RuntimeError("boom")):
        code = attacks.main()
    out = capsys.readouterr().out
    assert code == 1 and "ERROR RuntimeError" in out and "boom" not in out
