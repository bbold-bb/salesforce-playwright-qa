# Judge rubric: spec-ACME-16

Read by `evals/check.py` (lib/judge.py) against the run's Playwright spec. A judge vote passes or fails the run on this text alone.

This is a Playwright spec written from these approved Test Steps: 1. Build check [Build check] Compare the org with
the build sub-task's spec (ACME-16-build): the Product Area field, its values against the story's (Hardware,
Software, Billing, Accounts), and that it's required on the Support Request page. Flow F1, as Support Agent Test
User 2. Create a Support Request and leave Product Area blank, then save. Expected: the save is stopped until a
Product Area is picked. Criterion 2. [Video] 3. Pick Accounts as the Product Area and save. Expected: the case saves
with Product Area Accounts. Criterion 1. [Video] Judge each step after step 1 (step 1, the build check, isn't in the
spec). Pass if every step's assertions check its expected result as written, not something easier (for example,
checking a save button exists when the expected result is that the save is stopped with a message). Fail if any
step's assertions don't prove its expected result.
