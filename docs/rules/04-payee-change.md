# Rule 4: Payee change

Stops invoice fraud where a known supplier suddenly asks to be paid at a different account.

## The rule

- **Fires when:** the supplier is on the list, but the payee email in the request is different from the email Mandate has on file for that supplier. Capital letters and spaces around the address are ignored.
- **Result:** **HOLD**. A person decides.
- **Reason text:** `payee_change: payee for Acme Office Supplies changed from <address on file> to <address in the request>`

Mandate cannot tell a real update from a fraud. It makes a person look.

The agent is told less than the audit log. The gateway replaces the reason with `payee_change: payee email does not match the one on file for this supplier`, so the agent never learns the address on file.

## Examples

Demo mandate. Every demo supplier is paid at one address, the "address on file":

| Request | This rule | Final answer |
|---------|-----------|--------------|
| Acme, address on file, 25.00 | passes | **ALLOW** |
| Acme, the same address written with different capitals or spaces, 25.00 | passes | **ALLOW** |
| Acme, `new-account@example.test`, 40.00 | fires | **HOLD** |

## Scenarios and attacks that use it

- [Scenario 2, changed payee](../scenarios/02-changed-payee.md): the main case, with the reject and approve outcomes.
- [Scenario 4, hidden instructions](../scenarios/04-hidden-instructions.md): the footer in `5a_remittance_update.txt` asks for a new address.
- **Attack 2**, "Known supplier, changed payee", in `scripts/run_attacks.py`.
- Tests in `tests/test_policy.py`: `test_changed_payee_is_held_and_flagged` (it uses a look-alike address) and `test_payee_email_case_and_spaces_do_not_trigger_false_hold`.

## Where in the code

- `evaluate()` in `mandate/policy.py`, the block commented `# 4. payee change detection`. The comparison uses `_norm()`.
- The agent-safe reason is in `request_payment()` in `mandate/gateway.py`.

---

Previous: [Rule 3, payee allow-list](03-payee-allow-list.md) | Next: [Rule 5, duplicate invoice](05-duplicate-invoice.md) | Back to the [docs overview](../README.md)
