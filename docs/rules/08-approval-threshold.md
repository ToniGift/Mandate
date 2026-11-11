# Rule 8: Approval threshold

A large payment can be legitimate, so Mandate does not refuse it. It asks a person.

## The rule

- **Fires when:** the amount is **above** the approval threshold. An amount exactly equal to the threshold passes this rule.
- **Result:** **HOLD**. Nothing is sent until a person presses **Approve**. **Reject** sends nothing.
- **Reason text:** `approval_threshold: 150.00 is above approval threshold 100` (with the amount and the threshold).

The demo threshold is 100. It is lower than the cap (200): between the two, a person decides. Above the cap, [rule 6](06-per-payment-cap.md) blocks.

## Examples

Demo mandate (approval above 100, cap 200):

| Request | This rule | Final answer |
|---------|-----------|--------------|
| Northwind, 100.00 | passes (equal to the threshold) | **ALLOW**, because 100.00 is also not above Northwind's usual maximum of 150 |
| Northwind, 150.00 | fires | **HOLD** |
| Globex, 180.00 | fires | **HOLD** |

## Scenarios and attacks that use it

- [Scenario 3, large invoice](../scenarios/03-large-invoice.md): the main case, with the approve and reject outcomes.
- [Scenario 5, inflated invoice](../scenarios/05-inflated-invoice.md): 95.00 is under the threshold, so this rule does not catch it, and [rule 9](09-typical-amount.md) does.
- [Scenario 4, hidden instructions](../scenarios/04-hidden-instructions.md): `5a` (120.00) and `5b` (180.00) are held by this rule.
- **Attack 10**, "Large legitimate, then rejected", and **attack 11**, "Held payment approved by a person", in `scripts/run_attacks.py`. That script's own mandate has a threshold of 50, and both attacks use 80.
- Test: `test_above_threshold_is_held` in `tests/test_policy.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 8. human approval threshold`.
- `approve_payment()` and `reject_payment()` in `mandate/service.py`. Only the dashboard calls them. The gateway has no tool for either.

---

Previous: [Rule 7, cumulative budget](07-cumulative-budget.md) | Next: [Rule 9, typical amount](09-typical-amount.md) | Back to the [docs overview](../README.md)
