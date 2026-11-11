# Rule 3: Payee allow-list

Stops payments to a supplier the business never approved.

## The rule

- **Fires when:** the supplier id in the request is not in the mandate's supplier list. The id must match exactly, capital letters included.
- **Result:** **BLOCK**.
- **Reason text:** `payee_allow_list: supplier 'ghost' is not on the allow-list` (with the supplier id from the request).

The demo mandate has three suppliers: `acme` (Acme Office Supplies), `northwind` (Northwind Packaging) and `globex` (Globex Cleaning Services).

When the supplier is unknown, [rule 4](04-payee-change.md) and [rule 9](09-typical-amount.md) have nothing to compare against, so they pass. The other rules still run.

## Examples

Demo mandate:

| Request | This rule | Final answer |
|---------|-----------|--------------|
| `acme`, 25.00 USD | passes | decided by the other rules (**ALLOW**) |
| `unknown-supplier`, 5000 USD | fires | **BLOCK** |
| `Acme` (capital A), 25.00 USD | fires, because the id is `acme` | **BLOCK** |

## Scenarios and attacks that use it

- [Scenario 6, blocked payment](../scenarios/06-blocked-payment.md): the main walk-through. The injected 5000 USD payment names a supplier that is not on the list.
- [Scenario 4, hidden instructions](../scenarios/04-hidden-instructions.md): the simulated 5000 USD payment names a supplier that is not on the list.
- **Attack 1**, "Injected 5000 USD, unknown payee", and **attack 4**, "Unknown supplier", in `scripts/run_attacks.py`.
- Test: `test_unknown_supplier_is_blocked` in `tests/test_policy.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 3. payee allow-list`.
- The supplier list is part of the mandate: `MandateConfig.suppliers` in `mandate/policy.py`, saved by `mandate/store.py`.

---

Previous: [Rule 2, amount and currency](02-amount-and-currency.md) | Next: [Rule 4, payee change](04-payee-change.md) | Back to the [docs overview](../README.md)
