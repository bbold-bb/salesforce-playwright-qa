1. Build check [Build check]
   Compare the org with the build sub-task's spec (ACME-11-build): the Contact Channel field and its four values, its place on the Support Request page, the Support Agent permission set's access, and the Cases by Contact Channel report.

Flow F1, as Support Agent Test User
2. Create a Support Request, pick Email as the Contact Channel and save. Expected: the case saves with Contact Channel Email. Criterion 1. [Video]
3. Open the Cases by Contact Channel report from Support Reports. Expected: the new case is counted under Email. Criterion 3. [Video]

4. Query the Support Agent permission set's access to Contact Channel. Expected: read and edit. Criterion 4. [Query]

Coverage
- Criterion 1: flow F1, step 2.
- Criterion 2: step 1, the build check, which compares every value offered.
- Criterion 3: flow F1, step 3.
- Criterion 4: step 4.
