## Test Steps

1. Build check [Build check]
   Compare the org with the build sub-task's spec (ACME-11-build): the Contact Channel field, its values, the report and the permission set.

Flow F1, as Support Agent Test User
2. Create a Support Request, pick Email as the Contact Channel and save. Expected: it saves with Email. Criterion 1. [Video]
3. Run the Cases by Contact Channel report from Support Reports. Expected: the new case is counted under Email. AC 3. [Video]

4. Query the Support Agent permission set's access to Contact Channel. Expected: edit access. Criteria 4 and 2. [Query]

5. Query the cases created by this round. Expected: one case with Email. criterion 1. [Query]

**Coverage**
- Criterion 1: flow F1, step 2, checked again by step 5.
- Criterion 2: step 1, the build check, which lists every value offered.
- Criterion 3: flow F1, step 3.
- Criterion 4: step 4.
