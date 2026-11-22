# Judge rubric: spec-ACME-14

Read by `evals/check.py` (lib/judge.py) against the run's Playwright spec. A judge vote passes or fails the run on this text alone.

This is a Playwright spec written from these approved Test Steps: 1. Build check [Build check] Compare the org with
the build sub-task's spec (ACME-14-build): the Escalate Case flow and its button, the Tier 2 Escalations list view,
and the Accept button. Flow F1, as Support Agent Test User 2. Open a Support Request, click Escalate, try to finish
without a reason, then pick Technical and finish. Expected: a reason is required, and the case's owner becomes Tier
2 Support. Criterion 1. [Video] Flow F2, as Support Supervisor Test User 3. Open the Tier 2 Escalations list view.
Expected: the case from step 2 is listed. Criterion 2. [Video] 4. Select the case and click Accept. Expected: the
supervisor becomes the case's owner. Criterion 3. [Video] Judge each step after step 1 (step 1, the build check,
isn't in the spec). Pass if every step's assertions check its expected result as written, not something easier (for
example, checking a save button exists when the expected result is that the save is stopped with a message). Fail if
any step's assertions don't prove its expected result.
