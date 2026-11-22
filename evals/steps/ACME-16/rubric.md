# Judge rubric: steps-ACME-16

Read by `evals/check.py` (lib/judge.py) against the run's QA Test Steps draft. A judge vote passes or fails the run on this text alone.

These are QA Test Steps drafted for story ACME-16, for a person to approve. The story's acceptance criteria are: 1.
A support agent can pick a Product Area from Hardware, Software, Billing and Accounts when creating a Support
Request. 2. A Support Request can't be saved without a Product Area. Judge only the numbered steps and the Coverage
section; notes to the approver are allowed and not judged. Step 1 is the build check: it may list everything the
build sub-task adds, with API names. [Query] steps may name objects, settings and access, since nothing runs as a
user there. Pass if all of these hold: (1) the steps a user performs (in a flow, or tagged [Video] or [Screenshot])
use plain words a business user would recognise; (2) no step tests something the story's acceptance criteria don't
ask for, such as changing Setup, standard Salesforce behaviour or another story's work (checking by query that a
configured access or setting exists is not changing Setup); (3) each step's expected result matches the criterion it
names. Fail if any one does not hold.
