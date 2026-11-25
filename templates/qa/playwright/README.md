# Playwright QA scenarios

Click-through QA scenarios for a Salesforce build, run with Playwright. You script a story's scenarios once, then rerun them after every deployment (partial sandbox, then the full sandbox smoke test). Each run leaves the same evidence: what each scenario declares it needs (a screenshot, a video, query output, or a mix), a run summary, and a record of what changed since the last run. With the optional [QA ledger](../../../addons/qa-ledger/README.md) add-on, every run also adds its scenario runs to the ledger.

These scripts show the build behaves right. Whether it was built as specified is a separate check: the build check in the qa folder compares the org's metadata with the build spec.

## What's here

| File | What it is |
| --- | --- |
| [templates/story.spec.ts](templates/story.spec.ts) | The spec to copy for a new story, kept at the current rules: a query step, a flow on video with its opening card, and a screenshot step as a second user |
| [tests/example.spec.ts](tests/example.spec.ts) | A working demo on the standard Case object: one flow of three steps on video, which runs in any sandbox with Cases |
| [lib/config.ts](lib/config.ts) | Project settings: default org alias, the primary org for per-environment tickets, API version, record name prefix, evidence folder, time zone, and whether the ledger add-on is on |
| [lib/salesforce.ts](lib/salesforce.ts) | Org lookups through the sf CLI, sign-in, Login As and switching user, the console tab cleanup, picklist and lookup helpers, the console, related list and record page helpers (see Console and report patterns, below), the report helpers, the URL and list view helpers (see Navigation and list views), the sandbox email switch, and the metadata and Setup Audit Trail reads for the run manifest |
| [lib/evidence.ts](lib/evidence.ts) | Rounds, attempts and rehearsals, the evidence folder, flows and steps, screenshots, video, opening, chapter and caption cards, the rehearsal storyboard and failure snapshots, the run manifest, the run summary and the ledger rows |
| [personas.json](personas.json) | Who the specs test as and the access each holds (see Test users) |
| [lib/testUsers.ts](lib/testUsers.ts) | This machine's user for each persona, and the check that they exist before any spec starts |
| [lib/runLock.ts](lib/runLock.ts) | The lock every run takes before any spec starts, so only one goes at a time |
| [lib/videoCuts.ts](lib/videoCuts.ts) | Marks the waits in a video and cuts them once the run ends |
| [playwright.config.ts](playwright.config.ts) | Installed Chrome, one worker, scenarios in order, Playwright's own videos and screenshots off, traces kept for failed tests only, in a folder per run that's never cleared |

## First-time setup

1. Install Node.js 20 or later.
2. From this folder, run `npm install`.
3. Run `npx playwright install ffmpeg` for video. It's Playwright's own small build, about 1.4 MB.
4. Install Google Chrome. The scripts use your installed Chrome, so no Playwright browser is downloaded.
5. Authorize the sf CLI to the sandbox under an alias: `sf org login web -a my-partial-sandbox -r https://test.salesforce.com`. Set that alias as the default in `lib/config.ts`, or pass `SF_ORG` on each run.
6. In the sandbox, turn on **Administrators Can Log in as Any User** (Setup, Login Access Policies).
7. Say who you test as in [personas.json](personas.json), then create your own test users with [test_users.py](../test_users.py) (see Test users, below). The two entries it ships with are examples on the Standard User profile.
8. Check the app the persona uses. Log in as the test user once and open that app, or pass `appPath(...)` to `signInAs` as the example does.

This folder has its own `package.json`, so it doesn't disturb any npm toolchain at the repository root.

## Signing in

There are no passwords anywhere. Each run signs in as the sf CLI's admin user with a one-time URL from `sf org open --url-only`. It then uses Login As to become the test user (see Test users, below), and confirms the switch from Lightning's own current user. It goes straight to the page the scenario starts on, so the video never shows Home or a list view. Nothing about the session is saved to disk, and a one-time sign-in URL in an error message is removed before it reaches the evidence.

Queries run through the sf CLI as the admin. Use them to confirm what the test user did, never to decide what the test user can see.

## Test users

Each tester has test users of their own, one for each person they test as. Two people testing in one sandbox then don't see each other's records, tabs and changes, and the evidence shows whose users tested.

