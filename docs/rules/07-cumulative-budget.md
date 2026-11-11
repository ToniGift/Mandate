# Rule 7: Cumulative budget

Stops splitting one big payment into many small ones. Each small payment can look harmless, but the total cannot grow without limit.

## The rule

- **Fires when:** what has already been **paid** plus this amount is above the total budget. A total exactly equal to the budget passes.
- **Result:** **BLOCK**.
- **Reason text:** `budget: 960 already spent + 60 exceeds budget 1000` (with the amounts).

The demo budget is 1000. Only payments with the status PAID count as spent. Held and blocked requests do not use up the budget until a person approves them and they are paid.

## Examples

Demo mandate (budget 1000). Acme requests of 60.00 are under the approval threshold and equal to Acme's usual maximum, so no other rule fires:

| Already spent | Request | This rule | Final answer |
|---------------|---------|-----------|--------------|
| 0 | Acme, 60.00 | passes | **ALLOW** |
| 940 | Acme, 60.00 (total 1000) | passes | **ALLOW** |
| 960 | Acme, 60.00 (total 1020) | fires | **BLOCK** |

## Scenarios and attacks that use it

- [Scenario 6, blocked payment](../scenarios/06-blocked-payment.md): splitting into small payments is one of the BLOCK cases, and the injected 5000 USD payment also breaks the budget.
- **Attack 6**, "Splitting into small payments", in `scripts/run_attacks.py`. That script's own mandate has a budget of 300 and the attack sends payments of 40, each under the approval threshold of 50. Seven are ALLOWed (280 spent) and the eighth is BLOCKed.
- [Scenario 4, hidden instructions](../scenarios/04-hidden-instructions.md): a 5000 USD request also breaks the budget.
- Tests: `test_splitting_attack_hits_budget` in `tests/test_policy.py`, and `test_budget_tracking_blocks_when_exceeded` in `tests/test_service.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 7. cumulative budget`.
- The amount spent so far comes from `spent_so_far()` in `mandate/store.py`.
- The dashboard's mandate slip shows the budget left and a bar, and **Reset demo data** restores the full budget.

---

Previous: [Rule 6, per-payment cap](06-per-payment-cap.md) | Next: [Rule 8, approval threshold](08-approval-threshold.md) | Back to the [docs overview](../README.md)
