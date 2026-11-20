# QA ledger (optional add-on)

The QA ledger records what QA costs and how often it reruns: every scenario run, round and attempt with its reason, and how long the AI worked on each block of QA work and what that would cost at API list price. It rolls those up to QA sub-task, story or Task, epic and sprint, so it can answer questions like "how many scenarios did we run across this epic, and what did a scenario cost on average?" or "what did Sprint 1's QA cost?".

It's optional. The Playwright harness, the build check, the evidence index and `publish.sh` all work without it. Add it when you want effort and cost figures for QA. It stays private to your team: the figures stay on your machine and aren't tracked in Jira.

## Adding it to a project

1. Copy this folder into your qa folder as `ledger/`, beside `playwright/` and `data_hygiene.py`:

   ```
   <qa folder>/
     data_hygiene.py
     value_quirks.py
     ledger/          this folder
     playwright/
     evidence/        gitignored
   ```

2. Turn it on for Playwright runs with `QA_LEDGER=1`, either on each run or exported in your shell:

   ```bash
   QA_LEDGER=1 QA_ROUND=R1 QA_REASON=first-run npm run qa -- PROJ-21
   ```

   With it on, each run writes its scenario rows to the ledger and the run manifest reads the Jira snapshot. With it off (the default, `LEDGER_ENABLED` in `playwright/lib/config.ts`), runs write neither, and the manifest records the Jira items as not collected.

