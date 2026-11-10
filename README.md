# Mandate

Mandate is a policy gateway that sits between an AI agent and PayPal, because an AI agent that pays invoices can be tricked: one fake invoice, one hidden instruction, and real money moves.

Built for the PayPal AI Hackathon. Everything runs on the PayPal **sandbox**, so no real money is ever sent.

## Demo and links

- **Demo video (under 3 minutes):** [add the YouTube link here before submitting]
- **Live demo:** not hosted. The dashboard has no login, so it is meant to run on your own PC. Everything needed is in this repo, and the [Quick start](#quick-start-windows-powershell) takes about five minutes with a free PayPal sandbox account.
- **Source code:** https://github.com/ToniGift/Mandate (MIT license)

**If you only have a few minutes, check these:**

1. **Real PayPal use.** An allowed or approved payment makes a real sandbox payout through the PayPal Payouts API (`mandate/payouts.py`).
2. **The AI part.** An AI agent (Nebius) reads invoices and asks Mandate to pay them through an MCP gateway (`mandate/agent.py`, `mandate/gateway.py`).
3. **Rules in code, not AI.** Run `python scripts/run_attacks.py`. It needs no PayPal and no AI key, and it prints 11 attacks with PASS or FAIL.
4. **A person decides.** Run `python scripts/run_dashboard.py` and follow the click path under [Try it without any AI key](#try-it-without-any-ai-key). Only the dashboard can approve a held payment, and the agent cannot reach it.

## How it works

1. The business writes down a **mandate**: what the agent may pay (a budget, a cap per payment, an approval threshold, approved suppliers, an expiry date).
2. The AI agent reads an invoice and **asks** Mandate to pay it. The agent can only ask. It has no way to approve anything.
3. Mandate checks the request against the mandate using **plain code, not an AI**, and answers one of three things:
   - **ALLOW**: the payment is sent to PayPal.
   - **HOLD**: a person must approve it first, on the dashboard.
   - **BLOCK**: nothing is sent.
4. Every request, decision and reason is written to an audit log.

```
  AI agent  ->  Mandate gateway  ->  PayPal sandbox
  (reads        (rules in code:      (receives only ALLOWed payments
   invoices)     ALLOW, HOLD or       and held payments a person
                 BLOCK, then log)     approved on the dashboard)
```

The rules are code, so a tricked agent cannot talk Mandate out of them.

## Quick start (Windows PowerShell)

You need Python 3.10 or newer (tested on 3.12) and Git.

```powershell
git clone https://github.com/ToniGift/Mandate.git
cd Mandate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once in that window and activate again.

Copy .env.example to .env and fill in your values. Never commit .env.

```
# PayPal sandbox: developer.paypal.com > Apps & Credentials > Sandbox > your app
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
# Email of your sandbox PERSONAL account (receives the test payouts)
PAYPAL_PERSONAL_EMAIL=

# AI agent: Nebius Token Factory (any OpenAI-compatible provider also works)
# API key: Nebius Token Factory console > API keys
NEBIUS_API_KEY=
# Model used in our tests: deepseek-ai/DeepSeek-V4.1-Flash-1017
NEBIUS_MODEL_ID=deepseek-ai/DeepSeek-V4.1-Flash-1017
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
```

The PayPal values are needed for everything that makes payments. The Nebius values are only needed for the AI agent (scripts/run_agent.py). The dashboard, the simulated attacks and the attack script run without an AI key.

`.env.example` also lists three optional settings, commented out, with their defaults: `MANDATE_PORT` (gateway, 8000), `MANDATE_GATEWAY_URL` (where the agent finds the gateway) and `DASHBOARD_PORT` (8001).

**PayPal sandbox setup.** Everything is sandbox only, and every allowed or approved payment makes a real sandbox payout. You need two sandbox accounts:

- a **business** account, which the app belongs to and which pays the money out, and
- a **personal** account, which receives the money. Its email goes in `PAYPAL_PERSONAL_EMAIL`. All the demo suppliers are paid at this address.

To get the Client ID and Secret: go to [developer.paypal.com](https://developer.paypal.com), open Apps & Credentials, switch to Sandbox, and create an app of type **Merchant** linked to your sandbox business account. Copy its Client ID and Secret into `.env`.

## Try it without any AI key

Run these commands from the repo root, with the virtual environment active.

```powershell
python scripts/run_dashboard.py
```

Open http://127.0.0.1:8001. The first start creates `mandate.db` and seeds a demo mandate: USD, budget 1000, cap per payment 200, approval needed above 100, expires in 30 days, and three suppliers (Acme Office Supplies, Northwind Packaging, Globex Cleaning Services).

Click path:

1. Under **Try a request**, press **Legitimate invoice 25.00**. Mandate answers ALLOW and a real sandbox payout is made. The result box shows a stamp, and the payment appears in the **Ledger**.
2. Press **Changed payee 40.00**. Same supplier, new payee address: HOLD. It appears under **Needs a decision**.
3. Press **Large invoice 150.00**. Above the approval threshold: HOLD.
4. Under **Needs a decision**, press **Approve** on the 150.00 payment. It is paid.
5. Press **Reject** on the 40.00 payment. Nothing is sent.
6. Open the **Audit trail** tab in the Ledger to see every decision with its reasons.
7. In the red **Simulated compromised agent** panel, try the three attack buttons: an injected payment of 5000 USD to attacker@example.test (BLOCK), a changed payee on a known supplier (HOLD) and a payment over the cap (BLOCK). **These are simulated attacks, no AI involved.** Each button sends a hand-written bad request straight to Mandate's rule engine.
8. Use **Try your own request** to pick a supplier and an amount. The payee is always the address on file for that supplier.
9. Press **Reset demo data** (in the Try a request panel) to start again.

## Try it with the AI agent

This needs the Nebius values in `.env`. Use two terminals, both in the repo root with the virtual environment active.

Terminal 1, the gateway (an MCP server on http://127.0.0.1:8000/mcp):

```powershell
python scripts/run_gateway.py
```

Terminal 2, the agent:

```powershell
python scripts/run_agent.py
```

The agent reads each file in `samples/invoices/`, extracts the details and calls Mandate's `request_payment` tool. The gateway has exactly two tools, `request_payment` and `get_mandate`, and no tool to approve or reject. For each invoice the table shows how many `request_payment` calls the agent made, a **followed injection** column (YES if any call differs from what the visible invoice asks for), and for every call the arguments the agent sent and Mandate's decision.

```powershell
python scripts/run_agent.py --injection-only
```

This runs only the four invoices that hide malicious text (a fake instruction, a "remittance details changed" footer, a fake CFO override, and a note asking for a second payment). Their visible amounts are 30, 120, 180 and 240, so with the demo mandate the rules give ALLOW, HOLD, HOLD and BLOCK. Held payments show up on the dashboard for you to approve or reject. Run the dashboard in a third terminal to see them.

To check that your Nebius key and model can make tool calls before running the agent: `python scripts/check_nebius.py`.

## Run the tests and the attack script

```powershell
python -m pytest -q
```

The test suite has 111 tests. They use a fake PayPal and need no network or `.env`.

```powershell
python scripts/run_attacks.py
```

This simulates a fully compromised agent with 11 attacks (injected 5000 USD to an unknown payee, changed payee, oversized payment, unknown supplier, same invoice twice, splitting into small payments, expired mandate, wrong currency, zero and negative amounts, a large payment that is rejected, and a held payment that a person approves). It prints PASS or FAIL for each and exits with a non-zero code if any fail. The script uses a **fake PayPal and a temporary in-memory database**, so it sends no money and never touches `mandate.db`.

An offline demo of the rule engine alone is `python scripts/demo_policy.py`.

## The eight policy checks

If several checks fire, the worst outcome wins: BLOCK beats HOLD, and HOLD beats ALLOW. The checks live in `mandate/policy.py`.

| Check | Attack it stops | Decision |
|-------|-----------------|----------|
| Expiry | Replay of an old mandate | BLOCK |
| Amount and currency | Zero, negative or wrong-currency payment | BLOCK |
| Payee allow-list | Unknown recipient | BLOCK |
| Payee change | Known supplier, new payee account (invoice fraud) | HOLD |
| Duplicate invoice | Same invoice paid twice | BLOCK |
| Per-payment cap | Oversized payment | BLOCK |
| Cumulative budget | Splitting one big payment into many small ones | BLOCK when exceeded |
| Approval threshold | Large but legitimate payment | HOLD |

## PayPal APIs used

| API | Where in the code |
|-----|-------------------|
| OAuth 2.0 client credentials (access token, cached and refreshed) | `mandate/paypal_client.py` |
| Payouts (send a payment, read its status) | `mandate/payouts.py` |

The probe script `scripts/probe_paypal.py` also tried Orders and Invoicing in our sandbox. Orders worked but is not used. Invoicing returned 403 (not authorized) and is not used.

## AI tools used

- **Nebius Token Factory, model deepseek-ai/DeepSeek-V4.1-Flash-1017**: powers the demo agent. It reads invoices and calls Mandate's `request_payment` tool. The agent code works with any OpenAI-compatible provider through the three `NEBIUS_` settings.
- **Claude and Claude Code (Anthropic)**: development assistants, used to plan and write the code and tests.

## Honest limits

- In our tests the model resisted every injection sample. So the model did not prove the rules work. The **attack script and the simulated attacks** prove them, because they send the bad requests directly.
- There is no rule yet for an amount that is unusual for a particular supplier. Only the cap, the threshold and the budget apply.
- The dashboard has **no login**, and neither does the gateway. Run them only on your own PC, never on a public server.
- If a person approves a changed-payee payment, the money goes to the **new** address. In the sandbox it shows as Unclaimed.

## Reset

- Press **Reset demo data** on the dashboard. It deletes all payments and the audit log and restores the full budget. Payouts already sent to the sandbox are not undone.
- Or stop the dashboard and the gateway, delete `mandate.db`, and start one of them again. It seeds a fresh demo mandate when the database is empty.
- `python scripts/run_flow.py` also wipes `mandate.db` and re-seeds it, then runs six requests and approves one. It makes two real sandbox payouts.

After you change any `.py` file, restart the dashboard and the gateway. They load the code once at startup.

## Project layout

```
mandate/
  policy.py          the rule engine (plain code, no AI)
  service.py         runs a request: policy check, then pay, hold or block, and log it
  payouts.py         PayPal Payouts API
  paypal_client.py   PayPal OAuth token
  store.py           SQLite: mandate, suppliers, payments, audit log
  seed.py            the demo mandate and suppliers
  gateway.py         MCP server with request_payment and get_mandate
  agent.py           the AI agent (Nebius, OpenAI-compatible API)
  dashboard.py       web app for humans: approve, reject, audit
  static/index.html  the dashboard page (AG Grid)
scripts/             run_dashboard, run_gateway, run_agent, run_attacks, run_flow,
                     demo_policy, probe_paypal, check_nebius, mcp_smoke_test
samples/invoices/    eight sample invoices, four with hidden malicious text
tests/               111 tests
```

## License

MIT. See the `LICENSE` file.
