1. Build check [Build check]
   Compare the org with the build sub-task's spec (ACME-14-build): the Escalate Case flow and its button, the Tier 2 Escalations list view, and the Accept button.

Flow F1, as Support Agent Test User
2. Open a Support Request, click Escalate, try to finish without a reason, then pick Technical and finish. Expected: a reason is required, and the case's owner becomes Tier 2 Support. Criterion 1. [Video]

Flow F2, as Support Supervisor Test User
3. Open the Tier 2 Escalations list view. Expected: the case from step 2 is listed. Criterion 2. [Video]
4. Select the case and click Accept. Expected: the supervisor becomes the case's owner. Criterion 3. [Video]

Coverage
- Criterion 1: flow F1, step 2.
- Criterion 2: flow F2, step 3.
- Criterion 3: flow F2, step 4.
