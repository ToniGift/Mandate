# Scenario 5: An inflated invoice

The right supplier, the right payee address, an amount under the approval threshold, and still wrong: the invoice is much larger than that supplier usually sends. The answer is **HOLD**.

## What happens

1. A request arrives: pay 95.00 USD to Acme Office Supplies, at the address on file.
2. Nothing looks wrong to the other rules. The supplier is known, the payee has not changed, and 95.00 is under the approval threshold (100) and under the cap (200).
3. The [typical amount](../rules/09-typical-amount.md) rule fires. The business has said that Acme's usual largest invoice is **60**, and 95.00 is above it.
4. The answer is **HOLD**. A person decides.

| Request | Rules that fire | Result |
|---------|-----------------|--------|
| Supplier Acme Office Supplies (`acme`). Payee: the address on file. Amount: 95.00 USD. | [Typical amount](../rules/09-typical-amount.md) (HOLD). The other eight rules pass. | **HOLD** |

## The boundary

The rule fires only when the amount is **above** the usual maximum. Using the demo mandate:

| Request | Typical amount rule | Result |
|---------|---------------------|--------|
| Acme, 60.00 | passes (60 is not above 60) | **ALLOW** |
| Acme, 61.00 | fires | **HOLD** |
| Acme, 95.00 | fires | **HOLD** |

## It is per supplier

Each supplier has its own usual maximum: Acme 60, Northwind 150, Globex 200. The same amount can be normal for one supplier and unusual for another:

| Request | Result | Why |
|---------|--------|-----|
| Acme, 95.00 | **HOLD** | above Acme's 60 |
| Northwind, 95.00 | **ALLOW** | not above Northwind's 150, and under the threshold of 100 |
| Globex, 95.00 | **ALLOW** | not above Globex's 200, and under the threshold of 100 |

A supplier with no usual maximum set is not affected by this rule at all.

## BLOCK beats HOLD

This rule only ever says HOLD. If a harder rule also fires, the strictest result wins. Acme at 250.00 breaks the [per-payment cap](../rules/06-per-payment-cap.md) (200), so the answer is **BLOCK**. The reasons list also mentions the typical amount, and the [approval threshold](../rules/08-approval-threshold.md).

## The agent never sees the usual maximum

The usual maximum is for the owner, not the agent. An agent that knew the number could stay just under it.

- The gateway's `get_mandate` tool returns the currency, the remaining budget, the cap, the approval threshold, the expiry date, and the supplier ids and names. It does not return the usual maximum.
- When a request is held for this reason, the gateway tells the agent only: "typical_amount: amount is above the usual maximum for this supplier". The number stays in the audit log.
- The dashboard shows the usual maximums to the owner, on the mandate slip, under "Usual largest invoice per supplier".

## The owner sets the number

The usual maximum is a number the owner puts into the mandate. Mandate does not learn it from past payments, and nothing in the code changes it while Mandate runs. In the demo it comes from `mandate/seed.py`. The values (60, 150 and 200) were chosen so that every sample invoice keeps its decision, while 95.00 to Acme is held. None of the eight sample invoices trips this rule on its own, so use the dashboard buttons below.

## Try it

**Real mode:**

```powershell
python scripts/run_dashboard.py
```

Open http://127.0.0.1:8001. Under **Try a request**, press **Inflated invoice 95.00**.

- This click **sends nothing**. The result box shows a HOLD stamp and the reason about the usual maximum. The payment appears under **Needs a decision**.
- **Approve** makes a real payout of 95.00 in the PayPal sandbox. **Reject** sends nothing.
- The mandate slip shows the three usual maximums.
- To find the boundary, use **Try your own request**: pick Acme and send 60, then 61. **Sending 60 is ALLOWed and makes a real sandbox payout of 60.00.**

The red **Simulated compromised agent** panel has the matching button, **Inflated invoice on a known supplier, correct payee**. It sends a hand-written request straight to the rule engine. **No AI is involved.** The answer is HOLD, and it sends nothing.

**Offline mode** (no PayPal, no money): set `$env:MANDATE_FAKE_PAYOUTS = "1"` before `python scripts/run_dashboard.py`. The rule and the answers are the same. Approve then makes a simulated payout with a `FAKE-` batch id.

**Hosted demo:** https://mandate-jux7.onrender.com/ runs in offline mode. If it does not show the **Inflated invoice 95.00** button yet, it has not been redeployed with this version.

**In the attack script:** attack 12, "Known supplier, correct payee, inflated amount" (`python scripts/run_attacks.py`), expects HOLD, and the fake PayPal sees no payout. The script uses its own small mandate: supplier Alpha has a usual maximum of 30, the request is for 45, and the approval threshold is 50, so only this rule fires.

## Which rules decided this

- [9. Typical amount](../rules/09-typical-amount.md) fired and caused the HOLD.
- Passing, and worth comparing: [4. Payee change](../rules/04-payee-change.md) (the payee is the one on file) and [8. Approval threshold](../rules/08-approval-threshold.md) (95.00 is not above 100). This is the case those two rules do not catch.

## Where in the code

- Check 9 in `evaluate()` in `mandate/policy.py`, and the optional `typical_max` field on `Supplier`.
- `typical_max` is stored as a column of the suppliers table in `mandate/store.py`.
- The demo values are in `mandate/seed.py`.
- The generic reason for the agent is in `request_payment()` in `mandate/gateway.py`.
- `DEMOS["inflated"]` and `ATTACKS["inflated"]` in `mandate/dashboard.py`.
- `inflated_amount()` in `scripts/run_attacks.py`, and the tests in `tests/test_typical_amount.py`.

<details>
<summary>See the full audit reasons</summary>

For Acme at 95.00 (the audit log, which only the human owner sees):

```
typical_amount: amount 95.00 is above the usual maximum 60 for Acme Office Supplies
```

For Acme at 250.00 (BLOCK):

```
per_payment_cap: 250.00 exceeds per-payment cap 200
approval_threshold: 250.00 is above approval threshold 100
typical_amount: amount 250.00 is above the usual maximum 60 for Acme Office Supplies
```

What the AI agent is told through the gateway for the 95.00 request:

```
typical_amount: amount is above the usual maximum for this supplier
```

</details>

---

Previous: [Scenario 4, hidden instructions](04-hidden-instructions.md) | Next: [Scenario 6, blocked payment](06-blocked-payment.md) | Back to the [README](../../README.md) | [Docs overview](../README.md)
