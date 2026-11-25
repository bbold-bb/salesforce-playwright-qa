# Test users per tester and persona: design

Approved 2026-11-25.

**Why.** Two people running QA in one sandbox share the test users, so each sees the other's records, tabs and changes in their evidence. A team setting up the kit also has no test users yet, and creating them by hand drifts: names differ, a permission set is missed.

**Goal.** A team describes once who it tests as. Each tester runs one command and gets their own set of users, named the same way, holding the same access. Specs name the persona, never a person's user.

**Not goals.** Creating profiles, permission sets or groups (the build does that). Passwords. Production. Copying anyone's existing users into the kit: every persona in it is invented.

## Approaches

| Approach | Trade-off |
| --- | --- |
| **A personas file plus a create script (picked)** | One committed list of access per persona, checked against the org. Works with no users to start from |
| Copy a set of existing users | Needs a correct set to copy from, which a new team doesn't have |
| Each tester types in their own users | Nothing to build, but the sets drift apart |

## Design

- `qa/personas.json`, committed: an entry per person to test as, usually a persona, with the access it holds by name.
- `qa/test_users.py`: plan (the default), `--rehearse`, `--apply`, `--check`, `--rollback`, `--write-settings`, and `--from-user` to start a persona's entry from a user that already exists. Sandboxes only. No password, no email.
- Names: first name `<key>Test`, last name the tester (`SpecialistTest Ana P`). No name may contain another's. `example.com` email and a username unique across Salesforce.
- The plan compares the user and permission set licenses needed with those free, and stops when short.
- `qa/playwright/test-users.local.json`, gitignored, by org: which user stands for each persona on this machine. `testUser('Specialist')` reads it. No entry stops the run with the command to use.
- Evidence records who each step ran as. A recorded round keeps one set of users.

Alongside it, the harness changes since the kit's last update: the run lock covers every run and waits, waiting time is cut from videos, console tabs settle before they're closed, more screen patterns, check the screen before a query, and who reviews a tester's own evidence becomes a setup question.
