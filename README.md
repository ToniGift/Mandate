# Mandate

A policy gateway between an AI agent and PayPal. Built for the PayPal AI Hackathon.

An AI agent can be fooled by what it reads, and one fake invoice can move real money. Mandate sits between the agent and PayPal. The agent asks Mandate to pay an invoice. Mandate checks fixed rules written in plain code (no AI makes the decision) and answers **ALLOW**, **HOLD** for human approval, or **BLOCK**. Every decision is logged.

**Status:** work in progress. The policy engine, the PayPal Payouts connection, the database and the demo flow work. The MCP gateway, the AI agent and the approval screen are not built yet.

## What works today

| Part | File |
|------|------|
| Policy engine (8 checks, no LLM) | `mandate/policy.py` |
| PayPal sandbox client (OAuth token, cached and refreshed) | `mandate/paypal_client.py` |
| Payouts API: send a payment, read its status | `mandate/payouts.py` |
| SQLite storage: mandate, suppliers, payments, audit log | `mandate/store.py` |
| Request handling: pay, hold or block, and log | `mandate/service.py` |
| Demo business data | `mandate/seed.py` |

## Policy checks

If several checks fire, the worst outcome wins: block beats hold, hold beats allow.

| Check | Attack it stops | Decision |
|-------|-----------------|----------|
| Expiry | Replay of an old mandate | Block |
| Amount and currency | Zero, negative or wrong-currency payment | Block |
| Payee allow-list | Unknown recipient | Block |
| Payee change | Known supplier, new payee account (invoice fraud) | Hold |
| Duplicate invoice | Same invoice paid twice | Block |
| Per-payment cap | Oversized payment | Block |
| Cumulative budget | Splitting one big payment into many small ones | Block |
| Approval threshold | Large but legitimate payment | Hold |

## Run it yourself

You need Python 3.10 or newer and a free [PayPal sandbox](https://developer.paypal.com) account with a sandbox app.

1. Install the packages:

       pip install -r requirements.txt

2. Copy `.env.example` to `.env` and fill in your sandbox values. Never commit `.env`.

       PAYPAL_CLIENT_ID=
       PAYPAL_CLIENT_SECRET=
       PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
       PAYPAL_PERSONAL_EMAIL=     (your sandbox personal account email)

3. Run the tests (no network needed):

       python -m pytest -q

4. See the policy engine decide, offline, with no PayPal:

       python scripts/demo_policy.py

5. Run the full flow. This makes **real payments in the PayPal sandbox** (25.00 and 150.00 USD) to your sandbox personal account, and resets `mandate.db`:

       python scripts/run_flow.py

6. Optional: check which PayPal sandbox APIs your app can use:

       python scripts/probe_paypal.py

## PayPal APIs used

- OAuth 2.0 client credentials (`mandate/paypal_client.py`)
- Payouts API (`mandate/payouts.py`)

## License

MIT. See `LICENSE`.
