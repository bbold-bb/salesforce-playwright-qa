# Judge rubric: steps-ACME-13

Read by `evals/check.py` (lib/judge.py) against the run's QA Test Steps draft. A judge vote passes or fails the run on this text alone.

These are QA Test Steps drafted for story ACME-13, for a person to approve. The story's acceptance criteria are: 1.
A Tier 2 Support queue exists and can own Cases. 2. Support Supervisor Test User is a member of Tier 2 Support. 3.
The Tier 2 Access permission set gives edit access to the Case field Escalation Reason. Judge only the numbered
steps and the Coverage section; notes to the approver are allowed and not judged. Step 1 is the build check: it may
list everything the build sub-task adds, with API names. [Query] steps may name objects, settings and access, since
nothing runs as a user there. Pass if all of these hold: (1) the steps a user performs (in a flow, or tagged [Video]
or [Screenshot]) use plain words a business user would recognise; (2) no step tests something the story's acceptance
criteria don't ask for, such as changing Setup, standard Salesforce behaviour or another story's work (checking by
query that a configured access or setting exists is not changing Setup); (3) each step's expected result matches the
criterion it names. Fail if any one does not hold.
