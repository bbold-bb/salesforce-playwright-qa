1. Build check [Build check]
   Compare the org with the build sub-task's spec (ACME-15-build): Priority in the Case Details section of the Support Request page.

Flow F1, as Support Agent Test User
2. Open a Support Request, set Priority to High in Case Details and save. Expected: the case saves with Priority High. Criterion 2. [Video]

Coverage
- Criterion 1: step 1, the build check, which reads the page's Case Details section; flow F1 also shows it on screen.
- Criterion 2: flow F1, step 2.
- Criterion 3: tested in ACME-17, which builds the routing rule.
