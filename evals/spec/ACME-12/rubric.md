# Judge rubric: spec-ACME-12

Read by `evals/check.py` (lib/judge.py) against the run's Playwright spec. A judge vote passes or fails the run on this text alone.

This is a Playwright spec written from these approved Test Steps: 1. Build check [Build check] Compare the org with
the build sub-task's spec (ACME-12-build): the Resolution Summary field, and the validation rule's formula, message
and active flag. Flow F1, as Support Agent Test User 2. Open a Support Request, set Status to Closed with Resolution
Summary blank, and save. Expected: the save is stopped with 'Add a Resolution Summary before closing the case.'
Criterion 1. [Video] 3. Fill in a Resolution Summary and save again. Expected: the case saves as Closed. Criterion
2. [Video] Judge each step after step 1 (step 1, the build check, isn't in the spec). Pass if every step's
assertions check its expected result as written, not something easier (for example, checking a save button exists
when the expected result is that the save is stopped with a message). Fail if any step's assertions don't prove its
expected result.
