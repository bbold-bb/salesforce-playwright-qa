# Acme Support: the project

An invented Salesforce Service Cloud project, used only by the QA evals. Nothing here is a real client, person or org.

## The org

- **Cases** have two record types: **Support Request** (the support team's cases) and **Billing Question** (the billing team's).
- **Report folder:** Support Reports.
- **Queues:** Tier 2 Support (built in ACME-13).
- **QA sandbox alias:** `acme-qa`.

## Test users

Each tester has their own set, so a spec names the entry in `personas.json`, never a user.

| Test user | Entry in `personas.json` | Persona | Role | Permission sets |
| --- | --- | --- | --- | --- |
| Support Agent Test User | `SupportAgent` | A first-line support agent who works Support Requests | Support Agent | Support Agent |
| Support Supervisor Test User | `SupportSupervisor` | A supervisor who takes escalated cases | Support Supervisor | Support Agent, Tier 2 Access |

## How QA works here

- Each story has a build sub-task (the spec the admin built from) and a QA sub-task (Test Steps, then a Playwright spec).
- The QA sub-task's Test Steps follow the kit's rules in `docs/writing-test-steps.md`, and the Solution Architect approves them before any script is written.
- The Playwright harness and its spec template are in this project's `qa/playwright` folder when a spec is written.

## The app

Support agents and supervisors work in the **Acme Support** Lightning app, which has the Home, Cases and Reports tabs.