3. Set the project settings at the top of [jira_snapshot.py](jira_snapshot.py): `JIRA_PROJECT` (your project key) and `SPRINT` (your Sprint field's ID).

4. Check `PRICES` in [session_cost.py](session_cost.py) against the current Anthropic pricing page, and add a row for every model your sessions use.

It needs:

- Python 3.9 or later.
- [Polars](https://pola.rs/) for the report (`pip install polars`). Recording rows needs only the standard library.
- `data_hygiene.py` and `value_quirks.py` in the qa folder, one level up. The report audits every file it reads with them.
- Claude Code session logs under `~/.claude/projects/`, for `session_cost.py`. Without them you still get scenario runs, rounds and attempts, just no cost.
- A read-only Jira search you can save as JSON (through an Atlassian connector or the Jira REST API), for `jira_snapshot.py`. Without the snapshot, the report can't roll runs up to story, epic or sprint.

## The files

The ledger is four CSV files in `evidence/qa-ledger/` under the qa folder (or under `QA_EVIDENCE_DIR`, if you set it). Gitignore them and keep them on your machine: they hold your team's cost figures, and the QA Evidence folder in Drive may be shared with the client. `publish.sh` never copies them.

| File | One row per | Written by |
| --- | --- | --- |
| `scenarios.csv` | Each scenario defined, per QA sub-task, with the evidence it needs | The Playwright spec, on every run (its `SCENARIOS` list) |
| `scenario-runs.csv` | Each scenario, each time it runs: round, attempt, reason, method, org, sprint, result, seconds | The Playwright runner at the end of each run. Add browser-tool or by-hand runs the same way, one row per scenario |
| `sessions.csv` | Each block of QA work: kind, the QA sub-tasks and runs it covered, model calls, AI minutes, tokens, cost | [session_cost.py](session_cost.py), from the Claude Code session log |
| `jira-items.csv` | Each Jira item in the project: type, parent, epic, sprint, last update | [jira_snapshot.py](jira_snapshot.py), from a read-only Jira search |

The ledger records only the QA sub-task and the scenario. Story or Task, epic and sprint come from the Jira snapshot, so nobody types the structure in. A run is also stamped with its sprint when it runs, so it stays in that sprint if the story moves later.

Every value is text, written and read exactly as is. Don't open these files in Excel and save them: Excel drops leading zeros and rewrites dates.

## Rounds, attempts and reasons

A **round** is one version of the build. A new round means something under test changed. An **attempt** is a rerun within a round when nothing under test changed. Each run carries a reason from [qa_ledger.py](qa_ledger.py), the same list as `playwright/lib/evidence.ts`:

| Reason | Starts a | Use when |
| --- | --- | --- |
| `first-run` | Round | The first round for this QA sub-task in this org |
| `retest-after-fix` | Round | A failure reopened the build sub-task and the build was fixed |
| `story-changed` | Round | The story, its acceptance criteria or its Test Steps changed |
| `regression-after-deployment` | Round | A deployment touched what the story built |
| `script-fix` | Attempt | The test script was fixed; nothing under test changed |
| `steps-changed` | Attempt | The approved Test Steps changed and the script followed them; the build didn't change |
| `flaky` | Attempt | A step failed for a reason outside the build (timing, session) |
| `tooling-check` | Attempt | A check that the QA tooling still works after you changed it |
| `rehearsal` | Round `R0` only | A practice run of a script before its recorded run: no video, its own folder under `evidence/rehearsal/` |

`steps-changed` separates changes to what's tested from fixes to the script, which stay `script-fix`.

## Recording QA work

Add each block of QA work to `sessions.csv` when the block ends (times in the script's time zone, UTC unless you set `QA_TZ`, the end inclusive):

```bash
python3 ledger/session_cost.py --session <session ID> --start 2026-01-05T09:00 --end 2026-01-05T09:40 --kind run --qa PROJ-21 --runs PROJ-21-R3-A1 --append
```

| Kind | Use for |
| --- | --- |
| `setup` | One-time tooling setup, not tied to a story |
| `scripting` | Writing a story's scenarios as a script |
| `run` | Running scenarios and reading the result |
| `fix` | Fixing a failed script or scenario, and rerunning |
| `review` | Reviewing evidence and drafting the Testing Feedback |
| `build-check` | Running and reviewing a build check |
| `reporting` | Write-ups and figures about the QA |

- **The session ID** is the log's file name, without `.jsonl`, in your project's folder under `~/.claude/projects/`, or `latest`. Claude Code names that folder after the folder you started it in, with every character that isn't a letter or a digit replaced by `-`. The script works it out; if it can't, list `~/.claude/projects/` and pass `--log-dir`.
- **Subagents** that ran in the window are included in tokens and cost. Their time counts once on the clock, even when they run alongside the session or each other.
- **AI minutes** count from each prompt to the last model call, the session's or a subagent's, before the next prompt, so waiting on a person doesn't count.
- **Count only core QA work**, the work QA needs on any project: scripting, running, fixing, build checks, reviewing evidence, publishing and the Jira update. That way the figures carry over to other projects. Leave out a project's own extras, such as GitHub pushes: set the window to leave them out, and split a block in two if one falls in the middle.
- **Cost** is the Claude API list price for the model, from `PRICES` in `session_cost.py`. Each call's tokens are priced by kind: input, cache writes (1.25 times input for a five-minute write, twice input for a one-hour write, as the log records each), cache reads, and output, which includes thinking. It's a list-price equivalent for scoping, not what your team pays.
- **After a price change**, `python3 ledger/session_cost.py --reprice` measures every recorded block again from its session log and rewrites its cost.

A Playwright run started by a person costs no tokens, so it adds scenario runs but no session.

## Reporting

Refresh the Jira snapshot first (the steps are at the top of `jira_snapshot.py`), then run the report from the qa folder:

```bash
python3 ledger/qa_report.py
python3 ledger/qa_report.py --sprint "Sprint 1"
python3 ledger/qa_report.py --epic E1
python3 ledger/qa_report.py --qa PROJ-21
```

It prints tables of totals and rollups by sprint, epic, story or Task, and QA sub-task, plus cost by kind of work and by method (Playwright, browser tool, by hand). Each rollup shows scenarios defined, distinct scenarios run, scenario runs, failed runs, rounds, attempts, cost for running and for all work, the cost and tokens per scenario run, and AI minutes. With `--qa` it also lists every scenario run.

**How cost reaches a scenario.** A session's cost is split evenly across the QA sub-tasks it covered, then each QA sub-task's share is split evenly across the scenario runs that session produced for it. A share with no scenario run (scripting, a review, a write-up) stays with the QA sub-task: it counts in "all work" but not in "running". Setup not tied to a QA sub-task counts only in the totals.

**Runs that check the tooling are left out.** A run with the reason `tooling-check` tested the QA tooling after a change to it, not the build. It stays in the ledger and the evidence, but the report leaves it out of every figure and lists it at the end, so the per-scenario averages reflect QA of the build only.

**Rehearsals are left out too.** A run with the reason `rehearsal` is a practice run of a script before its recorded run, in round `R0`. It stays in the ledger, so rehearsals can be counted against recorded attempts, and the report leaves it out of every figure and lists it with the tooling checks. The work session that covered it still counts in the QA sub-task's all-work cost.

**Before a figure leaves the ledger**, the numbers gate applies: the report audits every file it reads (`data_hygiene.py`) and stops on anything unexplained, and any figure going into a write-up, ticket or message also gets an independent recompute that matches.

## Files

| File | What it is |
| --- | --- |
| [qa_ledger.py](qa_ledger.py) | Where the files live, their columns, and the reason, method and kind lists |
| [session_cost.py](session_cost.py) | Measures a block of work from the session log and adds it to `sessions.csv`; `--reprice` after a price change |
| [jira_snapshot.py](jira_snapshot.py) | Writes `jira-items.csv` from saved Jira search results |
| [qa_report.py](qa_report.py) | The report. Needs Polars |
