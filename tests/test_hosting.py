"""Tests for hosting the dashboard on a public server (Render). No network: uvicorn and PayPal are faked."""
import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mandate import dashboard, hosting, store
from mandate.paypal_client import PayPalClient
from mandate.seed import seed

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "run_dashboard.py"


@pytest.fixture(autouse=True)
def restore_environ():
    """Some tests here remove PayPal and Nebius settings, like a public server does. Put every
    setting back afterwards, so that nothing leaks into the other tests."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture(scope="module")
def run_dashboard():
    spec = importlib.util.spec_from_file_location("run_dashboard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clear_settings(monkeypatch):
    for name in ("DASHBOARD_HOST", "DASHBOARD_PORT", "PORT"):
        monkeypatch.delenv(name, raising=False)


# ---- settings ----------------------------------------------------------------------------------

@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "LOCALHOST", " 127.0.0.1 "])
def test_local_hosts(host):
    assert hosting.is_local_host(host) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::1", "192.168.1.20", "example.com", ""])
def test_everything_else_is_public(host):
    assert hosting.is_local_host(host) is False


def test_defaults_are_unchanged_for_a_local_run(monkeypatch):
    clear_settings(monkeypatch)
    assert hosting.server_settings() == ("127.0.0.1", 8001)


def test_port_comes_from_dashboard_port_then_port_then_8001(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("PORT", "10000")
    assert hosting.server_settings() == ("127.0.0.1", 10000)           # Render's PORT
    monkeypatch.setenv("DASHBOARD_PORT", "9000")
    assert hosting.server_settings() == ("127.0.0.1", 9000)            # DASHBOARD_PORT wins
    monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")
    assert hosting.server_settings() == ("0.0.0.0", 9000)


def test_a_bad_port_gives_a_clear_error(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("PORT", "not-a-number")
    with pytest.raises(ValueError, match="port must be a number"):
        hosting.server_settings()


# ---- no credentials, no .env on a public server ---------------------------------------------------

def test_scrub_removes_paypal_and_nebius_settings_and_nothing_else(monkeypatch):
    for name in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_PERSONAL_EMAIL", "NEBIUS_API_KEY",
                 "NEBIUS_MODEL_ID"):
        monkeypatch.setenv(name, "value")
    monkeypatch.setenv("DASHBOARD_PORT", "9000")
    hosting.scrub_credentials()
    assert not [n for n in os.environ if n.startswith(("PAYPAL_", "NEBIUS_"))]
    assert os.environ["DASHBOARD_PORT"] == "9000"


def test_env_file_is_read_locally_but_never_on_a_public_server(monkeypatch):
    with patch.object(hosting, "load_dotenv") as load:
        hosting.load_env_unless_public()
        assert load.call_count == 1                      # normal local run: .env is read

        monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")  # a public host in the real environment
        hosting.load_env_unless_public()
        monkeypatch.setenv("DASHBOARD_HOST", "127.0.0.1")
        hosting.mark_public()                            # or a process already marked public
        hosting.load_env_unless_public()
        assert load.call_count == 1


def test_the_paypal_client_refuses_to_start_on_a_public_server(monkeypatch):
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
    hosting.mark_public()
    with pytest.raises(RuntimeError, match="never used on a public server"):
        PayPalClient()


def test_seed_never_reads_env_on_a_public_server_and_uses_the_demo_address(monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    monkeypatch.delenv("PAYPAL_PERSONAL_EMAIL", raising=False)
    hosting.mark_public()
    with patch.object(hosting, "load_dotenv") as load:
        mandate = seed(store.connect(":memory:"))
    load.assert_not_called()
    assert {s.payee_email for s in mandate.suppliers.values()} == {"demo-owner@example.test"}


# ---- the start script --------------------------------------------------------------------------

@pytest.fixture
def work_in_temp_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the throwaway mandate.db is created here, not in the repo
    clear_settings(monkeypatch)
    return tmp_path


def test_local_start_is_unchanged(run_dashboard, work_in_temp_folder, monkeypatch, capsys):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", "me@example.test")
    with patch.object(run_dashboard.uvicorn, "run") as run:
        assert run_dashboard.main() == 0
    run.assert_called_once_with(run_dashboard.app, host="127.0.0.1", port=8001)
    assert "Mandate dashboard at http://127.0.0.1:8001" in capsys.readouterr().out
    assert os.environ["MANDATE_PUBLIC_SERVER"] == "0"        # not a public server


def test_a_public_host_without_offline_mode_refuses_to_start(run_dashboard, work_in_temp_folder, monkeypatch, capsys):
    monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "0")
    with patch.object(run_dashboard.uvicorn, "run") as run:
        assert run_dashboard.main() == 1
    run.assert_not_called()
    err = capsys.readouterr().err
    assert "Refusing to start" in err and "MANDATE_FAKE_PAYOUTS" in err and "real payouts" in err
    assert not (work_in_temp_folder / "mandate.db").exists()


def test_a_public_host_also_refuses_when_the_variable_is_missing(run_dashboard, work_in_temp_folder, monkeypatch):
    monkeypatch.setenv("DASHBOARD_HOST", "example.com")
    monkeypatch.delenv("MANDATE_FAKE_PAYOUTS", raising=False)
    with patch.object(run_dashboard.uvicorn, "run") as run:
        assert run_dashboard.main() == 1
    run.assert_not_called()


def test_a_public_start_in_offline_mode_seeds_scrubs_and_listens_on_render_settings(
        run_dashboard, work_in_temp_folder, monkeypatch):
    monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "should-be-removed")   # even if one was set by mistake
    monkeypatch.setenv("NEBIUS_API_KEY", "should-be-removed")
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", "real@example.com")

    def boom(*args, **kwargs):
        raise AssertionError("a public server must not read .env")

    with patch.object(hosting, "load_dotenv", boom), patch.object(run_dashboard.uvicorn, "run") as run:
        assert run_dashboard.main() == 0

    run.assert_called_once_with(run_dashboard.app, host="0.0.0.0", port=10000)
    assert not [n for n in os.environ if n.startswith(("PAYPAL_", "NEBIUS_"))]
    assert os.environ["MANDATE_PUBLIC_SERVER"] == "1"

    # the empty database was seeded with a fresh demo mandate that expires about 30 days from now
    conn = store.connect(str(work_in_temp_folder / "mandate.db"))
    mandate = store.load_mandate(conn)
    days_left = (mandate.expires_at - datetime.now(timezone.utc)) / timedelta(days=1)
    assert 29.9 < days_left <= 30
    assert {s.payee_email for s in mandate.suppliers.values()} == {"demo-owner@example.test"}  # not the real email
    conn.close()


def test_an_existing_database_is_not_reseeded(run_dashboard, work_in_temp_folder, monkeypatch):
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", "me@example.test")
    with patch.object(run_dashboard.uvicorn, "run"):
        run_dashboard.main()
        conn = store.connect()
        conn.execute("UPDATE mandate SET total_budget = '123'")
        conn.commit()
        conn.close()
        run_dashboard.main()
    conn = store.connect()
    assert store.load_mandate(conn).total_budget == 123
    conn.close()


# ---- the hosted dashboard: banner and abuse guard ---------------------------------------------------

@pytest.fixture
def hosted(tmp_path, monkeypatch):
    """The dashboard app set up like the hosted demo: public, offline mode, no PayPal values."""
    db_file = str(tmp_path / "hosted.db")
    monkeypatch.setattr(dashboard, "DB_PATH", db_file)
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    for name in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_PERSONAL_EMAIL", "NEBIUS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    hosting.mark_public()
    conn = store.connect(db_file)
    seed(conn)
    conn.close()
    dashboard._recent_posts.clear()
    return TestClient(dashboard.app)


def test_the_hosted_dashboard_reports_offline_mode_for_the_banner(hosted):
    assert hosted.get("/api/mandate").json()["fake_payouts"] is True
    assert "Offline demo: payouts are simulated, PayPal is not contacted." in hosted.get("/").text


def test_the_hosted_dashboard_works_without_paypal(hosted):
    def no_network(*args, **kwargs):
        raise AssertionError("no PayPal on a public server")

    with patch("mandate.payouts.PayPalClient", no_network), patch("requests.post", no_network), \
            patch("requests.request", no_network):
        r = hosted.post("/api/demo/legitimate").json()
    assert (r["decision"], r["status"]) == ("ALLOW", "PAID") and "FAKE-" in r["outcome"]


def test_posts_are_limited_per_visitor_on_a_public_server(hosted, monkeypatch):
    monkeypatch.setattr(dashboard, "POSTS_PER_MINUTE", 3)
    visitor = {"X-Forwarded-For": "203.0.113.5"}
    for _ in range(3):
        assert hosted.post("/api/demo/large", headers=visitor).status_code == 200
    blocked = hosted.post("/api/demo/large", headers=visitor)
    assert blocked.status_code == 429
    assert "Too many requests" in blocked.json()["detail"] and "3 actions per minute" in blocked.json()["detail"]
    assert blocked.headers["retry-after"] == "60"

    assert hosted.get("/api/mandate", headers=visitor).status_code == 200          # reading is not limited
    other = {"X-Forwarded-For": "198.51.100.7, 10.0.0.1"}
    assert hosted.post("/api/demo/large", headers=other).status_code == 200       # another visitor is counted separately


def test_the_limit_clears_after_a_minute(hosted, monkeypatch):
    monkeypatch.setattr(dashboard, "POSTS_PER_MINUTE", 2)
    clock = {"now": 1000.0}
    monkeypatch.setattr(dashboard.time, "monotonic", lambda: clock["now"])
    for _ in range(2):
        assert hosted.post("/api/demo/large").status_code == 200
    assert hosted.post("/api/demo/large").status_code == 429
    clock["now"] += 61
    assert hosted.post("/api/demo/large").status_code == 200


def test_the_limit_is_off_for_a_local_run(tmp_path, monkeypatch):
    db_file = str(tmp_path / "local.db")
    monkeypatch.setattr(dashboard, "DB_PATH", db_file)
    monkeypatch.setattr(dashboard, "POSTS_PER_MINUTE", 2)
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")  # no real payouts, and no PayPal needed
    monkeypatch.setenv("PAYPAL_PERSONAL_EMAIL", "me@example.test")
    conn = store.connect(db_file)
    seed(conn)
    conn.close()
    dashboard._recent_posts.clear()
    local = TestClient(dashboard.app)
    assert all(local.post("/api/demo/large").status_code == 200 for _ in range(6))


# ---- render.yaml and the README ----------------------------------------------------------------------

def test_render_yaml_matches_the_plan_and_holds_no_secrets():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    for needle in ("type: web", "runtime: python", "plan: free", "buildCommand: pip install -r requirements.txt",
                   "startCommand: python scripts/run_dashboard.py", "healthCheckPath: /api/mandate",
                   "key: DASHBOARD_HOST", "value: 0.0.0.0", "key: MANDATE_FAKE_PAYOUTS", 'value: "1"',
                   "key: PYTHON_VERSION", "value: 3.12.10"):
        assert needle in text, needle
    assert "PAYPAL" not in text and "NEBIUS" not in text and "SECRET" not in text.upper().replace("SECRETS", "")


def test_readme_has_the_hosted_demo_section():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("## Hosted demo", 1)[1].split("\n## ", 1)[0]
    for needle in ("https://mandate-jux7.onrender.com/", "offline demo mode", "simulated",
                   "No keys are on the server", "about a minute to wake up", "Data resets when it sleeps",
                   "default and is what the demo video shows"):
        assert needle in section, needle
