# Mandate

Mandate is a policy gateway that sits between an AI agent and PayPal, so an agent that pays invoices cannot be tricked into paying the wrong person or the wrong amount.

- **Demo video (under 3 minutes):** [add the YouTube link here before submitting]
- **Source code:** https://github.com/ToniGift/Mandate
- **License:** [MIT](LICENSE)
- **Hosted demo:** https://mandate-jux7.onrender.com/ (offline mode: payouts are simulated and PayPal is not contacted; the free server can take about a minute to wake up, and its data resets when it sleeps).
- **Real PayPal sandbox run:** the default mode. Run it on your own PC with the Quick start below (about five minutes with free PayPal sandbox accounts). The demo video shows this mode.

Built for the PayPal AI Hackathon. Everything runs on the PayPal sandbox, so no real money is sent.

## What Mandate does

**The problem.** An AI agent that pays invoices can be tricked. One fake invoice, one hidden instruction, or one changed bank detail, and real money moves to the wrong place.

**The solution.** The agent never talks to PayPal directly. It can only **ask** Mandate to pay an invoice. Mandate checks the request against a mandate the business wrote down (a budget, a cap per payment, an approval threshold, approved suppliers, an expiry date). It uses plain code, not an AI, and answers ALLOW, HOLD or BLOCK. Allowed payments go to PayPal. Held payments wait for a person to approve them on a dashboard. Blocked payments send nothing. Every decision is logged. Because the rules are code, a tricked agent cannot talk Mandate out of them.

```
  Agent  ->  Mandate gateway  ->  PayPal sandbox
  (reads     (rules in code:      (receives only ALLOWed payments
  invoices)   ALLOW, HOLD or       and held payments a person
              BLOCK, then log)     approved on the dashboard)
```

## Features