**Who to test as: [personas.json](personas.json).** Committed and shared by the team. An entry is usually a persona, but it can be anyone a story needs: a specialist with an add-on, a person with no access. It lists the access that person holds, by the names the org uses:

```json
{
  "defaults": { "TimeZoneSidKey": "America/New_York", "LocaleSidKey": "en_US", "LanguageLocaleKey": "en_US", "EmailEncodingKey": "UTF-8" },
  "personas": {
    "Agent": {
      "description": "Works Support Requests. Base access only, so the plain persona gets tested",
      "profile": "Standard User",
      "permission_set_groups": ["Support_Agent_Role"],
      "public_groups": ["Support_Team"]
    },
    "AgentBilling": {
      "description": "An agent with the billing add-on",
      "profile": "Standard User",
      "permission_set_groups": ["Support_Agent_Role"],
      "permission_sets": ["Billing_Addon"],
      "queues": ["Billing"]
    },
    "Supervisor": {
      "profile": "Standard User",
      "role": "Support_Supervisor",
      "permission_set_groups": ["Support_Supervisor_Role"],
      "user": { "UserPermissionsKnowledgeUser": true }
    }
  }
}
```

| Key | What it names |
| --- | --- |
| `profile` | The profile, by name. Required |
| `role` | The role, by developer name |
| `permission_set_groups`, `public_groups`, `queues`, `permission_set_licenses` | Each by developer name |
| `permission_sets` | Each by API name |
| `user` | User fields that differ from `defaults`: time zone, locale, language, email encoding, and the Knowledge, Service Cloud, Flow and Marketing user checkboxes |

To start an entry from a user that already holds the right access, print one: `python3 test_users.py --org my-partial-sandbox --from-user "Some User" --as Agent`. It prints access only, no one's name or email. Read it before you add it.

**Create your set**, from the qa folder, with your own name:

```bash
python3 test_users.py --org my-partial-sandbox --tester "Ana P"
python3 test_users.py --org my-partial-sandbox --tester "Ana P" --rehearse
python3 test_users.py --org my-partial-sandbox --tester "Ana P" --apply
python3 test_users.py --org my-partial-sandbox --tester "Ana P" --check
```

The first only reads, and shows the plan. `--rehearse` creates everything and undoes it. `--apply` creates it in one transaction and writes this machine's settings. `--check` compares the users with the file. `--rollback` deactivates the set and removes its access, since Salesforce users can't be deleted; `--apply` brings it back. `--persona Agent` limits any of them to one entry.

| Part | What the script gives it |
| --- | --- |
| Name | `<entry>Test <tester>`: `AgentTest Ana P`. No test user's name may hold another's, since some checks match part of a name, so an entry can't end with another entry's name either |
| Username | Made from the entry, the tester and the org's ID, so it's unique across Salesforce |
| Email | `agenttest.anap@example.com`, never a real inbox. No password is set and no email is sent |
| Licenses | The plan counts what the set takes against what's free and stops when short. Every tester takes a user license per entry, so a small sandbox can run out |

**A spec names the entry, never a user:** `testUser('Agent')` ([lib/testUsers.ts](lib/testUsers.ts)) gives this machine's user, from `test-users.local.json`, which `--apply` writes (`--write-settings` writes it alone, on a second machine). It's gitignored and goes by org:

```json
{ "my-partial-sandbox": { "Agent": "AgentTest Ana P", "Supervisor": "SupervisorTest Ana P" } }
```

- **No set, no run.** An org with no entry, or a user the org doesn't have, stops the run before any spec starts and says what to run. It never falls back to someone else's user.
- **Test Steps on a ticket name the persona,** so any tester can run them. The run summary (Signed in as, and Ran as on each step), `ran_as` in the evidence index, the run manifest and the cards name the user who ran them, and Testing Feedback's "ran as" does too.
- **A recorded round keeps one set.** Its records belong to the users who made them, so another attempt with other users stops. A rehearsal may change sets.
- **Rehearse after creating or changing a set.** New users start with fresh list view and console settings, and no default app.
- **After a build changes a persona's access,** update `personas.json`, then each tester runs `--apply` and `--check`. `--apply` adds what's missing and never removes access the file doesn't list; `--check` reports it.
- **Users don't move with a deployment.** Create the set again in each sandbox, and after a refresh.
- **Still shared, whoever's users run:** org-wide settings such as email deliverability, and any config record a test changes for a run. The lock covers one machine only, so agree with the other testers before a run that does either.

