# How Mandate works: the docs

Mandate sits between an AI agent and PayPal. The agent can only **ask** to pay an invoice. Plain code, not an AI, checks the request against rules the business wrote down. A person approves anything that is held. Everything runs on the PayPal sandbox.

[Back to the main README](../README.md)

## The three answers

- **ALLOW**: no rule objected. The payment is sent. In real mode that is a payout in the PayPal **sandbox**. In offline demo mode the payout is simulated.
- **HOLD**: a rule wants a person to look first. Nothing is sent until someone presses **Approve** on the dashboard. **Reject** sends nothing.
- **BLOCK**: a rule is broken. Nothing is sent, and a person is not asked.

**The strictest result wins.** Every rule is checked. If one says BLOCK, the answer is BLOCK, even if another rule only says HOLD. If none says BLOCK but one says HOLD, the answer is HOLD. The answer is ALLOW only when every rule passes. Every request, every reason and every human decision is written to the audit log.

## How a request is decided

1. The business writes down a **mandate**: a budget, a cap per payment, an approval threshold, approved suppliers (each with a payee email and, optionally, a usual maximum invoice) and an expiry date.
2. The AI agent reads an invoice and asks Mandate to pay it. The gateway gives it two tools, `request_payment` and `get_mandate`. There is no tool to approve or reject.
3. `evaluate()` in `mandate/policy.py` runs the nine rules and returns the answer and the reasons.
4. `handle_payment_request()` in `mandate/service.py` acts on it: ALLOW sends the payout, HOLD queues the payment, BLOCK sends nothing. Then it writes the audit log.
5. Only the dashboard can approve or reject a held payment. The agent cannot reach it.

## Six scenarios

Each page shows one situation, the exact buttons to press, and which rules decided it.

| # | Scenario | Dashboard button | Outcome | What it shows | Page |
|---|----------|------------------|---------|---------------|------|
| 1 | A normal invoice | Legitimate invoice 25.00 | **ALLOW** | The payment is made | [Normal invoice](scenarios/01-normal-invoice.md) |
| 2 | Same supplier, new payee address | Changed payee 40.00 | **HOLD** | A person must check the new address | [Changed payee](scenarios/02-changed-payee.md) |
| 3 | A large invoice | Large invoice 150.00 | **HOLD** | Above the approval threshold | [Large invoice](scenarios/03-large-invoice.md) |
| 4 | Invoices with hidden instructions | the four sample invoices, and the red attack panel | **ALLOW, HOLD or BLOCK**, depending on the invoice | In our runs the agent ignored the hidden text. The simulated 5000 USD payment is BLOCK. | [Hidden instructions](scenarios/04-hidden-instructions.md) |
| 5 | Right supplier, right payee, inflated amount | Inflated invoice 95.00 | **HOLD** | Above that supplier's usual maximum | [Inflated invoice](scenarios/05-inflated-invoice.md) |
| 6 | A payment that breaks a rule | Injected payment: 5000 USD to attacker@example.test, and Payment over the cap | **BLOCK** | Nothing is sent, and nobody is asked | [Blocked payment](scenarios/06-blocked-payment.md) |

ALLOW and HOLD can end in a payout (HOLD only after a person approves it). BLOCK never does. A payout is a payout in the PayPal sandbox in real mode, and a simulated one in offline demo mode.

## Nine rules

The rules are checked in this order. Each page explains when the rule fires, with examples.

| # | Rule | What it stops | Result | Page |
|---|------|---------------|--------|------|
| 1 | Expiry | Replay of an old mandate | BLOCK | [Expiry](rules/01-expiry.md) |
| 2 | Amount and currency | Zero, negative or wrong-currency payment | BLOCK | [Amount and currency](rules/02-amount-and-currency.md) |
| 3 | Payee allow-list | Unknown recipient | BLOCK | [Payee allow-list](rules/03-payee-allow-list.md) |
| 4 | Payee change | Known supplier, new payee account (invoice fraud) | HOLD | [Payee change](rules/04-payee-change.md) |
| 5 | Duplicate invoice | Same invoice paid twice | BLOCK | [Duplicate invoice](rules/05-duplicate-invoice.md) |
| 6 | Per-payment cap | Oversized payment | BLOCK | [Per-payment cap](rules/06-per-payment-cap.md) |
| 7 | Cumulative budget | Splitting one big payment into many small ones | BLOCK when exceeded | [Cumulative budget](rules/07-cumulative-budget.md) |
| 8 | Approval threshold | Large but legitimate payment | HOLD | [Approval threshold](rules/08-approval-threshold.md) |
| 9 | Typical amount | Known supplier, correct payee, amount above that supplier's usual maximum | HOLD | [Typical amount](rules/09-typical-amount.md) |

## The demo mandate

The dashboard and the gateway seed this mandate when the database is empty (`mandate/seed.py`):

| Setting | Value |
|---------|-------|
| Currency | USD |
| Total budget | 1000 |
| Cap per payment | 200 |
| Approval needed above | 100 |
| Expires | 30 days after it is seeded |
| Acme Office Supplies (`acme`) | usual maximum 60 |
| Northwind Packaging (`northwind`) | usual maximum 150 |
| Globex Cleaning Services (`globex`) | usual maximum 200 |

Every demo supplier is paid at one address. In real mode that is your sandbox personal account (`PAYPAL_PERSONAL_EMAIL`). In offline demo mode, without that setting, it is `demo-owner@example.test`.

The numbers on the scenario and rule pages come from this mandate. **The attack script is different:** `scripts/run_attacks.py` builds its own small mandate (budget 300, cap 100, approval above 50, suppliers `alpha` and `beta`) so it never depends on the demo seed. Where a page mentions an attack number, the amounts in that attack are the script's, not the demo's.

## Real mode and offline mode

- **Real mode** (the default, and what the demo video shows): allowed or approved payments make real payouts in the PayPal **sandbox**.
- **Offline demo mode** (`MANDATE_FAKE_PAYOUTS=1`): the rules, the dashboard and the audit log are the same, but payouts are simulated, with batch ids that start with `FAKE-`. No money moves and PayPal is not contacted. The hosted demo at https://mandate-jux7.onrender.com/ runs in this mode. The free server can take about a minute to wake up, and its data resets when it sleeps.

The gateway and the dashboard have no login. Run them only on your own PC. The hosted demo is open to anyone with the link, which is why it only runs in offline mode.

## More

- [Model comparison](model_comparison.md): the sample invoices run through two models, in a test setup with a fake PayPal. It is one run per model on a small sample.
- The attack script: `python scripts/run_attacks.py` (12 attacks, fake PayPal, no money).
- The tests: `python -m pytest -q`.
