1. Build check [Build check]
   Compare the org with the build sub-task's spec (ACME-16-build): the Product Area field, its values against the story's (Hardware, Software, Billing, Accounts), and that it's required on the Support Request page.

Flow F1, as Support Agent Test User
2. Create a Support Request and leave Product Area blank, then save. Expected: the save is stopped until a Product Area is picked. Criterion 2. [Video]
3. Pick Accounts as the Product Area and save. Expected: the case saves with Product Area Accounts. Criterion 1. [Video]

Coverage
- Criterion 1: flow F1, step 3, with every value compared in the build check.
- Criterion 2: flow F1, step 2.
