"""Start the Mandate dashboard (approval queue, payments, audit log).

Run from the repo root:  python scripts/run_dashboard.py
Open http://127.0.0.1:<DASHBOARD_PORT> (default port 8001). Seeds the database only if it is empty.

Settings: DASHBOARD_HOST (default 127.0.0.1), DASHBOARD_PORT, then PORT (set by Render), then 8001.
A host that is not 127.0.0.1 or localhost is a PUBLIC server. It refuses to start unless
MANDATE_FAKE_PAYOUTS=1 (offline demo mode), it never reads .env, and it removes every PayPal and
Nebius setting from its environment.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from mandate import store
from mandate.dashboard import app
from mandate.hosting import (is_local_host, load_env_unless_public, mark_public, scrub_credentials,
                             server_settings)
from mandate.payouts import fake_payouts_enabled
from mandate.seed import seed


def main() -> int:
    load_env_unless_public()  # reads .env only when the host is local
    try:
        host, port = server_settings()
    except ValueError as err:
        print(f"Cannot start: {err}.", file=sys.stderr)
        return 1

    public = not is_local_host(host)
    if public:
        if not fake_payouts_enabled():
            print(f"Refusing to start: the host is '{host}', which is not local, and MANDATE_FAKE_PAYOUTS is not 1.\n"
                  "A public server must never send real payouts. Set MANDATE_FAKE_PAYOUTS=1 (offline demo mode), "
                  "or use the host 127.0.0.1.", file=sys.stderr)
            return 1
        mark_public()
        scrub_credentials()  # a public server never holds PayPal or Nebius settings

    conn = store.connect()
    if conn.execute("SELECT COUNT(*) FROM mandate").fetchone()[0] == 0:
        seed(conn)  # a fresh demo mandate, expiring 30 days from now
        print("Database was empty: seeded the demo mandate.")
    conn.close()

    if public:
        print(f"Mandate dashboard (public, offline demo mode) on {host}:{port}")
    else:
        print(f"Mandate dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
