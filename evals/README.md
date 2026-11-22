# QA evals

A fixed test for the jobs where Claude's judgment decides the quality of the QA:

1. **Drafting Test Steps** for a QA sub-task from a story's acceptance criteria (tier `steps`).
2. **Writing the Playwright spec** from approved Test Steps (tier `spec`).
3. **Rehearsing and fixing that spec against a real org** until it passes (the org tier).

Run them on each new model, and before adopting a change to the rules, the skill or the harness, to show whether the change made things better or worse. Every story, user and value in them is invented (an "Acme Support" project), so they're safe to run and share.

## How a run is graded

Each case runs 3 times. A run's score combines three kinds of check:

- **Soft checks by Claude Code's eval runner** (`claude plugin eval`): the file was written, and it has a Coverage section.
- **A judge**, run by `check.py` (`lib/judge.py`): Sonnet reads the draft or spec against the case's `rubric.md`, three times, and the majority decides. The judge counts as one soft check beside the runner's. Every vote's reason is saved, so a judge miss can be read and argued with. A judge call that fails (the CLI updating itself, a network blip) isn't a vote; when no call returns, the run is marked "judge unavailable" and keeps its other scores. A run that already failed a hard check isn't judged, since it scores 0 either way.
- **Hard checks**, done in code by `check.py` on the files the run wrote. Any failed hard check scores the run 0.

| Tier | Hard checks |
| --- | --- |
| `steps` | Step 1 is the build check. Every step has one evidence tag and names a criterion. Coverage lists every criterion and no extra. Each criterion is proven with an evidence tag the answer key allows. Flows run only as users the story needs, and no more flows than it needs. A criterion tested elsewhere names that ticket. A drifted value from the build sub-task doesn't appear outside the build check |
| `spec` | `SCENARIOS` matches the approved steps (ids, flows, evidence). Every flow has an opening card, and every video step a chapter card. No XPath, CSS class, id or position locators. No `test.skip`, `test.fixme`, `test.only` or `storageState`. Records use the `QA <ticket> <round>` prefix. Every step checks by query. It compiles (TypeScript, strict) and `playwright test --list` shows each flow and standalone step |
| org | The rehearsal's own `results.json` shows every step passing, the stop rule never fired, and the final spec still passes the spec rules above. The number of rehearsal attempts is reported, not scored |

A case **passes when its average score is at least 2/3** (it holds on 2 of 3 runs). `check.py` exits 1 if any case fails.

The `steps` and `spec` tiers also run each case **without the kit's skill loaded**. The gap between the two arms is reported, never a pass or fail. It shows what the skill itself adds.

## What you need

- Claude Code 2.1.328 or later (`claude plugin eval` is experimental; the case files use schema 1.1).
- Node and Python 3. Run `npm install` in `evals/` once (TypeScript for the compile check) and in `templates/qa/playwright/` (Playwright).
- For the org tier only: the sf CLI, Google Chrome, and a Dev Hub. A free Developer Edition org can be a Dev Hub once Dev Hub is turned on in its Setup. A Dev Hub has a daily limit on new scratch orgs, and each org-tier run uses one, however many stories and runs it covers.

## Running them

| When | Command |
| --- | --- |
| After a change to the rules, the skill or the template | `evals/run.sh --tag steps --tag spec` |
| A new model, saved for comparison | `evals/run.sh --tag steps --tag spec --model <model id> --save <label>` |
| One case while working on it | `evals/run.sh --case steps-ACME-13 --runs 1 --keep` |
| The org tier | `QA_EVALS_DEVHUB=<dev hub alias> evals/org/run.sh` |

