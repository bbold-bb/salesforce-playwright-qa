# Starter prompt

There are two parts. The prompt starts a Claude Code session that sets up QA in your project and scripts your first story with you. The rules block goes in your project's `CLAUDE.md`, so every later session follows the same process.

Clone this kit first, then open Claude Code in your project's folder and add the kit's folder to the session.

## The prompt

Fill in the angle brackets, then paste it as your first message.

```text
I'm setting up AI-run QA for a Salesforce build, using the Salesforce Playwright QA kit at <path to the kit>.

Read the kit's README.md, docs/how-test-steps-flow.md, docs/writing-test-steps.md, docs/gotchas.md and docs/setup-guide.md first, then the READMEs in templates/qa/, templates/qa/playwright/ and templates/claude-skills/.

Then, one step at a time, and wait for me where a step says so:

1. Check what's already set up on this machine (sf, node, python3, Chrome, Playwright) and tell me what's missing.
2. Interview me with docs/project-questions.md, one group at a time. Wait for my answers before the next group. Don't guess any answer, and check every name I give you (alias, Jira field, user, app) against the live system. After each group, show me where each answer will go before you write it. End with the table of answers, the open questions, and the CLAUDE.md rules block filled in.
3. Copy templates/qa/ into <folder in this repo>, set the answers in its config blocks (playwright/lib/config.ts, the config block at the top of the spec template, build_check.py), and make sure evidence/, test-results/, .playwright-cli/, .drive-dir and node_modules/ are gitignored. Copy the folders in templates/claude-skills/ into this project's .claude/skills/, with the paths and the sandbox alias in salesforce-playwright-qa/SKILL.md set to ours. If I said yes to the ledger, copy addons/qa-ledger/ into <folder in this repo>/ledger/.
4. Add the QA rules block from the kit's docs/starter-prompt.md to this project's CLAUDE.md, with our answers filled in. Show me the text before you write it.
5. Run the example spec against the sandbox as a rehearsal (QA_ROUND=R0 QA_REASON=rehearsal) and show me the run summary. Fix anything that fails, and tell me whether the fix was in the setup or the script.
6. Take my first QA sub-task, <Jira key>. Read it and its story. Draft its Test Steps from the story's acceptance criteria, following docs/writing-test-steps.md: step 1 the build check, then flows with the user, criterion and evidence tag on each step, then Coverage. Show me the draft and stop until I approve it.
7. Once I've approved the steps: read the build sub-task and run the build check. Write the spec from the template, copying the approved steps and tags word for word. Rehearse it in R0 until every step passes, then show me the storyboard. Stop there: I approve the storyboard before the recorded run, and I watch the videos before anything is published or written to Jira.

Rules for this session: no passwords anywhere (sign in through the sf CLI and Login As); only read the org, apart from the test records the scenarios create; nothing goes to Jira, Drive or Slack without my approval of the exact text.
```

## The rules block for `CLAUDE.md`

Copy this into your project's `CLAUDE.md` and replace the angle brackets. It's the generic form of the rules the process ran under. Change what doesn't fit your project, and keep the two approvals.

```markdown
## QA

Every build ticket gets a QA sub-task. QA answers two questions, each with its own evidence.

- **Was it built as specified?** A build check compares the org's metadata, read-only, with the build sub-task's spec: one row per component by metadata type and API name, with expected and actual (`<qa folder>/build_check.py`). No Setup screenshots.
- **Does it behave right?** Each step gets the evidence its tag names (see Evidence tags).

### Roles

- The <Solution Consultant> owns the story: description, user story, acceptance criteria. No one else edits those fields; a change is proposed in a comment.
- The <Salesforce Administrator> builds from the build sub-task.
- The <Solution Architect> approves the QA sub-task's Test Steps, the storyboard, the videos before they're shared, and the exact Testing Feedback text.

### Test Steps

- **Test Steps first.** Before any script, draft the QA sub-task's Test Steps: step 1 the build check, then the steps grouped into flows, each naming the test user, the criterion it proves and its evidence tag, then a Coverage section with one bullet per criterion. The <Solution Architect> approves the text, and the script implements it word for word. See `docs/writing-test-steps.md` in the QA kit.
- **Steps come from the story, not the build.** Draft the flows from the acceptance criteria before reading the build sub-task. The build spec feeds only step 1, the build check.
- **Keep steps simple.** One step per criterion where possible, plain user words, the fewest users and records, the build check carries the bulk, nothing the story doesn't ask for.
- **Evidence tags.** Each step carries [Build check], [Query], [Screenshot] or [Video], the first that proves its criterion, in that order. A step with a video gets no screenshot on top. An unclear tag goes to the <Solution Architect>, and the answer becomes a row in the decided-cases table in `<qa folder>/playwright/README.md`.
- **Flows.** One user's session through several steps is one video, with an opening card saying what this video covers and a chapter card per step. A step that fails stops its flow.
- **A step found wrong after approval** goes back to the <Solution Architect> as a change to what's tested. Once accepted, the ticket, the script and the rerun follow, with the reason `steps-changed`.

### Running

- **Scenarios run in Playwright** (`<qa folder>/playwright/`) against `<sandbox alias>`. They sign in through the sf CLI's one-time URL and use Login As to run as the persona's test user. No script holds a password, and no session is saved. Use the `salesforce-playwright-qa` skill before writing, running, fixing or debugging a spec, and start every new spec from `templates/story.spec.ts`.
- **Rehearse in R0, then record once.** A new or reworked script is rehearsed (`QA_ROUND=R0 QA_REASON=rehearsal`, no video) until every step passes. A step that fails three rehearsals in a row stops and goes to the <Solution Architect> with the failure snapshot and options. The <Solution Architect> approves the storyboard from the last green rehearsal, then the round is recorded.
- **Rounds and attempts.** A round is one version of the build. A rerun with nothing under test changed is an attempt in the same round, with an honest reason: `script-fix` when the script was wrong, `steps-changed` when the approved steps changed, `flaky` when nothing changed. Earlier attempts are kept, never overwritten. Only one recorded run goes at a time, since runs share the test users.
- **Test records stay in the sandbox** as the record of the testing, named `<prefix> <ticket> <round> S<n> <what>`. Use made-up names and `example.com` addresses only. Don't delete them.
- **A failure reopens the build sub-task** with what failed. The retest is a new round.
- **Testing path:** <for example partial sandbox, then full sandbox, then UAT>. Each environment gets its own QA sub-task with the same Test Steps.

### Approvals

Nothing leaves this machine without them:

1. The <Solution Architect> watches every video before evidence is published. Then `publish.sh` copies the round's final evidence and the build check to <evidence folder>. Earlier attempts, run manifests, traces and the ledger stay local.
2. The <Solution Architect> approves the exact Testing Feedback text before it's written to Jira. It carries the dated build check line and the final passing round: who the steps ran as, the result per step, the evidence link, and a link to each test record. It doesn't say how the testing was done. Read every Jira write back.

Nothing is sent to Jira, Drive, Slack or email without approval of the exact text.

### Numbers

No count from a build check or the ledger goes into a ticket or a message until the script that produced it ran the hygiene audit (`data_hygiene.py`) on every value list it read, and an independent subagent has recomputed the figures from the raw data and they match.

### Optional: QA ledger

When a block of QA work ends, record it with `ledger/session_cost.py` (scripting, run, fix, review, build-check or reporting). Runs with the reason `rehearsal` or `tooling-check` stay out of the figures. The ledger stays on this machine.
```
