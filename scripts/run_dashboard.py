"""Start the Mandate dashboard (approval queue, payments, audit log).

Run from the repo root:  python scripts/run_dashboard.py
Open http://127.0.0.1:<DASHBOARD_PORT> (default port 8001). Seeds the database only if it is empty.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from dotenv import load_dotenv

from mandate import store
from mandate.dashboard import app
from mandate.seed import seed

load_dotenv()


def main() -> None:
    conn = store.connect()
    if conn.execute("SELECT COUNT(*) FROM mandate").fetchone()[0] == 0:
        seed(conn)
        print("Database was empty: seeded the demo mandate.")
    conn.close()

    port = int(os.environ.get("DASHBOARD_PORT", "8001"))
    print(f"Mandate dashboard at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
