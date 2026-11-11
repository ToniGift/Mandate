# Rule 2: Amount and currency

Stops payments with a zero or negative amount, or in the wrong currency.

## The rule

- **Fires when:** the amount is zero or less, or the currency is not the mandate's currency. Capital letters do not matter, so `usd` and `USD` are the same.
- **Result:** **BLOCK**.
- **Reason texts:**
  - `amount_valid: amount must be greater than zero`
  - `amount_valid: currency EUR does not match mandate currency USD`

The demo mandate is in USD.

Badly formed input never reaches this rule. The gateway refuses it with an error first: text that is not a number, more than two decimal places, or a currency that is not three letters.

## Examples

Demo mandate (currency USD):

| Request | This rule | Final answer |
|---------|-----------|--------------|
| Acme, 25.00 USD | passes | **ALLOW** |
| Acme, 0 USD | fires | **BLOCK** |
| Acme, -5 USD | fires | **BLOCK** |
| Acme, 25.00 EUR | fires | **BLOCK** |

## Scenarios and attacks that use it

- [Scenario 6, blocked payment](../scenarios/06-blocked-payment.md): a wrong currency and a zero or negative amount are two of the BLOCK cases.
- It passes in scenarios 1 to 5 (see the [six scenarios](../README.md#six-scenarios)).
- **Attack 8**, "Wrong currency" (EUR), and **attack 9**, "Zero and negative amounts", in `scripts/run_attacks.py`.
- Test: `test_wrong_currency_and_non_positive_amounts_are_blocked` in `tests/test_policy.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 2. amount must be positive and in the mandate currency`. The check is named `amount_valid`.
- The input checks that run before it are `_to_amount()` and `_currency()` in `mandate/gateway.py`.

---

Previous: [Rule 1, expiry](01-expiry.md) | Next: [Rule 3, payee allow-list](03-payee-allow-list.md) | Back to the [docs overview](../README.md)
