# QA evals: design

Status: ready for approval. Owner: Ben Bolding. Date: 2026-11-21.

## Intent and why

The kit asks Claude to do two jobs where its judgment decides the quality of the QA:

1. **Draft the Test Steps** for a QA sub-task from a story's acceptance criteria.
2. **Write the Playwright spec** from those approved Test Steps.

There's no fixed test for either today, so nobody can say whether a new model, or a change to the rules, the skill or the template, made them better or worse. The evals are that fixed test:

- They're run again on each new model, with scores compared to the last run.
- They're run before a rule or harness change is adopted, to show it doesn't make the drafts or specs worse.
- An opt-in org tier proves a written spec actually runs green against a real org, and that it does so repeatably.

They live in the public repo, so anyone using the kit can run them.

## Goals

- A suite of cases, each run 3 times, scored, with a pass threshold, that anyone can run with one command.
- An **offline tier** (stages 1 and 2) that needs no org: cheap enough to run on every rule change.
- An **org tier**, tagged and opt-in, that runs a written spec in rehearsal (round R0) against an org and checks it goes green.
- Scores saved per model and date, so a new run can be compared with the last one.
- A with and without the skill comparison, to show the skill earns its place.

## Non-goals

- Grading video quality, card wording or the storyboard. Those stay a person's call.
- Jira, Slack, publishing or the ledger. The evals never write outside the run's own folders.
- Scoring real past runs from a project's ledger (option C). That's a later local add-on, kept out of the public repo.
- Stage 3 as its own offline case set (a broken spec handed over with a snapshot). The org tier covers fixing in practice, since Claude rehearses and fixes its own spec there.

## Anti-goals (a failure even if it technically works)

- **Any client, employer or real-person data in a fixture.** Every story, user and value is invented.
- **Graders that only check the format.** A draft with perfect headings that misses a criterion, or a spec that compiles but checks nothing, must fail.
- **An eval that passes by loosening a check.** The graders hold the same rules the kit does: no `test.skip`, `test.fixme` or weakened assertion.
- **An org-tier failure from the org itself** (a sandbox refresh, a missing user) read as a model regression. The org tier checks its setup first and reports setup failures apart from scores.
- **Evals that drift from the rules.** A rule change in `docs/writing-test-steps.md`, the skill or `templates/story.spec.ts` updates the matching graders in the same commit.

## Constraints

- Uses Claude Code's built-in runner, `claude plugin eval`. Cases are folders under `evals/` with a prompt and graders. Graders are scripts (pass or fail) or short rubrics scored by a judge model. The runner repeats each case (`--runs`, default 3), switches models (`--model`), gives a pass or fail exit code (`--threshold`) and runs a without-the-skill baseline arm. It's marked experimental, so the suite should keep most of its logic in plain scripts that would survive a move to another runner.
- The runner publishes its HTML report to claude.ai by default. The suite's run command always passes `--no-publish`.
- Script graders and the scaffold run as the person, on their machine. Scaffolds and the org tier are opt-in (`--scaffold`, `--allow-tools`).
- The offline tier must pass `tsc` and `playwright test --list` without an org, which the harness already supports.

## Approaches considered

| Approach | Trade-off | Decision |
| --- | --- | --- |
| A. Built-in `claude plugin eval`, offline cases plus an opt-in org tier | Least new code; repeats, judging, model switching and reports come free. Depends on an experimental feature | **Picked by Ben** |
| B. A custom runner in the repo | Full control, no dependency; several times the work to rebuild repeats, judging and reports | Not picked |
| C. Score real past runs from the ledger | Data already exists, but it's client data and can't replay a change before it's adopted | Deferred to a later, local-only add-on |

## The design

### Layout

