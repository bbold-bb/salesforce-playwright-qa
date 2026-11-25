# Test users per tester and persona: build plan

**Spec:** [2026-11-25-test-users-design.md](../specs/2026-11-25-test-users-design.md)

**Constraints:** invented names only; no password, email or production; Python standard library; nothing about the kit's optional ledger changes.

**Review focus:** a tester whose name contains another's; a persona naming something the org doesn't have; too few licenses; a rerun after a partial edit to `personas.json`; a settings file naming a user that was deactivated. Each has a test in `templates/qa/tests/test_test_users.py` or a check in the scratch org run.

- [ ] 1. `personas.json` and `test_users.py`, with unit tests for names, validation, the plan and the Apex
- [ ] 2. `lib/testUsers.ts`, and the harness records who each step ran as
- [ ] 3. `lib/runLock.ts`, `lib/videoCuts.ts`, tab settling and the new screen helpers
- [ ] 4. Template, example spec, skill, docs, setup questions
- [ ] 5. Eval fixtures and checker follow the template
- [ ] 6. Run in a throwaway scratch org: plan, rehearse, apply, check, a run as the new user, rollback
