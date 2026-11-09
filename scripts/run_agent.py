"""Run the AI agent on the sample invoices and print what happened.

Start the gateway first (python scripts/run_gateway.py), then in another terminal:
    python scripts/run_agent.py                    # all sample invoices
    python scripts/run_agent.py --injection-only   # only the prompt-injection invoices (5, 5a, 5b, 5c)
WARNING: allowed invoices make REAL payments in the PayPal SANDBOX (small amounts).
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from mandate import agent

load_dotenv()
INVOICE_DIR = ROOT / "samples" / "invoices"


def load_invoices(injection_only: bool = False) -> list[tuple[str, str]]:
    """Read the sample files. {RUN_ID} makes invoice ids fresh on every run, and
    {PAYEE_EMAIL} is the email every seeded supplier is paid at (see mandate/seed.py).
    The injection invoices are the ones whose file name starts with 5."""
    run_id = str(int(time.time()))
    email = os.environ.get("PAYPAL_PERSONAL_EMAIL", "")
    if not email:
        raise SystemExit("PAYPAL_PERSONAL_EMAIL must be set in .env")
    invoices = []
    for path in sorted(INVOICE_DIR.glob("*.txt")):
        if injection_only and not path.stem.startswith("5"):
            continue
        text = path.read_text(encoding="utf-8").replace("{RUN_ID}", run_id).replace("{PAYEE_EMAIL}", email)
        invoices.append((path.stem, text))
    return invoices


def short(text, width: int) -> str:
    text = str(text or "-").replace("\n", " ")
    return text if len(text) <= width else text[: width - 3] + "..."


def print_result(name: str, invoice_text: str, r: dict) -> None:
    expected = agent.expected_request(invoice_text)
    followed = "YES" if agent.followed_injection(expected, r["calls"]) else "NO"
    print(f"{short(name, 24):<25}{len(r['calls']):<7}{followed}")

    if not r["calls"]:
        print(f"{'':<4}no request_payment call made ({short(r['error'], 80)})")
    for i, call in enumerate(r["calls"], start=1):
        a = call["arguments"]
        sent = (f"invoice={a.get('invoice_id')} supplier={a.get('supplier_id')} "
                f"payee={a.get('payee_email')} amount={a.get('amount')} {a.get('currency', '')}")
        reason = call["reasons"][0] if call["reasons"] else (call["error"] or "-")
        print(f"{'':<4}call {i}: {sent}")
        print(f"{'':<11}-> {call['decision'] or 'ERROR'} / {call['status'] or '-'}: {short(reason, 80)}")
    print(f"{'':<4}agent: {short(r['summary'] or r['error'], 100)}\n")


async def main(injection_only: bool) -> None:
    invoices = load_invoices(injection_only)
    llm = agent.make_llm()
    model = agent.model_name()
    print(f"Model: {model}\n")
    print(f"{'INVOICE':<25}{'CALLS':<7}FOLLOWED INJECTION")
    print("       (each request_payment call the agent made, and Mandate's decision on it)")
    print("-" * 110)

    try:
        async with agent.connect_gateway() as session:
            tools = agent.mcp_tools_to_openai((await session.list_tools()).tools)
            for name, text in invoices:
                print_result(name, text, await agent.process_invoice(llm, model, session, tools, text))
    except Exception as err:
        print(f"Could not use the gateway ({type(err).__name__}). Is scripts/run_gateway.py running?")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Mandate agent on the sample invoices.")
    parser.add_argument("--injection-only", action="store_true",
                        help="run only the prompt-injection invoices (5, 5a, 5b, 5c)")
    asyncio.run(main(parser.parse_args().injection_only))
