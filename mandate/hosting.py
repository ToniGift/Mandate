"""Settings and safety rules for running the dashboard on a public server (for example on Render).

A public server must never send real payouts and must never hold PayPal or Nebius credentials,
so it only runs in offline demo mode (MANDATE_FAKE_PAYOUTS=1).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

LOCAL_HOSTS = {"127.0.0.1", "localhost"}


def is_local_host(host: str) -> bool:
    """Only 127.0.0.1 and localhost count as local. Anything else can be reached from other machines."""
    return host.strip().lower() in LOCAL_HOSTS


def server_settings() -> tuple[str, int]:
    """Host and port for the dashboard.

    Host: DASHBOARD_HOST, default 127.0.0.1.
    Port: DASHBOARD_PORT, then PORT (Render sets this one), then 8001.
    """
    host = (os.environ.get("DASHBOARD_HOST") or "127.0.0.1").strip()
    raw_port = os.environ.get("DASHBOARD_PORT") or os.environ.get("PORT") or "8001"
    try:
        port = int(raw_port)
    except ValueError:
        raise ValueError(f"the port must be a number, but it is '{raw_port}'") from None
    return host, port


def public_mode() -> bool:
    """True in a process that is serving the public dashboard (set by mark_public)."""
    return os.environ.get("MANDATE_PUBLIC_SERVER") == "1"


def mark_public() -> None:
    os.environ["MANDATE_PUBLIC_SERVER"] = "1"


def load_env_unless_public() -> None:
    """Read .env, except on a public server, which must never read it."""
    host = os.environ.get("DASHBOARD_HOST", "")
    if public_mode() or (host and not is_local_host(host)):
        return
    load_dotenv()


def scrub_credentials() -> None:
    """Remove every PayPal and Nebius setting from this process, so nothing can use them."""
    for name in list(os.environ):
        if name.startswith(("PAYPAL_", "NEBIUS_")):
            del os.environ[name]