## Run it

From this folder, give the round you're running and why:

```bash
QA_ROUND=R0 QA_REASON=rehearsal npm run qa -- PROJ-21
QA_ROUND=R1 QA_REASON=first-run npm run qa -- PROJ-21
QA_ROUND=R2 QA_REASON=retest-after-fix QA_NOTE="PROJ-20 reopened: message reworded" npm run qa -- PROJ-21
```

The last argument picks the spec file by name. Name each spec after its QA sub-task, such as `tests/PROJ-21.spec.ts`.

| Setting | Default | What it does |
| --- | --- | --- |
| `QA_ROUND` | none, required | The round: `R1`, `R2` and so on. It goes into the test records' names and the evidence folder. `R0` is the rehearsal round |
| `QA_REASON` | none, required | Why this run is happening. A new round: `first-run`, `retest-after-fix`, `story-changed`, `regression-after-deployment`. Another attempt in the same round, with nothing under test changed: `script-fix`, `steps-changed` when the approved Test Steps changed and the script followed them, `flaky`, or `tooling-check` for a run that only checks the QA tooling after a change to it (kept in the evidence, left out of the ledger report's figures). A practice run before the recorded one: `rehearsal`, with `QA_ROUND=R0` (see Rehearse first, below) |
| `QA_NOTE` | empty | A short note on what changed or why, for the run summary and the ledger |
| `SF_ORG` | `my-partial-sandbox` (set in `lib/config.ts`) | The sf CLI alias of the org to test, for example `my-full-sandbox` |
| `QA_VIDEO` | on | `QA_VIDEO=0` skips the video and its pauses, for a fast run with screenshots only. A rehearsal never records video |
| `QA_HEADED` | off | `QA_HEADED=1` shows the browser window while it runs |
| `QA_TRACE` | failures only | A trace is kept for a test that fails. `QA_TRACE=on` keeps one for every test (see When a run fails, below) |
| `QA_LEDGER` | off | `QA_LEDGER=1` writes ledger rows and reads the ledger's Jira snapshot. Needs the [QA ledger add-on](../../../addons/qa-ledger/README.md) |
| `QA_EVIDENCE_DIR` | `evidence/` in the qa folder, beside this one | Where the evidence goes. The build check, evidence index, publish script and ledger read the same folder |
| `QA_TZ` | `UTC` | The time zone for dates in folder names, the run summary and the ledger |
| `QA_WAIT` | `30` | The most minutes to wait while another run holds the lock. `QA_WAIT=0` stops at once (see One run at a time, below) |
| `QA_PRIMARY_ORG` | `my-partial-sandbox` | The org whose QA sub-tasks the specs name, when each environment has its own (see Rounds and attempts) |
| `SF_API_VERSION` | `62.0` | The API version for UI API calls |

## Rounds and attempts

A **round** is one pass of QA on one version of the build: the first run, a retest after a build fix, a run after the story changed, or a regression run after a deployment. Each round gets its own folder.

An **attempt** is another try within a round when nothing under test changed: the script was fixed, the approved Test Steps changed, a step was flaky, or the run only checks the QA tooling. Pick scenarios with `--grep`:

```bash
QA_ROUND=R2 QA_REASON=script-fix npm run qa -- PROJ-21 --grep F1
```

The run stops before it starts if the reason doesn't fit the round. A new-round reason on a round that already ran stops it, and so does an attempt reason on a round that hasn't run. An attempt never overwrites earlier evidence: the earlier files move to `attempts/A<n>/` first.

Records a scenario creates stay in the org as the record of the test. Decide per scenario how a later attempt treats them. The template adds the attempt to the name when the name is taken. A scenario whose records must exist once per round should stop instead if that round's records already exist.

A step taken off the Test Steps since an earlier attempt is passed to `finishRun` in `extra.dropped`, so the round's results, evidence index and shared summary carry only the steps on the ticket; its history stays in `results.json`. A step renumbered onto an ID an earlier attempt used for another step starts its own history.

**One QA sub-task per environment.** If each environment has its own QA sub-task with the same Test Steps, a spec names the primary org's ticket through `qaTicket('PROJ-21')`, and `environment-tickets.json` in the qa folder maps it for the other orgs: `{ "my-full-sandbox": { "PROJ-21": "PROJ-121" } }`. In the full sandbox the run then names its records and files its evidence under that ticket. Without the file, a spec's ticket is used in every org.

## Rehearse first

A new or reworked script is rehearsed until every step passes, and only then recorded:

```bash
QA_ROUND=R0 QA_REASON=rehearsal npm run qa -- PROJ-21
```

A rehearsal runs without video, so it goes at full speed. Its screenshots, query output, run summary and manifest go to `evidence/rehearsal/<QA sub-task>/`, apart from every round, and `publish.sh` refuses that folder. Its records are named with `R0`, so they never collide with a real round's or show in a count filtered on a round's record names; like every test record they stay in the org. Each rehearsal of a script is the next attempt in its `R0`, so "the first attempt creates the records" works as it does in a real round. With the ledger on, its scenario runs go into the ledger with the reason `rehearsal` and are left out of the report's figures, as tooling checks are. Finding out how a screen behaves belongs here, not in a recorded round.

A rehearsal also leaves three things a recorded round doesn't:

| What | Where | For |
| --- | --- | --- |
| A failure snapshot | `failures/A<n>-<step>.aria.yml` and `.png`, one pair per open page | What each page showed when a step failed: its address, then the role and name of everything on it, frames included, which is what role and label locators match. Read the fix from it (search it for the label; don't read it whole) before opening a trace or running again. A spec that opens a browser context itself, such as a visitor's page, passes it through `trackContext` so it's included |
| The storyboard | `storyboard.md`, rewritten each rehearsal | Every opening card, step card, caption and screenshot in the order a viewer meets them. Whoever approves the Test Steps approves the wording and the screenshot framing from it before the recorded run, so nothing is recorded again for wording |
| A stop line | Printed at the end of the run | A step that has failed three rehearsals in a row. It isn't tried again: it goes to the approver with what the page showed and the options, such as another way to do the step or proving it by query |

**Tab cleanup.** Before recording, a run closes every console tab that isn't one of this ticket's records: a Case whose Subject holds "QA <ticket>", or a record whose tab label does. Console tabs carry over between sessions, so a new ticket's video starts clear and shows only its own records, with nothing left from another ticket's run or from real data copied into the sandbox. The console restores tabs one by one, so the cleanup first waits until none is loading and the list has stopped changing. `openRun` tells `closeNonTestTabs` the ticket.

**One run at a time on a machine, rehearsal or recorded.** Runs from two sessions share this machine's test users, so each would see the other's records, tabs and changes. Every `playwright test` command takes a lock (`evidence/.recording.lock`) before any spec starts and gives it up when the command ends. It's Playwright's global setup ([lib/runLock.ts](lib/runLock.ts)), so it covers every spec. A run that finds it held names the run that holds it, repeats that once a minute, and waits for up to 30 minutes (`QA_WAIT`); then it stops before any spec starts. `QA_WAIT=0` stops at once. Waiting runs go in no set order, and there is one lock for every org. A lock left by a run that died is taken over, so never delete it. Two testers on two machines don't wait for each other, because each has users of their own (Test users, above). Each run keeps its traces in its own folder.

## Email sending

A sandbox usually keeps Access to Send Email at System email only, so a send from a record is refused. A step that sends an email wraps the send in `withEmailOpen(browser, why, send)` (`lib/salesforce.ts`): it turns email to All email right before the send and back straight after, on Setup's Deliverability page in a browser context of its own, so it's never in the video. Rehearsals and recorded rounds both do this. Each window is timed; the spec calls `closeEmailIfOpen` in `afterAll` and passes `emailTotals()` to `finishRun` as `extra.email`, so the run summary keeps each attempt's time in its note and a total for the round, and the Testing Feedback can report the total time email was on. Send only to `example.com` addresses or to test users.

## Evidence

Everything a run produces goes to the qa folder's `evidence/`, which is gitignored. Run output captures org pages, which can include real data copied into a sandbox.

```
evidence/
  qa-ledger/                              the optional QA ledger; stays on this machine
  rehearsal/                              practice runs, one folder per QA sub-task; stays on this machine
  E1 Example Epic/                        one folder per epic
    PROJ-21 E1.1 Example Case intake/     one per QA sub-task, with its newest build check once published
      2026-01-05 my-partial-sandbox R2/   one per round: date, org, round
        screenshots/  PROJ-21-S2.png, PROJ-21-S5a.png ...   the latest attempt's
        videos/       PROJ-21-F1.webm                       one per flow or standalone scenario
        queries/      query output, for scenarios where nothing runs as a user
        evidence-index.csv                what each scenario needs and has (written by ../evidence_index.py)
        attempts/A1/  earlier attempts' screenshots and videos, never overwritten
        run-manifest-A2.json              what was under test, one per attempt
        results.json                      every attempt and every scenario's history
        run-summary.md
```

- **Evidence per scenario.** Each scenario in `SCENARIOS` declares `evidence`: `screenshot` for what a user sees at one moment with no process to follow (report totals, a list view), `video` where the proof depends on actions or a rule firing (a save blocked, a record created end to end), or `query` where nothing runs as a user (save it with `saveQuery`). A scenario with a video doesn't also declare a screenshot, and not every scenario needs a video. How to choose is in [Writing Test Steps](../../../docs/writing-test-steps.md). `evidence-index.csv` lists what each scenario needs and has, and publishing stops on anything missing.
- **Screenshots** are named by ticket and scenario. A scenario that covers several records gets one per record, lettered (S5a, S5b), and the run summary says which is which. A screenshot is full page when the page is at the top. When the page has scrolled, or a picklist is open, it's the visible window, because Lightning's fixed header lands mid-image in a full-page capture of a scrolled page.
- **Videos** are one per flow or standalone scenario that declares one, slowed to a pace a person can follow. Each flow video opens with its opening card, then a chapter card per step, and a pointer and outline mark each element as it's used. The format is WebM with VP9, which Chrome plays. Check that your shared storage's preview plays it before you rely on it.
- **Dead time is cut from a video.** Wrap a wait that's nothing to watch in `waiting(() => ...)` ([lib/videoCuts.ts](lib/videoCuts.ts)): mail arriving, a page loading. The email switch marks its own. Once the run ends, each marked wait is cut to a second at each end; cards, results and the time Salesforce takes after a click stay whole. Never wrap the step's own action or result. The run summary says how much was cut, and the uncut video stays on this machine in `attempts/A<n>-uncut/`. It needs `ffmpeg` on the path (`brew install ffmpeg`); without it the video stays as recorded.
- **The run summary** lists every attempt in the round with its reason and note, each scenario's result and its attempts, what changed before the latest attempt, what was seen, and links to the records used, ready for the Testing Feedback entry.
- **The run manifest** records, for each attempt: the script's commit and any uncommitted edits, the Jira items' last update and sprint (from the ledger's Jira snapshot, when the ledger is on), the build's metadata as the spec collects it, and the org's Setup changes since the last run of the same QA sub-task (Setup Audit Trail, user management left out). It compares that with the last run and lists what differs. That list tells a build change from a script change.
- **Sharing.** Watch the videos first; each should show its scenario clearly and only test records. Then, from the qa folder, run [`publish.sh`](../publish.sh) with the round's folder. It runs [`evidence_index.py`](../evidence_index.py) to check every scenario has the evidence it declares, then copies the round's final evidence and the QA sub-task's newest build check into the Drive folder that Google Drive for desktop syncs, and never deletes anything there. Earlier attempts, run manifests, `results.json` and the ledger stay on this machine, and the shared run summary leaves out the attempts and the test tooling ([shared_summary.py](../shared_summary.py)). Link the QA sub-task's Drive folder from its Testing Feedback entry.

## Keeping a script working

Scripts find fields and buttons by their label and name ("Case Origin", "Save", "Edit Case Origin"), the way a person reads the screen. They find records by name or developer name, never by Id, so a script runs in any sandbox. They never use a position on the page or Salesforce's internal page code. So most build changes need nothing, and a failed run stops at the step it couldn't do and names it in the run summary. Every scenario also checks its result by query, so a broken script fails rather than passing.

| Change | What the script needs |
| --- | --- |
| Fields moved between sections or columns, sections reordered, fields added, record page components rearranged, report moved to another folder | Nothing |
| Salesforce's routine release updates | Usually nothing. If releases keep breaking label lookups, Salesforce's UTAM is the fallback |
| A label renamed (Case Origin to Channel), a validation message reworded, picklist values added, removed or renamed, a record type, test user or report renamed | A one-line edit. A run on the old value fails, which is right when the story set the value |
| How the user does a step changes: create through a quick action, Flow or custom component instead of the standard New form; a new field required on save; inline edit removed; a different app; Login As unavailable in the org | Rework that scenario, usually under an hour. A new required field showing up here is what rerunning after deployments is meant to catch |
| A new story, or most of a story's acceptance criteria or Test Steps rewritten | A new script, or new scenarios in the existing one |

## Console and report patterns

How a Lightning console app and reports behave under a script. Each has a helper in [lib/salesforce.ts](lib/salesforce.ts); use the helper rather than working it out again, and add a row when a new story turns up another.

| What happens | Helper |
| --- | --- |
| New on a related list opens the form as a console subtab of the record, not a modal. A narrow related list can keep New under its "Show actions" menu instead of showing the button | `newFromRelatedList` uses the button or the menu and returns the form; fill it with `pickValue` and `pickLookup` scoped to the form |
| A lookup field needs the name typed, then the suggestion chosen by its title | `pickLookup` |
| Saving from a related list opens the new record in a subtab of its own, which Lightning re-renders while it loads, so a single close often misses | `closeSubtab` retries until the tab is gone |
| With one record left open the console hides the subtab bar | `selectSubtab` does nothing when the tab isn't shown |
| The console keeps earlier records in the page, hidden, so a related list can match twice | `relatedList` takes only the visible one |
| Related-list cells render in shadow DOM, so cells can't be read one by one | `relatedRow` matches a row by its first column (the user or record name) and other text in the row; `rowAction` opens its menu |
| An enhanced related list in a narrow column draws each record as a card, not a table row | `relatedRow` also matches the card: an article named for the record, with the text matching one of its values exactly |
| A new user's console opens a list in split view, sometimes drawing nothing, and offers Table as a radio or a checkbox item | `goTo` and `listSearch` call `tableView`, which turns split view off and reloads once if the list never draws, waits for a grid, then picks Table either way |
| A user's list opens the way they last left it. In Split View there's no named grid and no row menu, so a search finds nothing | `tableView`, called by `goTo` and `listSearch`, switches it to Table first |
| A picklist reports itself open before its options take a click | `pickValue` waits for the option, scrolls to it, and reopens the list once if the click doesn't land |
| A report runs inside the Report Viewer frame | `openReportFromFolder` opens it through All Folders and waits for Total Records; `reportViewer` for a report opened another way; `reportTotal` reads its total |
| A report groups on a lookup's field under the lookup's name, such as "Owner: Full Name", not the field label | Check the grouping by that name |
| A report draws its rows as they scroll into view, so a later group isn't on the page yet; each group cell is named "<grouping>: <value>" | `hideDetailRows` switches Detail Rows off (not saved) so every group shows; `reportGroup` finds one |
| A report's date range is changed on its run page from the Filters panel: each filter is a button "Edit Filter <field> <value>", and the date one opens "Filter by <field>" with a Range text box listing ranges such as This Month. A tabular report shows no Total Records, so `openReportFromFolder` waits for it in vain: open it by `reportPath` and wait for its grid | `setReportDateRange` |
| A report's run page draws its rows as you scroll, so a row near the end of a long report isn't on the page and `getByText` never finds it | `scrollReportTo(grid, text)` |
| A screen flow's radio group and checkbox group draw a box over each input that takes the pointer: `check()` and a mouse click at the input's spot both leave it unchanged | `pickAnswer` and `tickItem` click the words, as a person does, and confirm the result |
| A validation rule whose message sits on a field on another tab shows on save only as a pop-up naming the field; the message itself shows once that tab is opened | Close the pop-up and open the tab |
| An org query holds up the recording while it runs, so the step before it looks slow | Wait for the result on screen first, `beat`, then query |
| The text to check can be on more than one page: a console keeps earlier records in the page behind, and a record can repeat an email's text | Check it in the page or frame it belongs to, such as the email's own frame |
| A flow screen's data table with one-row selection draws its own radio over the real one, which takes the click; a click at the radio's spot only focuses the cell, and the table selects the row on Space | Click the radio's position with the mouse, press Space if it isn't checked, and confirm `toBeChecked` |
| Setup's Deliverability page runs inside a frame, and a Lightning pop-up can cover the frame's Save | `setEmailAccess` works inside the frame, saves, then reloads and reads the saved value back rather than trusting the click |
| A Dynamic Forms section hidden by a visibility rule isn't rendered at all | `recordSection` finds a section by its heading; `toHaveCount(0)` means the record type doesn't show it |
| Change Record Type opens "Change <object> Record Type": each radio is the type's label followed by its description, the current type is disabled and another is preselected, then Next leads to an edit form to save | `changeRecordType` clicks the chosen radio by mouse, since its real input is a hidden 1 by 1 pixel element `check()` can't act on, and confirms it's checked before Next |
| New with the record type check shows the record type chooser; plain `/new` skips it and uses the user's default type | `recordTypeChooser` returns the types offered and the one selected; `chooseRecordType` picks one |
| A field's inline edit pencil on a long Dynamic Forms page can be drawn late, so a plain click sometimes times out even after the record has opened | `editFieldInline` brings the section into view and retries until the pencil is there. On a short page, `startInlineEdit` |
| Change Owner searches Users until Queues is picked, and offers only queues that take the record's object: a queue set up only for another object doesn't appear | `changeOwnerToQueue` |
| Login As can report net::ERR_ABORTED while it still completes, the "Logged in as" banner doesn't always render, and Login As run again as the test user lands in Classic | `signInAs` runs it once and confirms the switch from Lightning's current user, repeating only while the page is still the admin |
| "Log out as" and `/secur/logout.jsp` end at the login page, so one tab can't go back to the admin that way. A fresh one-time URL can, and one video can then follow several sign-ins | `switchUser` |
| A permission set given through the API didn't show its record type at the next Login As in the same browser, because Lightning reused the object info it keeps in browser storage; in a fresh browser it showed | `clearOrgBrowserData` before `switchUser` |
| Command Center for Service has no `/lightning` path: `/lightning/page/omnisupervisor` gives "Page doesn't exist". It opens from its link in the app's navigation, whose address is `/one/one.app#...`. For a user without the tab there's no link, and that address stops on a "Loading..." tab | The link by role and name |
| Whether an action (Delete, say) is offered on a record page | `recordActions` lists the buttons and the overflow menu's items |

## Navigation and list views

Open a page by URL whenever getting there isn't what the step tests, so the step doesn't depend on the App Launcher, the list view switcher or scrolling. Each path helper looks its target up by developer name or label, so it works in any sandbox; pass the path to `signInAs` or, once signed in, to `goTo`.

| What happens | Helper |
| --- | --- |
| An app opens by its AppDefinition ID; a console app reopens on the last workspace tab it had | `appPath('My_Service_Console')` (developer name or label), then `expectApp` |
| A list view opens with `filterName`, which takes its ID or developer name | `listViewPath('Case', 'AllOpenCases')` |
| A report or record opens by its ID | `reportPath`, `recordPath` |
| A list view's grid is named after the list view ("All Open Cases") | `listGrid` |
| The list's search box ("Search this list...") narrows the rows. Searching the round's record prefix ("QA PROJ-21 R2") leaves only that round's records | `listSearch` waits until every row matches |
| A list view's column headers have zero height, so they never count as visible; its "Sort by: <column>" buttons do | Check a column with `grid.getByRole('button', { name: 'Sort by: Date/Time Opened' })` |
| Row checkboxes are labelled by position ("Select Item 2"), not by record | `listRow(grid, 'QA ...').getByRole('checkbox')` |

## When a run fails

**A failed test keeps a Playwright trace** in `test-results/<ticket> <round> <start time>/<test>/trace.zip`: each action with its timing and locator, the page's DOM and accessibility snapshots, the console and the network. Every run gets its own folder and none is cleared, so traces stay on this machine for later troubleshooting. They're gitignored and never published or copied to Drive, because they hold the session. Delete old run folders yourself when you no longer need them. The trace's filmstrip is off, because it would start a screencast of its own and take over the evidence video.

In a rehearsal, read the failure snapshot first (Rehearse first, above): it usually holds the fix.

Read a trace from the command line, yourself or through Claude (the `playwright-trace` skill in the kit's `templates/claude-skills/`):

```bash
npx playwright trace open "test-results/<run>/<test>/trace.zip"
npx playwright trace errors
npx playwright trace actions
npx playwright trace console
npx playwright trace close
```

`trace snapshot` needs Playwright's own headless browser, which the harness doesn't install. To see the page itself, open the zip at trace.playwright.dev in Chrome, which reads it on your machine and uploads nothing.

**Steps show in the trace and the report by scenario.** `step()` runs each flow step as a boxed `test.step` named `S<n> <title>`, so a failure points at the step in the spec rather than inside a helper.

**Finding a locator on a live page:** the Playwright CLI (`npx playwright cli`, part of the `playwright` package, so nothing else to install) opens the installed Chrome in a named session, signed in with the sf CLI's one-time URL, and `find`, `snapshot` and `generate-locator` show the accessibility names that role and label locators match. `recording-start` and `recording-stop`, in a `--headed` session, print the clicks a person makes as Playwright code, to rewrite with the helpers before it goes into a spec. It saves page snapshots to `.playwright-cli/`, which is gitignored; delete the folder and the session's data (`close`, then `delete-data`) when done. The `salesforce-playwright-qa` skill has the sign-in command. QA sandbox only.

## Adding a story

Write and approve the QA sub-task's Test Steps first: how to draft them from the story, the Coverage section, keeping steps simple, evidence tags and grouping steps into flows are in [Writing Test Steps](../../../docs/writing-test-steps.md). The script then implements the approved steps as written. The mechanics:

1. Copy [templates/story.spec.ts](templates/story.spec.ts) to `tests/<QA sub-task>.spec.ts` and keep its shape, not an older spec's, which may predate a rule. When a rule here changes, the template changes in the same commit.
2. Fill in its settings block: `TICKET` (through `qaTicket`), `PARENT` (its story or Task), `EPIC_FOLDER`, `TICKET_FOLDER`, who it runs as (`testUser('<entry in personas.json>')`), and what the story builds, by label and API name.
3. List the steps in `SCENARIOS`, in the ticket's words, each with the evidence tag the ticket gives it. Steps in a flow carry `flow: 'F<n>'`.
4. Have `buildSnapshot` collect the metadata the story builds, so the next run can say what changed.
5. Write the tests: `openRun` and `writeManifest` in `beforeAll`, then one test per flow (`startFlow`, `signInAs`, `startVideo`, `openingCard`, then a `chapter` and `step` per step, and `stopVideo`) or per standalone step (`standalone('S<n>')`, `step`, and `shot` or `saveQuery`), and `finishRun` in `afterAll`.
6. Rehearse it (`QA_ROUND=R0 QA_REASON=rehearsal`) until every step passes, get the storyboard approved, then record it once.

**Flows.** A flow is one user's session through several steps end to end, recorded as one video, `<ticket>-F<n>.webm`. Each step runs inside `step(...)` and keeps its own result; a step that fails stops the rest of the flow, which show as not run until the flow is rerun. A step that stands alone (a different user, or one that needs its own records) is its own test.

**Cards.** Every flow video opens with `openingCard`: the ticket and its title, what the video shows, the steps it covers, who it runs as, and the org and round, so a reader who opens one video on its own knows what it is about. It says only what this video covers: no count of videos and no pointer to other videos or evidence. Each step's `chapter` card then reads "Step 3 of 5: ...", and `caption` adds a short card inside a step.

**Records.** Name the records a script creates `QA <ticket> <round> S<n> <what>`, look records up by name or developer name rather than Id so it runs in any sandbox, and leave them in the org. Use `example.com` for any email address it enters. Confirm every step's result by query, and say so in `seen`.

When the label on the page differs from the story's wording (a relabelled standard field can keep its old label on the form), the script uses the label the user sees. Say so in the spec's header comment.
