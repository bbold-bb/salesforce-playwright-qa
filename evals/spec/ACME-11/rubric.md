# Judge rubric: spec-ACME-11

Read by `evals/check.py` (lib/judge.py) against the run's Playwright spec. A judge vote passes or fails the run on this text alone.

This is a Playwright spec written from these approved Test Steps: 1. Build check [Build check] Compare the org with
the build sub-task's spec (ACME-11-build): the Contact Channel field and its four values, its place on the Support
Request page, the Support Agent permission set's access, and the Cases by Contact Channel report. Flow F1, as
Support Agent Test User 2. Create a Support Request, pick Email as the Contact Channel and save. Expected: the case
saves with Contact Channel Email. Criterion 1. [Video] 3. Open the Cases by Contact Channel report from Support
Reports. Expected: the new case is counted under Email. Criterion 3. [Video] 4. Query the Support Agent permission
set's access to Contact Channel. Expected: read and edit. Criterion 4. [Query] Judge each step after step 1 (step 1,
the build check, isn't in the spec). Pass if every step's assertions check its expected result as written, not
something easier (for example, checking a save button exists when the expected result is that the save is stopped
with a message). Fail if any step's assertions don't prove its expected result.
