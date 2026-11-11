# Scenario 3: A large invoice

A large invoice from a known supplier, to the right address, can be perfectly legitimate. Mandate does not guess. Above the approval threshold the answer is **HOLD**, and a person decides.

## What happens

1. A request arrives: pay 150.00 USD to Northwind Packaging, at the address on file.
2. The [approval threshold](../rules/08-approval-threshold.md) rule fires, because 150.00 is above 100.
3. The answer is **HOLD**. Nothing is sent. The payment waits under **Needs a decision**.
4. If a person presses **Approve**, the payment is sent (a payout in the PayPal sandbox, or a simulated one in offline mode) and marked PAID. If they press **Reject**, nothing is sent.

| Request | Rules that fire | Result |
|---------|-----------------|--------|
| Supplier Northwind Packaging (`northwind`). Payee: the address on file. Amount: 150.00 USD. | [Approval threshold](../rules/08-approval-threshold.md) (HOLD). The other eight rules pass. | **HOLD**, then PAID if approved |

Northwind's usual maximum is 150, so 150.00 does not trip the [typical amount](../rules/09-typical-amount.md) rule. The amount is also under the cap of 200.

## Try it

**Real mode:**

```powershell
python scripts/run_dashboard.py
```

Open http://127.0.0.1:8001. Under **Try a request**, press **Large invoice 150.00**.

- This click **sends nothing**. The result box shows a HOLD stamp, and the payment appears under **Needs a decision**.
- Press **Approve**. **In real mode this makes a real payout of 150.00 in the PayPal sandbox**, and the payment shows as PAID in the **Ledger**.
- Or press **Reject**, and nothing is sent.

**Offline mode** (no PayPal, no money): set `$env:MANDATE_FAKE_PAYOUTS = "1"` before `python scripts/run_dashboard.py`. Approve then makes a simulated payout with a `FAKE-` batch id.

**Hosted demo:** https://mandate-jux7.onrender.com/ runs in offline mode, so Approve is simulated there.

**With the AI agent:** `samples/invoices/3_large.txt` is a Northwind invoice for 150.00. In our runs the agent asked to pay it as written, and the answer was HOLD.

## Which rules decided this

- [8. Approval threshold](../rules/08-approval-threshold.md) fired and caused the HOLD.
- The others passed, including the [per-payment cap](../rules/06-per-payment-cap.md) (150.00 is not above 200) and the [budget](../rules/07-cumulative-budget.md).

## Where in the code

- `DEMOS["large"]` in `mandate/dashboard.py`.
- Check 8 in `evaluate()` in `mandate/policy.py`.
- `approve_payment()` in `mandate/service.py` sends the payout for a held payment, and writes an APPROVE row to the audit log.

<details>
<summary>See the full audit reasons</summary>

```
approval_threshold: 150.00 is above approval threshold 100
```

The outcome text is `waiting for human approval`. If a person approves, the audit log gets a second row:

```
human approved the held payment
approved by human, payout accepted, batch <PayPal batch id>, PayPal status <status>
```

</details>

---

Previous: [Scenario 2, changed payee](02-changed-payee.md) | Next: [Scenario 4, hidden instructions](04-hidden-instructions.md) | Back to the [README](../../README.md) | [Docs overview](../README.md)
