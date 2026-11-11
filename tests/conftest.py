"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def local_real_mode_by_default(monkeypatch):
    """Tests start as a normal local run: real payout mode (offline demo mode off), a local host and
    not a public server, whatever is in the developer's .env.
    Setting each variable here also stops load_dotenv from copying a value from .env, because it
    never overrides a variable that is already set. Tests that want another mode set it themselves."""
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "0")
    monkeypatch.setenv("DASHBOARD_HOST", "127.0.0.1")
    monkeypatch.setenv("MANDATE_PUBLIC_SERVER", "0")
