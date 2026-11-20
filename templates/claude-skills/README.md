# Claude Code skills

Skills for Claude Code to use with the Playwright harness. Copy each folder into your project's `.claude/skills/`, where Claude Code finds them at the start of every session and loads one when a task matches its description. To make sure the QA skill is used, name it in your project's `CLAUDE.md` (the rules block in [docs/starter-prompt.md](../../docs/starter-prompt.md) does).

| Skill | What it's for |
| --- | --- |
| [salesforce-playwright-qa/](salesforce-playwright-qa/SKILL.md) | The kit's own skill: Test Steps before any spec, which harness helper to use for each Lightning interaction, the rehearse-then-record order (failure snapshots, the stop rule, the storyboard, honest attempt reasons), finding a locator with the Playwright CLI under the sf CLI's sign-in, reading a failed run's trace, and the rules (no healer, no stored sessions, traces stay local). Fill in `<harness path>` and `<sandbox alias>` when you copy it |
| [playwright-cli/](playwright-cli/SKILL.md) | Microsoft's skill for the Playwright CLI (`npx playwright cli`): opening a browser session, snapshots, finding elements, generating locators, recording, tracing |
| [playwright-trace/](playwright-trace/SKILL.md) | Microsoft's skill for reading a trace from the command line (`npx playwright trace`): actions, errors, console, network |

The two Microsoft skills are copied unchanged from the `playwright` package 1.64.1 (`node_modules/playwright-core/lib/tools/skills/`, Apache 2.0), so they can be copied again after a Playwright upgrade:

```bash
cp -R qa/playwright/node_modules/playwright-core/lib/tools/skills/playwright-cli qa/playwright/node_modules/playwright-core/lib/tools/skills/playwright-trace .claude/skills/
```

`npx playwright cli install --skills` does the same copy but also downloads a Playwright browser, which the harness doesn't use (it runs the installed Chrome).