Useful options: `--case GLOB` (one per run: the runner keeps only the last, so use a glob such as `steps-ACME-1[12]` for several), `--runs N`, `-j N` (runs at once), `--max-cost-usd X` (stops the suite at that spend), `--keep` (leaves the runs' folders in `/private/tmp` for reading). The org tier takes `--stories`, `--runs`, `--model`, `--budget-usd` (the most one run may spend, default 10) and `--keep-org`.

Each run writes to `evals/results/<time>/` (not committed): `scores.md`, `hard-checks.json` with every failed rule and every judge vote with its reason, `report.html` from the runner, and `outputs/<case>/<arm>-<n>/` with each draft, spec and rehearsal result and the judge's `judge.md`, to read by hand. `--save <label>` also copies the scores to `evals/baselines/<date>-<model>-<label>.{json,md}`, which is committed so later runs can be compared.

The runner's HTML report is never published: `run.sh` always passes `--no-publish`.

## Reading the scores

- **A drop across all 3 runs of a case is a regression.** A 2-of-3 is noise until it repeats.
- Read `hard-checks.json` for which rule failed, then the run's file under `outputs/`. When the check is wrong and the draft is right, fix the checker or the answer key, not the pass mark.
- For a judge miss, read the run's `judge.md`: it gives each vote's reason. If the reason is wrong, the rubric needs sharpening (`rubric.md` beside the case). `check.py --no-judge` skips the judge, and `QA_EVALS_JUDGE` and `QA_EVALS_JUDGE_VOTES` change its model and number of votes.

## The org tier

`evals/org/run.sh` builds a throwaway scratch org from the fixture project in `fixtures/acme-support/sfdx/` (`org-up.sh`): it deploys the metadata, creates the test users, signs in once to warm the org up, and runs a setup check. A setup failure is reported as "setup failed" and nothing is scored. Then, for each story and run, Claude works in its own copy of the harness, writing the spec and rehearsing it until it passes. The scratch org is deleted at the end, even after Ctrl-C (`org-down.sh`, which only deletes orgs whose alias starts `qa-evals-`).

It runs outside `claude plugin eval`, because the runner's sealed runs have no network, no sf CLI and none of your sign-ins. So the org tier runs as you, on your machine:

- Claude runs headless (`claude -p`) with your personal `CLAUDE.md` and settings left out (`--setting-sources ""`), no MCP servers, and a short list of tools. Bash is limited to running the harness, reading files, and sf queries and describes. A run can't write the rehearsal's evidence (which is what grades it) or read the evals' answer keys and design.
- Ctrl-C stops the whole loop and still deletes the scratch org.
- The harness reaches Salesforce only through `evals/org/guard/sf`, placed first on the run's PATH. It allows only the commands the harness uses, and only against the eval's scratch org. It is a guard against mistakes, not a sandbox: code that calls the real sf by its full path would get past it. Read the runs' specs under `outputs/` if that matters to you.

## Keeping the evals honest

- **A rule change updates its check in the same commit.** A change to `docs/writing-test-steps.md`, the skill or `templates/qa/playwright/templates/story.spec.ts` updates the matching checker (`lib/steps_check.py`, `lib/spec_check.py`), answer key (`fixtures/acme-support/keys/`) or rubric (`steps/*/rubric.md`, `spec/*/rubric.md`).
- **Answer keys and approved steps never enter a run's folder.** The scaffolds copy only the story, the build sub-task, the kit's docs and the harness. `docs/superpowers/` (the evals' own design, which describes the traps) is never copied.
- **No real names in the fixtures.** List the client, employer and people names your fixtures must never contain in `evals/tests/deny-words.txt`, one per line. It's gitignored, so your list stays on your machine, and `test_no_real_names` checks the fixtures against it (it's skipped when the file is missing).
- **Tests:** `python3 -m unittest discover -s evals/tests -t .` from the repo root checks the checkers themselves.

## The fixture stories

| Story | What it tests |
| --- | --- |
| ACME-11 Contact Channel | A report run in the same session as a flow is covered by the flow's video, with no screenshot |
| ACME-12 Resolution Summary rule | A blocked save is a video; the rule's scope is read from its formula in the build check |
| ACME-13 Tier 2 Support queue | A permission story's QA proves access by build check and query, with no user video |
| ACME-14 Escalate to Tier 2 | A second user only when a criterion is about a second person |
| ACME-15 Priority on the page | A criterion tested in another story is named in Coverage, not given a step |
| ACME-16 Product Area | Steps come from the story, not the build: the build sub-task drifted from a criterion |

## Files

| Path | What it is |
| --- | --- |
| `run.sh` | Runs the `steps` and `spec` tiers through `claude plugin eval`, then `check.py` |
| `check.py` | The hard checks, the combined score and the score table |
| `lib/` | The checkers (`steps_check.py`, `spec_check.py`, `org_check.py`), the judge (`judge.py`), the tiers' registration (`tiers.py`), reading runs (`runs.py`) and scores (`score.py`) |
| `steps/`, `spec/` | One case per story: `case.yaml` (prompt and the runner's soft checks), `rubric.md` (what the judge reads against) and `scaffold.sh` |
| `scaffold/` | What each tier's run starts with |
| `org/` | The org tier: `run.sh`, `org-up.sh`, `org-down.sh`, `warm.cjs`, `write_result.py` and the sf guard |
| `fixtures/acme-support/` | The invented project: stories, build sub-tasks, approved Test Steps, answer keys, and the scratch org's metadata |
| `smoke/` | A one-line case that proves the plumbing works |
| `tests/` | Tests for the checkers |
| `baselines/` | Saved scores, by date, model and label |
