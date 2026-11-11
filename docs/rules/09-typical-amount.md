# Rule 9: Typical amount

Stops an inflated invoice from a known supplier, sent to the right address, for an amount that is still under the approval threshold.

## The rule

- **Fires when:** the supplier is on the list, the business has set a **usual maximum** for that supplier, and the amount is **above** it. An amount exactly equal to the usual maximum passes.
- **Result:** **HOLD**. A person decides.
- **Reason text:** `typical_amount: amount 95.00 is above the usual maximum 60 for Acme Office Supplies`

The usual maximum is optional and is set per supplier by the owner. A supplier with none is not affected by this rule. An unknown supplier is skipped, because [rule 3](03-payee-allow-list.md) already blocks it. Mandate does not learn the number from past payments.

The agent never sees the number. The gateway's `get_mandate` tool does not return it, and when this rule holds a request the gateway tells the agent only `typical_amount: amount is above the usual maximum for this supplier`. The dashboard shows the numbers to the owner on the mandate slip.

This rule only ever says HOLD, so BLOCK from another rule still wins. It is the last rule in the list.

## Examples

Demo mandate (usual maximums: Acme 60, Northwind 150, Globex 200; approval above 100):

| Request | This rule | Final answer |
|---------|-----------|--------------|
| Acme, 60.00 | passes (equal to the usual maximum) | **ALLOW** |
| Acme, 95.00 | fires | **HOLD** (the only rule that fires) |
| Northwind, 95.00 | passes (not above 150) | **ALLOW** |
| Acme, 250.00 | fires | **BLOCK**, from the [cap](06-per-payment-cap.md) |

## Scenarios and attacks that use it

- [Scenario 5, inflated invoice](../scenarios/05-inflated-invoice.md): the main case, with the boundary, the per-supplier values and what the agent sees.
- The dashboard has **Inflated invoice 95.00**, and the red panel has **Inflated invoice on a known supplier, correct payee**. **No AI is involved** in the red panel.
- **Attack 12**, "Known supplier, correct payee, inflated amount", in `scripts/run_attacks.py`. That script's own mandate gives supplier Alpha a usual maximum of 30 and sends 45, under its approval threshold of 50.
- Tests: `tests/test_typical_amount.py`. It checks that every sample invoice keeps its decision.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 9. typical amount for this supplier`, and the optional `typical_max` field on `Supplier`.
- Stored in the suppliers table (`typical_max` column) by `mandate/store.py`. An older `mandate.db` has no such column: stop the servers, delete `mandate.db`, and start again.
- The demo values (60, 150, 200) are in `mandate/seed.py`.
- The agent-safe reason is in `request_payment()` in `mandate/gateway.py`.

---

Previous: [Rule 8, approval threshold](08-approval-threshold.md) | Back to the [docs overview](../README.md)
