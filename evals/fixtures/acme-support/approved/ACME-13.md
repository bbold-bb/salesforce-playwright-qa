1. Build check [Build check]
   Compare the org with the build sub-task's spec (ACME-13-build): the Tier 2 Support queue and its supported object, the Escalation Reason field, and the Tier 2 Access permission set.

2. Query the Tier 2 Support queue's supported objects. Expected: Case. Criterion 1. [Query]
3. Query the Tier 2 Support queue's members, through the Support Supervisor role. Expected: Support Supervisor Test User is a member. Criterion 2. [Query]
4. Query the Tier 2 Access permission set's access to Escalation Reason. Expected: read and edit. Criterion 3. [Query]

Coverage
- Criterion 1: step 2, with the queue itself in the build check.
- Criterion 2: step 3.
- Criterion 3: step 4. What this access lets a supervisor do on screen is tested in ACME-14.
