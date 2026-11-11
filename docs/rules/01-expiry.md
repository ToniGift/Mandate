# Rule 1: Expiry

Stops an old mandate from being used again. A mandate is a permission with an end date.

## The rule

- **Fires when:** the time of the request is at or after the mandate's expiry time.
- **Result:** **BLOCK**. Nothing is sent, and a person is not asked.
- **Reason text:** `expiry: mandate has expired`

The demo mandate expires 30 days after it is seeded. When it has expired, every request is blocked until a new mandate is created (**Reset demo data** on the dashboard seeds a new one).

## Examples

Demo mandate, expiry 30 days after seeding:

| When the request arrives | This rule | Final answer |
|--------------------------|-----------|--------------|
| Day 10 of the mandate | passes | decided by the other rules |
| Exactly at the expiry time | fires | **BLOCK** |
| One day after the expiry | fires | **BLOCK** |

## Scenarios and attacks that use it

- [Scenario 6, blocked payment](../scenarios/06-blocked-payment.md): an expired mandate is one of the BLOCK cases.
- It passes in scenarios 1 to 5 (see the [six scenarios](../README.md#six-scenarios)), because the demo mandate is fresh.
- **Attack 7**, "Expired mandate", in `scripts/run_attacks.py`: the script builds a mandate that expired a day ago and expects BLOCK.
- Test: `test_expired_mandate_is_blocked` in `tests/test_policy.py`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 1. expiry`.
- The expiry date is set when the demo mandate is created, in `mandate/seed.py`.

---

Next: [Rule 2, amount and currency](02-amount-and-currency.md) | Back to the [docs overview](../README.md)