```
evals/
  README.md                how to run, what each tier needs, how to compare scores
  run.sh                   the one command: wraps claude plugin eval with --no-publish and the repo's defaults
  fixtures/                the invented project: stories, build sub-tasks, approved steps, answer keys
    acme-support/
      project.md           the fictional org: objects, record types, test users, report folder
      stories/<KEY>.md     acceptance criteria and the story's own Test Steps
      builds/<KEY>.md      the build sub-task's spec
      approved/<KEY>.md    the approved Test Steps (stage 2 input)
      keys/<KEY>.yaml      the answer key: criteria, expected tag per criterion (with allowed alternatives), traps
      metadata/            the org tier's fixture metadata, deployable with sf
  graders/                 shared script graders, used by many cases
  steps/<case>/            stage 1 cases
  spec/<case>/             stage 2 cases
  org/<case>/              org tier cases, tagged org
  baselines/               saved aggregate results and a score table per model and date
```

The kit's skill (`templates/claude-skills/salesforce-playwright-qa`) is what the runner loads as the plugin under test, so the with and without arm measures the skill. How the repo exposes it as a plugin (a manifest at the root, or a skills directory) is the builder's call.

### Fixtures

One invented project, "Acme Support", with about six stories. Each story is picked to test one rule, not to be realistic for its own sake:

| Story | Rule it tests |
| --- | --- |
| A picklist field and a report grouped on it | Report in the same session as a flow is covered by the video, no screenshot |
| A validation rule that blocks a save | A blocked save is a video |
| A queue and permission set story | Access is proven by query and build check, no user video |
| A handoff from one user to a supervisor | A second user only when a criterion is about a second person |
| A story with one criterion tested in another story | Coverage points to the other story instead of a step |
| A story whose build sub-task drifted from one criterion | Steps come from the story, not the build: a draft that copies the drift fails |

