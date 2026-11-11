# Rule 5: Duplicate invoice

Stops the same invoice from being paid twice.

## The rule

- **Fires when:** the invoice id has already been **paid**.
- **Result:** **BLOCK**.
- **Reason text:** `duplicate_invoice: invoice ATK5 was already paid` (with the invoice id from the request).

Only payments with the status PAID count. A held or blocked request has not been paid, so the same invoice id can be sent again while the first one is still waiting. Each held request is a separate row in the queue.

There is a second guard when a payout is sent to PayPal (the sandbox): the batch id is built from the invoice id, so PayPal refuses a second payout for the same invoice (`mandate/payouts.py`).

## Examples

| Request | This rule | Final answer |
|---------|-----------|--------------|
| Invoice `INV-1` for the first time | passes | decided by the other rules |
| Invoice `INV-1` again, after it was paid | fires | **BLOCK** |
| Invoice `INV-2`, held and still waiting, sent again | passes (it was not paid) | decided by the other rules |

The dashboard demo buttons use a fresh invoice id for every click, so they never trip this rule.

## Scenarios and attacks that use it

- [Scenario 6, blocked payment](../scenarios/06-blocked-payment.md): paying the same invoice twice is one of the BLOCK cases.
- **Attack 5**, "Same invoice paid twice", in `scripts/run_attacks.py`: the first request is ALLOW and the second, with the same invoice id, is BLOCK.
- Test: `test_duplicate_invoice_is_blocked` in `tests/test_policy.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 5. duplicate invoice`.
- The list of paid invoice ids comes from `paid_invoice_ids()` in `mandate/store.py`.

---

Previous: [Rule 4, payee change](04-payee-change.md) | Next: [Rule 6, per-payment cap](06-per-payment-cap.md) | Back to the [docs overview](../README.md)
