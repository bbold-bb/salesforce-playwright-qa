# Setup guide

This guide takes you from a fresh Mac to a first rehearsed and recorded scenario against your sandbox, then sets up the build check, publishing and, if you want it, the cost ledger. Each part ends with how to confirm it worked.

Parts 1 to 5 get you to a first recorded scenario. Parts 6 to 9 can wait until you're scripting a real story. Before you script a real story, answer [project-questions.md](project-questions.md) (the starter prompt has Claude interview you) and read [writing-test-steps.md](writing-test-steps.md): the Test Steps are approved before any script is written.

## Before you start

### Access to ask for

- [ ] A Claude plan that includes Claude Code (Pro, Max, Team or Enterprise)
- [ ] System Administrator on the sandbox you'll test in
- [ ] Jira access to the project, if Claude will read and write the QA sub-tasks
- [ ] Edit access to the team's evidence folder in Google Drive, if you'll publish evidence there

### Install

| Tool | How to install | Check it worked |
| --- | --- | --- |
| Claude desktop app | Download it from [claude.com/download](https://claude.com/download) and sign in | The **Code** tab opens |
| Git | `xcode-select --install` | `git --version` |
| Node.js 20 or later | The macOS installer from [nodejs.org](https://nodejs.org) | `node --version` |
| Salesforce CLI | `npm install --global @salesforce/cli` | `sf --version` |
| Python 3.12 | The macOS installer from [python.org](https://www.python.org/downloads/) | `python3 --version` |
| Polars | `python3 -m pip install polars` | `python3 -c "import polars"` prints nothing |
| Google Chrome | [google.com/chrome](https://www.google.com/chrome/) | Opens from Applications |
| Google Drive for desktop (optional) | [google.com/drive/download](https://www.google.com/drive/download/) | Drive shows in Finder's sidebar |

### Get the kit

- [ ] Clone this repo (`git clone <this repo's URL>`) into a folder next to your project, or download it as a zip from GitHub

## 1. Set up Claude Code

The desktop app includes Claude Code, so there's nothing else to install for it.

1. Open the Claude app and click the **Code** tab.
2. Under the prompt box, choose the **Local** environment, then click the folder control, select **Open folder…**, and choose your project's folder.
3. Click **+** next to the prompt box, select **Add folder**, and choose the kit's folder, so Claude can read the kit and copy its templates.
4. Click **+** again and select **Add connectors**. Connect **Atlassian** for Jira and **Google Drive**. If the menu shows **Connectors**, select it, then **Browse connectors**.

To confirm, ask Claude "Can you see the kit folder and my Jira project?" It should list the kit's files and find a ticket in your project.

If you'd rather use the terminal, install the CLI with `curl -fsSL https://claude.ai/install.sh | bash`, then run `claude` in your project's folder.

## 2. Authorize the sandbox

1. Run `sf org login web --alias my-partial-sandbox --instance-url https://test.salesforce.com`, and sign in in the browser window it opens. Use your own alias; the templates read it from `SF_ORG`.
2. Run `sf org display --target-org my-partial-sandbox`.

The display shows your username and a Connected status. Every script uses this session, so nothing stores a password.

## 3. Prepare the sandbox

1. In Setup, enter **Login Access Policies** in Quick Find, select **Administrators Can Log in as Any User**, and save.
Test users come after the templates are copied (part 5).

## 4. Copy the templates into your project

1. Copy `templates/qa/` into your project, for example as `qa/`. The Playwright runner is inside it, in `qa/playwright/`, and everything shares `qa/evidence/`.
2. Check that the copied `.gitignore` files cover `evidence/`, `test-results/`, `.playwright-cli/`, `.drive-dir` and `node_modules/`, so evidence, traces and installs stay out of git.
3. Set your answers from [project-questions.md](project-questions.md) in the config blocks: the org alias, the time zone, the record prefix, the Jira project key, who you test as (`playwright/personas.json`), the app name and the epic folder. The starter prompt in [starter-prompt.md](starter-prompt.md) has Claude do this with you.
4. Copy the folders in `templates/claude-skills/` into your project's `.claude/skills/`. Claude Code finds them in the next session it starts: the QA skill points it at the harness's helpers and rules, and the two Playwright skills cover the CLI and reading traces. Fill in the harness path and the sandbox alias in `salesforce-playwright-qa/SKILL.md` (they're in angle brackets). See [templates/claude-skills/README.md](../templates/claude-skills/README.md).

## 5. Create your test users

Each tester has users of their own, named for them, so two people can test in one sandbox. How it works is in [templates/qa/playwright/README.md](../templates/qa/playwright/README.md), Test users.

1. Fill in `qa/playwright/personas.json`: one entry for each person the stories are about, with the access that person holds. Keep one entry on a persona's base access only, so the plain persona gets tested. To try the kit first, leave the two examples as they are.
2. From `qa/`, read the plan: `python3 test_users.py --org my-partial-sandbox --tester "<your name>"`. It stops if the org doesn't have something the file names, or if there aren't enough licenses.
3. Run the same command with `--rehearse`, which creates everything and undoes it, then with `--apply`, then with `--check`.
4. From the Users list, click **Login** next to one of your test users. If the **Login** link shows, Login As is on. Open the app the stories expect, so it's the one the user lands in, and log out back to your admin user.

Commit `personas.json`. The other testers start at step 2, each with their own name. `test-users.local.json` is this machine's own and stays out of git.

## 6. Run the example spec

1. From `qa/playwright/`, run `npm install`.
2. Run `npx playwright install ffmpeg`. This is Playwright's own build of ffmpeg, about 1.4 MB, for video. Playwright is pinned to 1.64.1 in `package.json`.
3. The example runs as the `Specialist` entry in `personas.json`, in the Service Console app. Change either in the settings block at the top of the spec if yours differ. Rehearse it in round R0: `QA_ROUND=R0 QA_REASON=rehearsal npm run qa -- example`. A rehearsal runs without video, at full speed, and writes to `qa/evidence/rehearsal/`. If a step fails, read its failure snapshot in `failures/` first (search it for the label you expected), fix the script, and rehearse again.
4. When every step passes, open `storyboard.md` in the rehearsal folder. It lists every card, caption and screenshot in the order a viewer meets them. This is what the approver signs off before a recorded run.
5. Record once: `QA_ROUND=R1 QA_REASON=first-run npm run qa -- example`.

The recorded run prints each scenario's result. `qa/evidence/` now has a round folder with `screenshots/`, `videos/`, `run-summary.md` and `results.json`. Open a video in Chrome: it should start with an opening card, show the test user's session with a chapter card for each step, and show no records other than this ticket's test records.

## 7. Run a build check

The build check compares a ticket's spec with the org's metadata, read-only. The example check works on standard Case metadata, so it runs in any org.

1. From `qa/`, retrieve the two value sets the example check reads:
   `sf project retrieve start --metadata StandardValueSet:CaseOrigin StandardValueSet:CaseStatus --target-metadata-dir build-check-retrieve --unzip --target-org my-partial-sandbox`
2. Run the example check on the folder in `build-check-retrieve` that holds `package.xml`:
   `python3 build_check.py PROJ-21 --retrieve <that folder>`
3. Open the Markdown file it writes, `PROJ-21-build-check-<date>.md`.

To add a check for your own ticket, follow the steps in [templates/qa/README.md](../templates/qa/README.md).

Each row shows a metadata type, an API name, the expected value, the org's value, and Match, Mismatch or Recorded.

## 8. Set up publishing to Drive

Skip this if your evidence goes somewhere else.

1. In Google Drive, add the team's evidence folder to your Drive so Drive for desktop syncs it.
2. Put the folder's local path in `qa/.drive-dir`. It's under `~/Library/CloudStorage/GoogleDrive-<your account>/`.
3. Run `publish.sh` from your own terminal or the Claude desktop app's Terminal panel, not from Claude's Bash tool (see [gotchas.md](gotchas.md)), with the round folder: `./publish.sh "evidence/<epic>/<QA sub-task>/<round folder>"`.

The round folder shows up in Drive in the browser within a minute or two.

## 9. Allow full-resolution screenshots (optional)

Playwright saves its own screenshots, at twice the screen's resolution. You only need this if you also drive Chrome through Claude's browser tools for one-off checks and want evidence-quality images from them.

1. In System Settings, open **Privacy & Security**, then **Screen Recording**, and turn it on for the app that runs Claude Code's shell.
2. Run `capture_chrome_window.sh test.png <part of the test tab's URL>`, and allow the prompt to control Google Chrome.

The PNG shows only the page, at full resolution, with no browser toolbar.

## 10. Record the cost of QA work (optional add-on)

The ledger add-on records every scenario run and how long the AI worked on each block of QA, with what it would cost at API list price, so you can scope QA on the next project. Skip it if you don't need the figures.

1. Copy [addons/qa-ledger/](../addons/qa-ledger/README.md) into your qa folder as `ledger/`.
2. After a block of QA work, have Claude run `ledger/session_cost.py` for that block's time window, as the add-on's README describes. Rehearsals and tooling checks are kept out of the figures.
3. Run `python3 ledger/qa_report.py`.

The report prints totals and rollups by QA sub-task, story, epic and sprint.
