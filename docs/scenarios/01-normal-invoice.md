# Scenario 1: A normal invoice

A normal invoice from a known supplier, paid to the right address, for a normal amount, is **ALLOW** and is paid.

## What happens

1. A request arrives: pay 25.00 USD to Acme Office Supplies, at the payee address Mandate has on file for Acme.
2. Mandate runs all nine rules. None of them objects.
3. The answer is **ALLOW**. Mandate sends the payout and writes the decision to the audit log.

In real mode the payout is a real payout in the PayPal **sandbox**. In offline demo mode it is simulated.

| Request | Rules that fire | Result |
|---------|-----------------|--------|
| Supplier Acme Office Supplies (`acme`). Payee: the address on file. Amount: 25.00 USD. | None. All nine rules pass. | **ALLOW**, status PAID |

## Try it

**Real mode** (the default, with the PayPal sandbox):

```powershell
python scripts/run_dashboard.py
```

Open http://127.0.0.1:8001. Under **Try a request**, press **Legitimate invoice 25.00**.

- **This click makes a real payout of 25.00 in the PayPal sandbox**, to your sandbox personal account.
- The result box shows an ALLOW stamp. The payment appears in the **Ledger**, under **Payments**, with a PayPal batch id and a status.

**Offline mode** (no PayPal, no money):

```powershell
$env:MANDATE_FAKE_PAYOUTS = "1"
python scripts/run_dashboard.py
```

Press the same button. The page shows an amber banner, and the payment is paid with a simulated payout whose batch id starts with `FAKE-`.

**Hosted demo:** https://mandate-jux7.onrender.com/ runs in offline mode, so the payout is simulated. The free server can take about a minute to wake up, and its data resets when it sleeps.

**With the AI agent** (needs the gateway running and a Nebius key): `python scripts/run_agent.py` reads `samples/invoices/1_legitimate.txt` (Acme, 25.00) and asks Mandate to pay it. In our runs the answer was ALLOW. In real mode that makes a real sandbox payout.

You can also use **Try your own request**: pick Acme and enter 25.

## Which rules decided this

All nine rules were checked and all passed:

| Rule | Why it passes here |
|------|--------------------|
| [1. Expiry](../rules/01-expiry.md) | The mandate has not expired. |
| [2. Amount and currency](../rules/02-amount-and-currency.md) | 25.00 is above zero and in USD. |
| [3. Payee allow-list](../rules/03-payee-allow-list.md) | Acme is on the supplier list. |
| [4. Payee change](../rules/04-payee-change.md) | The payee is the address on file. |
| [5. Duplicate invoice](../rules/05-duplicate-invoice.md) | The invoice id is new. |
| [6. Per-payment cap](../rules/06-per-payment-cap.md) | 25.00 is not above 200. |
| [7. Cumulative budget](../rules/07-cumulative-budget.md) | Spent so far plus 25.00 is not above 1000. |
| [8. Approval threshold](../rules/08-approval-threshold.md) | 25.00 is not above 100. |
| [9. Typical amount](../rules/09-typical-amount.md) | 25.00 is not above Acme's usual maximum of 60. |

## Where in the code

- The button's request is defined in `DEMOS["legitimate"]` in `mandate/dashboard.py`, and sent by `_submit()`.
- `handle_payment_request()` in `mandate/service.py` calls `evaluate()` in `mandate/policy.py`.
- On ALLOW it calls `_pay()` in `mandate/service.py`, which calls `send_payout()` in `mandate/payouts.py`.

<details>
<summary>See the full audit reasons</summary>

The reason list for an allowed request is a single line:

```
all checks passed
```

The outcome text in the audit log:

```
payout accepted, batch <PayPal batch id>, PayPal status <status>
```

In offline mode the outcome reads:

```
simulated payout accepted, batch FAKE-DEMO-legitimate-<number>-<code>, payout status SUCCESS
```

</details>

---

Next: [Scenario 2, changed payee](02-changed-payee.md) | Back to the [README](../../README.md) | [Docs overview](../README.md)
