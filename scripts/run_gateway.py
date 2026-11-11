"""Start the Mandate gateway (MCP over Streamable HTTP on localhost).

Run from the repo root:  python scripts/run_gateway.py
Seeds the database only if it is empty. URL: http://127.0.0.1:<MANDATE_PORT>/mcp (default port 8000)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mandate import gateway, store
from mandate.seed import seed


def main() -> None:
    try:
        conn = store.connect()
    except store.SchemaMismatch as err:  # an old mandate.db: say what to do, not a traceback
        print(err, file=sys.stderr)
        raise SystemExit(1)
    if conn.execute("SELECT COUNT(*) FROM mandate").fetchone()[0] == 0:
        seed(conn)
        print("Database was empty: seeded the demo mandate.")
    conn.close()

    print(f"Mandate gateway at http://{gateway.mcp.settings.host}:{gateway.mcp.settings.port}/mcp")
    gateway.mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