Each has an answer key: the criteria by number, the expected evidence tag for each (with any allowed alternatives), the users the steps should use, and what must not appear (the drifted value, a Setup step, another story's work).

### Stage 1 cases: drafting Test Steps

- **Input:** the project file, one story and its build sub-task, plus the kit's `docs/writing-test-steps.md`.
- **Task:** draft the QA sub-task's Test Steps in the kit's template format.
- **Script graders:**
  - Step 1 is the build check.
  - Every other step sits in a named flow (or stands alone), with a user, a criterion number and one evidence tag.
  - There's a Coverage section with one bullet per criterion in the answer key, none missing, none extra.
  - Each criterion's tag matches the key or an allowed alternative.
  - No step uses a user the key doesn't allow, and the drifted value or forbidden content doesn't appear.
- **Judge rubric:** steps use plain user words, add nothing the story doesn't ask for, and each step's expected result matches its criterion.

### Stage 2 cases: writing the spec

- **Input:** a scaffolded copy of the harness (`templates/qa/playwright`), with the fixture's approved Test Steps.
- **Task:** write `tests/<KEY>.spec.ts` from the template.
- **Script graders:**
  - `tsc` passes, and `playwright test --list` lists the expected tests.
  - `SCENARIOS` matches the approved steps: same ids, flows and evidence tags.
  - Every flow calls `openingCard`, and every step on video has a chapter card.
  - No locator by XPath, CSS class, `nth` or generated id, and no `test.skip`, `test.fixme` or `storageState`.
  - Records use the `QA <TICKET> <round> S<n>` naming.
  - Every step has a `query(` check.
- **Judge rubric:** each step's assertions check its expected result, not something easier.

### Org tier: proving it against an org

- Tagged `org`, run only with `--tag org --scaffold --allow-tools Bash Edit Write` and a Dev Hub alias in an environment variable.
- **The org is a scratch org** (Ben, 2026-11-21). The scaffold creates one from `evals/fixtures/acme-support/project-scratch-def.json`, deploys `metadata/`, creates the test users, and the suite deletes it at the end. Each person needs a Dev Hub, which they can enable on a free Developer Edition org (to confirm in Salesforce's docs while building). One scratch org serves every org case in a run, so a run doesn't create one per case.
- **Setup check first:** the scaffold checks the metadata and test users are there, and fails as "setup" (not scored against the model) if not.
- **Claude rehearses and fixes** (Ben, 2026-11-21). Each case starts from the approved Test Steps, has Claude write the spec, then rehearse it (`QA_ROUND=R0 QA_REASON=rehearsal`), read the failure snapshot and fix, as the skill says, until green or until the stop rule fires.
- **Graded on:** every step green at the end (hard rule), no stop rule fired, no forbidden fix (`test.skip`, a loosened check, a step changed from the approved text), and the number of rehearsal attempts (fewer scores higher).
- Each case has a turn cap and a long timeout, set by the builder after a first timing run.
- Never records video, publishes or writes to the ledger.

### Scores and comparison

- `run.sh` saves each run's aggregate result to `evals/baselines/<date>-<model>.json` when asked to save.
- A short score table (case, pass rate over 3 runs, with and without the skill) goes next to it as markdown.
- The README says how to read a change: a drop in one case across all 3 runs is a regression, and a 2 of 3 is noise until it repeats.

### Hard checks run after the runner (Ben, 2026-11-21)

The installed runner (Claude Code 2.1.328, case schema 1.1) has text-pattern (`regex`), `file_exists`, `tool_used`, `tool_order`, judge (`llm`) and `baseline` graders, and no script grader. So the "script graders" above run in a second step:

1. `run.sh` runs `claude plugin eval` with `--keep-temp --json`. The runner does the model runs, the pattern graders and the judge rubrics.
2. `evals/check.py` reads that JSON, opens each run's kept folder (the run's files are at `<kept>/sealed/home/cwd`), runs the hard checks in code (Test Steps against the answer key, `tsc`, `playwright test --list`, the spec rules, the rehearsal's `results.json`), and writes one score table.
3. A run with any failed hard check scores 0. Otherwise it keeps the runner's score.
4. `check.py` deletes the kept folders when it's done, unless asked to keep them.

Every hard rule is checked by code, not by what the run printed.

### Calls made after the builder check (Claude's, for Ben to check)

- **Pass mark.** A case's score is the share of its graders passed, averaged over 3 runs. `run.sh` uses `--threshold 0.67`, so a case fails only when it misses on 2 of 3 runs. Script graders are hard rules: one failing makes that run score 0. A judge rubric only lowers the run's score.
- **The with and without comparison is reported, not a gate.** Both arms get the same workspace (the kit's docs, the harness, the template) but the prompts don't paste the docs in. A person asks the way a teammate would ("draft the Test Steps for ACME-12"). The skill's value is knowing which rules and files to follow, which is what the gap measures.
- **Local only for now.** No CI gate. `run.sh` takes `--max-cost-usd` as an option. CI can come later once the suite is stable.
- **TypeScript comes with the evals.** `evals/package.json` adds `typescript` as a dev dependency for the `tsc` grader, so the kit's template stays as it is.
- **The org tier starts with two stories**: the picklist and report story, and the validation rule story. That's enough to prove a written spec runs against an org. The others join once those are stable.
- **Org records stay in the org,** named `QA <KEY> R0 S<n>`, the same as the kit's rule. The "never writes outside its folders" goal means no Jira, Slack, publishing or ledger, not no org records.

## Left to the builder

- How the skill is exposed to the runner as a plugin.
- Grader script language (Python preferred, to match the kit's other tools).
- Exact case and fixture names, and the number of cases per stage beyond one per fixture story.
- The judge model (the runner's default is Haiku; pick a stronger one if Haiku misjudges rubrics in testing).

## Open questions for Ben

None. Both answered 2026-11-21: scratch org, and Claude rehearses and fixes.

## Change Log

| Date | Change |
| --- | --- |
| 2026-11-21 | First draft |
| 2026-11-21 | Calls after the builder check: pass mark, comparison, local only, TypeScript, two org-tier stories, org records |
| 2026-11-21 | Ben: org tier uses a scratch org, and Claude rehearses and fixes its spec there |
| 2026-11-21 | Ben: hard checks run in evals/check.py after the runner, since the runner has no script grader |
