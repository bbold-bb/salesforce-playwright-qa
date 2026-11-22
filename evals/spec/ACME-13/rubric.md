# Judge rubric: spec-ACME-13

Read by `evals/check.py` (lib/judge.py) against the run's Playwright spec. A judge vote passes or fails the run on this text alone.

This is a Playwright spec written from these approved Test Steps: 1. Build check [Build check] Compare the org with
the build sub-task's spec (ACME-13-build): the Tier 2 Support queue and its supported object, the Escalation Reason
field, and the Tier 2 Access permission set. 2. Query the Tier 2 Support queue's supported objects. Expected: Case.
Criterion 1. [Query] 3. Query the Tier 2 Support queue's members, through the Support Supervisor role. Expected:
Support Supervisor Test User is a member. Criterion 2. [Query] 4. Query the Tier 2 Access permission set's access to
Escalation Reason. Expected: read and edit. Criterion 3. [Query] Judge each step after step 1 (step 1, the build
check, isn't in the spec). Pass if every step's assertions check its expected result as written, not something
easier (for example, checking a save button exists when the expected result is that the save is stopped with a
message). Fail if any step's assertions don't prove its expected result.
