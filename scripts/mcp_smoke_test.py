"""Smoke test: talk to the running gateway like an agent would.

Start the gateway first (python scripts/run_gateway.py), then in another terminal:
    python scripts/mcp_smoke_test.py
WARNING: the legitimate request makes a REAL 25.00 USD payment in the PayPal SANDBOX.
"""
import asyncio
import os
import time

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()
URL = f"http://127.0.0.1:{os.environ.get('MANDATE_PORT', '8000')}/mcp"


async def call(session: ClientSession, tool: str, args: dict) -> None:
    print(f"\n> {tool}({args})")
    result = await session.call_tool(tool, args)
    label = "ERROR" if result.isError else "result"
    print(f"{label}: {result.content[0].text}")


async def main() -> None:
    run = str(int(time.time()))
    # The smoke test needs a payee email; the gateway never reveals it, so read it from .env.
    email = os.environ["PAYPAL_PERSONAL_EMAIL"]

    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            await call(session, "get_mandate", {})
            await call(session, "request_payment", {
                "invoice_id": f"SMOKE-{run}-1", "supplier_id": "acme", "payee_email": email,
                "amount": "25.00", "currency": "USD", "memo": "Smoke test: legitimate invoice"})
            await call(session, "request_payment", {
                "invoice_id": f"SMOKE-{run}-2", "supplier_id": "acme",
                "payee_email": "new-account@example.test",
                "amount": "25.00", "currency": "USD", "memo": "Smoke test: changed payee"})


if __name__ == "__main__":
    asyncio.run(main())
