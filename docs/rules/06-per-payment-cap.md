# Rule 6: Per-payment cap

Stops one oversized payment, whatever the invoice says.

## The rule

- **Fires when:** the amount is **above** the cap. An amount exactly equal to the cap passes this rule.
- **Result:** **BLOCK**. Nothing is sent, and a person is not asked.
- **Reason text:** `per_payment_cap: 250.00 exceeds per-payment cap 200` (with the amount and the cap).

The demo cap is 200. The cap is the largest single payment the agent may ever ask for, even with a person ready to approve. A payment above it is simply not allowed.

## Examples

Demo mandate (cap 200, approval above 100):

| Request | This rule | Final answer |
|---------|-----------|--------------|
| Acme, 25.00 | passes | **ALLOW** |
| Globex, 200.00 | passes (equal to the cap) | **HOLD**, because 200.00 is above the approval threshold of 100 |
| Globex, 201.00 | fires | **BLOCK** |
| Acme, 250.00 | fires | **BLOCK** (the reasons also list the threshold and Acme's usual maximum, and BLOCK wins) |

## Scenarios and attacks that use it

- [Scenario 6, blocked payment](../scenarios/06-blocked-payment.md): the injected 5000 USD payment and the 250.00 payment over the cap are both BLOCKED by this rule.
- [Scenario 4, hidden instructions](../scenarios/04-hidden-instructions.md): `5c_second_payment.txt` is for 240.00, which exceeds the cap, and the simulated 5000 USD payment exceeds it too.
- [Scenario 5, inflated invoice](../scenarios/05-inflated-invoice.md): Acme at 250.00 shows BLOCK beating HOLD.
- The dashboard's red panel has a button for it, **Payment over the cap** (Acme, 250.00). **No AI is involved.**
- **Attack 3**, "Payment over the per-payment cap", in `scripts/run_attacks.py`. That script's own mandate has a cap of 100, and the attack asks for 150.
- Test: `test_over_cap_is_blocked` in `tests/test_policy.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 6. per-payment cap`.
- The demo cap is set in `mandate/seed.py`.

---

Previous: [Rule 5, duplicate invoice](05-duplicate-invoice.md) | Next: [Rule 7, cumulative budget](07-cumulative-budget.md) | Back to the [docs overview](../README.md)
