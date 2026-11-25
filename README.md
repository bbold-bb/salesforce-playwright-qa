# Salesforce QA with Claude Code and Playwright

A kit for running QA on a Salesforce build with Claude Code. For each build ticket, Claude Code checks the org's metadata against the build spec, drafts the QA Test Steps from the story for a person to approve, writes a Playwright script that clicks through those steps as the right test user, rehearses it until it passes, records screenshots and videos as evidence, and drafts the Jira results for a person to approve.

It's for Salesforce teams: solution architects, consultants, admins and QA. Copy it into your own project and set your own names.

**Status: draft.** The harness helpers and the process were built and proven on one large Service Cloud project. The kit's example spec hasn't yet been run on a fresh org, and nobody has followed the setup guide end to end. Fix what you find and send it back as a pull request.

## What QA answers

Every build ticket gets a QA sub-task. QA answers two questions for each one:

| Question | Evidence | How |
| --- | --- | --- |
| Was it built as specified? | A build check: one row per component by metadata type and API name, with what the ticket specifies and what the org has | Claude Code reads the org's metadata, read-only, and compares it exactly |
| Does it behave right? | The evidence each step is tagged for: a query, a screenshot, or a video | Playwright clicks through each flow as the persona's test user |

People approve at three points: the Test Steps before any script, the videos (and the storyboard before recording) before evidence is shared, and the exact Jira text before it's written. [docs/how-test-steps-flow.md](docs/how-test-steps-flow.md) shows who does what.

## What's in the kit

| Item | What it's for |
| --- | --- |
| [docs/how-test-steps-flow.md](docs/how-test-steps-flow.md) | Who does what, from story to Testing Feedback, and where the handoff to automation is |
| [docs/writing-test-steps.md](docs/writing-test-steps.md) | How to write a QA sub-task's Test Steps: from the story, not the build; Coverage; keeping steps simple; evidence tags; flows. Includes a template to paste into a ticket |
| [docs/project-questions.md](docs/project-questions.md) | Every question to answer to set the kit up for your project, why each matters and where the answer goes. Claude runs it as an interview |
| [docs/tech-stack.md](docs/tech-stack.md) | Each tool, what it does in the process, the version used, and the permissions it needs |
| [docs/setup-guide.md](docs/setup-guide.md) | From a fresh Mac to a first rehearsed and recorded scenario: the order to set things up and how to confirm each one works |
| [docs/gotchas.md](docs/gotchas.md) | What went wrong while the process was built, how it showed up, and the fix. Read it before your first run |
| [docs/starter-prompt.md](docs/starter-prompt.md) | A prompt to paste into Claude Code in your project, and a block of QA working rules for your project's `CLAUDE.md` |
| [templates/qa/](templates/qa/README.md) | Everything to copy into your project: the script that creates each tester's own test users from the personas you define, the build check, the data hygiene audit, the evidence index, the publish script and the full-resolution screenshot script |
| [templates/qa/playwright/](templates/qa/playwright/README.md) | The Playwright harness inside it: sign-in and Login As, flows with opening and chapter cards, rehearsal with failure snapshots and a storyboard, evidence and video helpers, console, list view and report helpers, traces kept for failed tests, and a spec template |
| [templates/claude-skills/](templates/claude-skills/README.md) | Claude Code skills to copy into your project's `.claude/skills/`: the kit's own Salesforce Playwright QA skill, and Microsoft's Playwright CLI and trace skills |
| [evals/](evals/README.md) | A fixed test of Claude drafting Test Steps and writing specs, with an optional tier that rehearses the spec in a throwaway scratch org. Run it on each new model and before changing a rule |
| [addons/qa-ledger/](addons/qa-ledger/README.md) | Optional. A ledger of every scenario run and what each block of AI work would cost at API list price, rolled up by ticket, story, epic and sprint |

## Where to start

1. Read [docs/how-test-steps-flow.md](docs/how-test-steps-flow.md) for the shape of the process, then [docs/gotchas.md](docs/gotchas.md).
2. Follow [docs/setup-guide.md](docs/setup-guide.md) as far as the example spec running against your sandbox.
3. Open Claude Code in your project and paste the prompt from [docs/starter-prompt.md](docs/starter-prompt.md). Claude interviews you with [docs/project-questions.md](docs/project-questions.md), copies the templates in with your answers, and works your first story with you, starting with its Test Steps.

## What you need

- A Claude plan that includes Claude Code
- A Salesforce sandbox where you're a System Administrator, with Login As turned on
- A Mac (the screenshot helper uses macOS tools; the rest should work elsewhere but hasn't been tried)
- Jira, if Claude will read and write the QA sub-tasks

The kit holds no passwords and stores no sessions. It reads the org's metadata and creates only the test users you approve and the test records its scenarios need.

## Contributing

Pull requests are welcome: fixes from running the setup guide, new Lightning patterns with their helper, new gotchas, and clearer wording. Keep examples generic (`PROJ-21`, `my-partial-sandbox`, `example.com`), and leave out anything that names a client, a person or a real org. Open an issue first for a larger change to the process.

## License

MIT, see [LICENSE](LICENSE). The two Playwright skills in `templates/claude-skills/playwright-cli/` and `playwright-trace/` are Microsoft's, copied unchanged, and keep their own Apache 2.0 license (the `LICENSE` and `NOTICE` files in each folder).

## Change Log

| Date | Change |
| --- | --- |
| 2026-11-20 | First public version |
| 2026-11-25 | Test users per tester and persona (`personas.json`, `test_users.py`, `testUser()`), with who ran each step in the evidence. The run lock covers rehearsals and waits its turn, waiting time is cut from videos, console tabs settle before they're closed, and more report and screen flow helpers |
| 2026-11-21 | Added evals: Test Steps and spec cases on an invented project, and an org tier on a scratch org |
