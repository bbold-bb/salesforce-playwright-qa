# Tech stack

Every tool the QA process uses, what it does, the version it ran on, and what it needs from you. Versions are what the process ran on through 2026-11; newer versions should work, but pin Playwright to the version in `templates/qa/playwright/package.json` until you've rerun a spec on a newer one.

## On your machine

| Tool | What it does in QA | Version used | What it needs |
| --- | --- | --- | --- |
| Claude Code | Reads the tickets, runs the build check, writes and runs the Playwright scripts, reviews the results, drafts the Jira text, and records the cost of each block of work if you use the ledger add-on | 2.1.312, desktop app (Code tab); the CLI works the same | A Claude plan with Claude Code. The process ran on Claude Opus |
| Salesforce CLI (`sf`) | Retrieves metadata and runs SOQL and Tooling API queries for the build check, and gives Playwright a one-time sign-in URL | 2.155.8 | The sandbox authorized under an alias (`sf org login web --alias <alias>`) |
| Node.js and npm | Run Playwright | Node 24.18, npm 11.6 | Nothing beyond the install |
| Playwright (`@playwright/test`) | Rehearses each spec without video until it passes, then clicks through each scenario as a user and records screenshots and videos. A failed rehearsal step saves an accessibility snapshot of every open page. The same package gives the Playwright CLI (`npx playwright cli`) for finding locators on a live page, and the trace reader (`npx playwright trace`) for a failed run | 1.64.1 | `npm install`, then `npx playwright install ffmpeg` for video. It drives your installed Chrome, so no Playwright browser download |
| Google Chrome | The browser Playwright drives | 156 | Installed in `/Applications` |
| Python | The build check, data hygiene audit, evidence index, and the optional QA ledger add-on | 3.12, with Polars 2.1 for data work | Standard library for the templates. Polars for any analysis you add |
| macOS | Runs everything | macOS 27 | Screen Recording and Automation permission only if you use `capture_chrome_window.sh` (see the setup guide) |
| Google Drive for desktop | Syncs the evidence folder, so publishing is a file copy | Current | The shared evidence folder added to your Drive, and its local path in `.drive-dir` |
| Git | Versions the scripts and the build checks | Any | A repo for your project. Evidence, traces and the ledger stay out of it (gitignored) |

## Connectors in Claude Code

| Connector | What it does | Notes |
| --- | --- | --- |
| Atlassian (Jira) | Reads tickets and their approved Test Steps; writes drafted Test Steps, Testing Feedback, the acceptance check and the status, each after the approver approves the exact text | Rich-text custom fields need Atlassian Document Format (ADF) through the API. Descriptions accept markdown. See [gotchas.md](gotchas.md) |
| Google Drive | Finds the link to each published round folder for the Testing Feedback | Read only in this process. The files themselves go through Drive for desktop |

## In the Salesforce sandbox

| Item | Why | Where |
| --- | --- | --- |
| Administrators Can Log in as Any User | Playwright signs in as you through the CLI, then uses Login As to become the test user, so no script holds a password | Setup, Login Access Policies |
| Each tester's own test users, one per persona | Each scenario runs as the person the story is about, with that persona's access, and testers don't see each other's records | `test_users.py` creates them from `playwright/personas.json`, with `example.com` addresses. Needs an admin who can manage users, and a free user license for each. Users are data, so create them in every QA sandbox |
| Access to Send Email | Left at System email only. A step that sends email turns it to All email for the send and back straight after | Setup, Deliverability. Only if a story sends email |
| The app the personas use | Scripts open records in that app, so the video shows what the user sees | Set as the test users' default app, or the test user may land in a different console (see [gotchas.md](gotchas.md)) |

Nothing is installed in the org. The scripts only read metadata, sign in, and create the test users a tester approves and the test records the scenarios need, apart from a step that changes a setting on purpose (such as email deliverability) and sets it back.

## In Jira

The process writes these fields on each QA sub-task. The names below are examples: use whatever your project's screens carry, and rename them in the prompt and templates to match.

| Field | What QA puts in it |
| --- | --- |
| Test Steps | Step 1 the build check, then the steps grouped into flows, each with its user, criterion and evidence tag, then Coverage. Drafted by Claude from the story and approved before any script ([writing-test-steps.md](writing-test-steps.md)) |
| Testing Feedback | The dated build check line, then the final passing round: who it ran as, the result per step, the evidence link, and a link to each test record |
| A criteria-met field, if your project has one (for example "Criteria Met?") | Yes, on a pass |
| Status | Done, on a pass. A failure reopens the build sub-task instead |

## Optional add-on

| Add-on | What it does | Notes |
| --- | --- | --- |
| [QA ledger](../addons/qa-ledger/README.md) | Records every scenario run, round and attempt with its reason, and how long the AI worked on each block of QA and what it would cost at API list price, rolled up by QA sub-task, story, epic and sprint | Python standard library. Its Jira snapshot uses a read-only search. Stays on your machine |