- A **mandate** with a budget, a cap per payment, an approval threshold, a supplier list (each supplier can have a usual maximum invoice) and an expiry date.
- **Nine rule checks** that answer ALLOW, HOLD or BLOCK (see [How it works in detail](#how-it-works-in-detail)).
- **Real PayPal sandbox payouts** for allowed or approved payments.
- An **MCP gateway with exactly two tools**, `request_payment` and `get_mandate`. There is no tool to approve or reject.
- An **AI agent** that reads invoices and asks Mandate to pay them.
- A **human dashboard** with an approval queue, a payments list, an audit trail, a simulated attacks panel, a "Try your own request" form and a reset button.
- An **attack test script** that runs 12 attacks and prints PASS or FAIL for each.
- **190 automated tests**.

## How Mandate meets the technology requirement

### PayPal

| API | What it does in the project | Where |
|-----|-----------------------------|-------|
| OAuth 2.0 client credentials | Gets the sandbox access token. It is cached and refreshed before it expires. | `mandate/paypal_client.py` |
| Payouts | Sends the payment for an allowed or approved request, and reads the payout status back. Retrying the same invoice cannot pay twice, because the batch id is built from the invoice id. | `mandate/payouts.py` |

The probe script `scripts/probe_paypal.py` also tried Orders and Invoicing in our sandbox. Orders worked but is not used. Invoicing returned 403 (not authorized) and is not used.

### AI

**Nebius Token Factory with the model deepseek-ai/DeepSeek-V4.1-Flash-1017** powers the agent (`mandate/agent.py`). The agent reads an invoice, extracts the invoice id, supplier, payee email, amount, currency and memo, and calls Mandate's `request_payment` tool. The agent code works with any OpenAI-compatible provider through the three `NEBIUS_` settings.

The model only asks. The ALLOW, HOLD or BLOCK decision is made by plain code in `mandate/policy.py`, not by the model.

## Run it yourself

### Access you need (free)

- A **PayPal developer account** ([developer.paypal.com](https://developer.paypal.com)) with two sandbox accounts:
  - a **business** account, which the app belongs to and which pays the money out, and
  - a **personal** account, which receives the money. Its email goes in `PAYPAL_PERSONAL_EMAIL`. All the demo suppliers are paid at this address.
- A **Merchant app** linked to the sandbox business account. To get the Client ID and Secret: open Apps & Credentials, switch to Sandbox, create an app of type Merchant linked to your sandbox business account, and copy its Client ID and Secret into `.env`.
- **Only for the AI agent:** a Nebius Token Factory API key. Any OpenAI-compatible provider also works.

No keys are included in this repo. Nothing needs payment. The dashboard, the simulated attacks and the attack script need no AI key.

Everything is sandbox only, and every allowed or approved payment makes a real sandbox payout.

### Quick start (Windows PowerShell)

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

`.env.example` also lists optional settings, commented out, with their defaults: `MANDATE_PORT` (gateway, 8000), `MANDATE_GATEWAY_URL` (where the agent finds the gateway), `DASHBOARD_PORT` (8001), `DASHBOARD_HOST` (127.0.0.1, for hosting) and `MANDATE_FAKE_PAYOUTS` (offline demo mode, off by default, see the next section).

## Try it with no keys at all

**Real mode, with the PayPal sandbox, is the default, and it is what the demo video shows.** If you have no PayPal sandbox account yet and just want to look around, use **offline demo mode**.

It simulates only the payout: the batch id starts with `FAKE-` and the status is `SUCCESS`. Everything else is the real code: the nine rules, the budget, the approval queue, the audit trail and the simulated attacks. No PayPal values, no AI key and no `.env` file are needed.

```powershell
$env:MANDATE_FAKE_PAYOUTS = "1"
python scripts/run_dashboard.py
```

Open http://127.0.0.1:8001 and follow the same [dashboard click path](#dashboard-click-path). An amber banner at the top reads "Offline demo: payouts are simulated, PayPal is not contacted." The banner is shown whenever this mode is on. In this mode nothing is sent to PayPal, so nothing appears in any PayPal account.

- Without `PAYPAL_PERSONAL_EMAIL`, the demo suppliers use a made-up address (`demo-owner@example.test`).
- The AI agent still needs its Nebius key. To run it offline too, set `MANDATE_FAKE_PAYOUTS=1` and `PAYPAL_PERSONAL_EMAIL=demo-owner@example.test` in the terminals that run the gateway and the agent.
- To go back to real mode, run `Remove-Item Env:MANDATE_FAKE_PAYOUTS`, restart the dashboard, and press **Reset demo data**. Payments made offline stay in `mandate.db` until you reset.
- You can also put `MANDATE_FAKE_PAYOUTS=1` in `.env` instead of setting it in the terminal.

## Hosted demo

**URL:** https://mandate-jux7.onrender.com/

The hosted demo is the dashboard running on a free [Render](https://render.com) web service, set up by `render.yaml`. Real mode, with the PayPal sandbox, is the default and is what the demo video shows. The hosted copy is different:

- It runs in **offline demo mode**: payouts are simulated, and an amber banner on the page says so.
- **No keys are on the server.** There are no PayPal or Nebius values, and the app does not read a `.env` file there.
- The free tier can take **about a minute to wake up** the first time you open it.
- **Data resets when it sleeps or restarts.** The server starts with a fresh demo mandate (budget 1000, expiring 30 days from the start), because its database file is lost on restart.
- It has no login, so everyone who has the link shares the same demo data, and anyone can press Approve, Reject or Reset demo data. To keep it from being abused, it allows 30 actions (POST requests) per visitor per minute and answers with a clear message after that.

Safety rules in the code (`mandate/hosting.py`, `scripts/run_dashboard.py`): a dashboard host other than `127.0.0.1` or `localhost` is treated as a public server. It refuses to start unless `MANDATE_FAKE_PAYOUTS=1`, it never reads `.env`, and it removes every `PAYPAL_` and `NEBIUS_` setting from its environment, so a public server cannot send real payouts.

Settings for hosting: `DASHBOARD_HOST` (default `127.0.0.1`; `render.yaml` sets `0.0.0.0`) and the port, taken from `DASHBOARD_PORT`, then `PORT` (Render sets it), then 8001.

## Try it

Run every command from the repo root, with the virtual environment active.

### Five-minute check for judges

1. **Real PayPal use.** An allowed or approved payment makes a real sandbox payout through the PayPal Payouts API (`mandate/payouts.py`).
2. **The AI part.** An AI agent (Nebius) reads invoices and asks Mandate to pay them through an MCP gateway (`mandate/agent.py`, `mandate/gateway.py`).
3. **Rules in code, not AI.** Run `python scripts/run_attacks.py`. It needs no PayPal and no AI key, and it prints 12 attacks with PASS or FAIL.
4. **A person decides.** Run `python scripts/run_dashboard.py` and follow the [dashboard click path](#dashboard-click-path). Only the dashboard can approve a held payment, and the agent cannot reach it.

### Dashboard click path

No AI key is needed.

```powershell
python scripts/run_dashboard.py
```

Open http://127.0.0.1:8001. The first start creates `mandate.db` and seeds a demo mandate: USD, budget 1000, cap per payment 200, approval needed above 100, expires in 30 days, and three suppliers (Acme Office Supplies, Northwind Packaging, Globex Cleaning Services). Each supplier also has a usual largest invoice (60, 150 and 200), shown on the mandate slip.

1. Under **Try a request**, press **Legitimate invoice 25.00**. Mandate answers ALLOW and a real sandbox payout is made. The result box shows a stamp, and the payment appears in the **Ledger**.
2. Press **Changed payee 40.00**. Same supplier, new payee address: HOLD. It appears under **Needs a decision**.
3. Press **Large invoice 150.00**. Above the approval threshold: HOLD.
4. Press **Inflated invoice 95.00**. The right supplier and the right payee, and under the approval threshold, but more than Acme usually invoices (60): HOLD, with the reason "typical_amount".
5. Under **Needs a decision**, press **Approve** on the 150.00 payment. It is paid.
6. Press **Reject** on the 40.00 payment. Nothing is sent.
7. Open the **Audit trail** tab in the Ledger to see every decision with its reasons.
8. In the red **Simulated compromised agent** panel, try the four attack buttons: an injected payment of 5000 USD to attacker@example.test (BLOCK), a changed payee on a known supplier (HOLD), a payment over the cap (BLOCK) and an inflated invoice on a known supplier with the correct payee (HOLD). **These are simulated attacks, no AI involved.** Each button sends a hand-written bad request straight to Mandate's rule engine.
9. Use **Try your own request** to pick a supplier and an amount. The payee is always the address on file for that supplier.
10. Press **Reset demo data** (in the Try a request panel) to start again.

### The AI agent

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

### Tests and the attack script

```powershell
python -m pytest -q
```

The test suite has 190 tests. They use a fake PayPal and need no network or `.env`.

```powershell
python scripts/run_attacks.py
```

This simulates a fully compromised agent with 12 attacks (injected 5000 USD to an unknown payee, changed payee, oversized payment, unknown supplier, same invoice twice, splitting into small payments, expired mandate, wrong currency, zero and negative amounts, a large payment that is rejected, a held payment that a person approves, and a known supplier with the correct payee and an inflated amount that is held). It prints PASS or FAIL for each and exits with a non-zero code if any fail. The script uses a **fake PayPal and a temporary in-memory database**, so it sends no money and never touches `mandate.db`.

An offline demo of the rule engine alone is `python scripts/demo_policy.py`.

## How it works in detail

1. The business writes down a **mandate**: a budget, a cap per payment, an approval threshold, approved suppliers and an expiry date.
2. The AI agent reads an invoice and **asks** Mandate to pay it. The agent can only ask. It has no way to approve anything.
3. Mandate checks the request against the mandate using **plain code, not an AI**, and answers one of three things:
   - **ALLOW**: the payment is sent to PayPal.
   - **HOLD**: a person must approve it first, on the dashboard.
   - **BLOCK**: nothing is sent.
4. Every request, decision and reason is written to an audit log.

### The nine policy checks

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
| Typical amount | Known supplier, correct payee, but an invoice far above what that supplier usually sends (only when the business has set a usual maximum for the supplier) | HOLD |

The usual maximum is for the human owner. The agent's gateway never returns it, not even in the reasons it gives back.

## How Mandate maps to the judging criteria

- **Technological implementation:** real PayPal Payouts calls (`mandate/payouts.py`), an MCP gateway (`mandate/gateway.py`), an agent that uses tool calling (`mandate/agent.py`), 190 tests, and a 12-attack script (`scripts/run_attacks.py`).
- **Design:** the dashboard (`mandate/static/index.html`) with an approval queue, an audit trail, rubber-stamp decisions, and the mandate shown as a slip with a budget bar.
- **Potential impact:** it addresses invoice fraud against AI agents that pay. It is for finance teams that give an agent access to payments and want fixed limits and a human sign-off on anything unusual.
- **Innovation:** the rules are code that the agent cannot override, and the approval path (the dashboard) cannot be reached by the agent or through the gateway.
- **Presentation:** the demo video (link at the top) and this README.

## Project history

This is a new project, built solo for this hackathon. The first commit in this repository is dated 9 November 2026.

The rule engine `mandate/policy.py` was drafted first and then left alone. On 11 November 2026 one check (`typical_amount`) and one optional supplier field (`typical_max`) were added to it. No other check was changed.

## Third-party tools and licenses

These are used within their terms.

- **PayPal sandbox and the PayPal Payouts API**: the payment side of the project.
- **Nebius Token Factory**: hosts the model that powers the demo agent.
- **AG Grid Community**: the grids on the dashboard. It is loaded from the jsDelivr CDN and pinned to version 32.3.3.
- **Google Fonts**: the dashboard loads the Bricolage Grotesque and IBM Plex Sans fonts from Google Fonts.
- **Python packages** (see `requirements.txt`): pytest (MIT), requests (Apache-2.0), python-dotenv (BSD-3-Clause), mcp (MIT), openai (Apache-2.0), fastapi (MIT) and uvicorn (BSD-3-Clause).
- **Claude and Claude Code (Anthropic)**: development assistants, used to plan and write the code and tests.

## Honest limits

- In our tests the model resisted every injection sample. So the model did not prove the rules work. The **attack script and the simulated attacks** prove them, because they send the bad requests directly.
- The dashboard has **no login**, and neither does the gateway. Run them only on your own PC. The one exception is the hosted demo, which is safe to expose only because it runs in offline demo mode with no keys on the server. Anyone with its link can approve, reject or reset its shared demo data.
- If a person approves a changed-payee payment, the money goes to the **new** address. In the sandbox it shows as Unclaimed.

## Reset

- Press **Reset demo data** on the dashboard. It deletes all payments and the audit log and restores the full budget. Payouts already sent to the sandbox are not undone.
- Or stop the dashboard and the gateway, delete `mandate.db`, and start one of them again. It seeds a fresh demo mandate when the database is empty.
- If you update from an older version and the start script says the database does not match the current schema, do the same: stop both, delete `mandate.db`, and start again. There is no migration.
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
  hosting.py         settings and safety rules for a public (hosted) dashboard
  gateway.py         MCP server with request_payment and get_mandate
  agent.py           the AI agent (Nebius, OpenAI-compatible API)
  dashboard.py       web app for humans: approve, reject, audit
  static/index.html  the dashboard page (AG Grid)
scripts/             run_dashboard, run_gateway, run_agent, run_attacks, run_flow,
                     demo_policy, probe_paypal, check_nebius, mcp_smoke_test
render.yaml          Render blueprint for the hosted demo (offline demo mode)
samples/invoices/    eight sample invoices, four with hidden malicious text
tests/               190 tests
```

## License

[MIT License](LICENSE). Free to test and evaluate, with no restrictions, under the MIT license.

Mandate is an independent hackathon project and is not affiliated with any other product of the same name.
