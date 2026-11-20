---
name: salesforce-playwright-qa
description: Use when writing, fixing, running or debugging the project's Playwright QA specs in <harness path>, when finding locators on a Salesforce Lightning page (consoles, list views, related lists, lookups, record pages, picklists, reports), or when reading a failed run's trace. Points at the harness's helpers and rules so console and list view behaviour isn't worked out again.
---

# Salesforce Playwright QA

The harness is in `<harness path>` (for example `qa/playwright/`; the setup step fills this in). Run every command below from that folder. Its README is the source for how a run works (rounds, attempts, flows, evidence, publishing); this skill only says where to look and what not to do.

## Before writing or fixing a spec

0. For a new story, the QA sub-task's Test Steps come first: draft them from the story's acceptance criteria (not the build sub-task), as flows with a user, criterion and evidence tag on each step and a Coverage section, and get the approver's go on the text before writing the spec (README, Adding a story; the kit's `docs/writing-test-steps.md`).
1. Read the README sections **Console and report patterns**, **Navigation and list views** and **Adding a story**.
2. Start a new spec from `templates/story.spec.ts`, not from an older spec: older ones can predate a rule. Copy the approved steps and their evidence tags into `SCENARIOS` word for word.
3. Use the helpers in `lib/salesforce.ts` rather than writing the interaction again:

| Need | Helper |
| --- | --- |
| Sign in and become the persona's test user, landing on a page | `signInAs(browser, user, path)` |
| A second user in the same video | `switchUser`; `clearOrgBrowserData` first if the user's access changed mid-run |
| A page by URL when getting there isn't under test | `appPath`, `listViewPath`, `reportPath`, `recordPath`, then `goTo` |
| A list view in table view, narrowed to the round's QA records, and a row in it | `tableView`, `listSearch`, `listGrid`, `listRow` |
| A picklist value, the values it offers, a lookup | `pickValue`, `picklistOptions`, `pickLookup` |
| A related list, its New form, a row (table or card), a row action | `relatedList`, `newFromRelatedList`, `relatedRow`, `rowAction` |
| Console subtabs | `closeSubtab`, `selectSubtab` |
| A page section, an inline edit, Change Record Type, Change Owner to a queue | `recordSection`, `editFieldInline`, `changeRecordType`, `changeOwnerToQueue` |
| A report from its folder, its frame, every group showing | `openReportFromFolder`, `reportViewer`, `hideDetailRows` |
| A step that sends email from a sandbox with email off | `withEmailOpen`, and `closeEmailIfOpen` in `afterAll` |
| A browser context the spec opens itself, so failure snapshots include it | `trackContext` |

4. Find elements by role and label, the way a person reads the screen. Never by position, generated IDs, XPath or CSS classes: XPath doesn't reach inside shadow roots, and Salesforce changes its internal markup between releases.
5. Every step checks its result by query as well as on screen.
6. When a new console or list view behaviour turns up, add a helper and a row to the README's patterns table in the same change.

## Rehearse, then record

Never find out how a screen behaves inside a recorded round. In this order:

1. For each screen the spec touches that no helper covers, look at it first with the CLI (next section) and take the locators from its accessibility tree.
2. Rehearse until every step passes: `QA_ROUND=R0 QA_REASON=rehearsal npm run qa -- <ticket>`. No video, its own folder, left out of the ledger's figures (README, Rehearse first). Rerun one flow with `--grep F2` while fixing it, then the whole spec once before recording.
3. When a step fails, read `failures/A<n>-<step>.aria.yml` in the rehearsal folder first: it holds the address and the role and name of everything each open page showed. Search it for the label you expected (`grep -n -i "owner"`), don't read it whole, and open the trace only if it doesn't answer the question. Fix every problem the snapshot shows for that step in one edit, not one per run.
4. **Stop rule.** A step that fails three rehearsals in a row is not tried a fourth time, and the run prints a STOP line saying so. Take it to the approver with the snapshot, what was tried, and the options with a recommendation: another way to do the step, proving it by query, or changing the step.
5. Show the approver `storyboard.md` from the last green rehearsal, with its screenshots, and get their go on the card wording and framing.
6. Record once: the real round with its real reason. If it fails on the script, fix it and go back to step 2 before another recorded attempt. Only one recorded run goes at a time; a second one stops on the lock.

Pick the attempt reason honestly: `script-fix` when the script was wrong, `steps-changed` when the approved Test Steps changed and the script followed them, `flaky` when nothing changed.

## Finding a locator on a live page

Use the Playwright CLI (the `playwright-cli` skill lists its commands; run them as `npx playwright cli ...`). Always the installed Chrome, a named session, and the sf CLI's one-time sign-in URL read inside the shell so it never prints. Replace `<sandbox alias>` with the QA sandbox's sf CLI alias:

```bash
U=$(FORCE_COLOR=0 sf org open --url-only --path /lightning/page/home -o <sandbox alias> --json | python3 -c "import json,sys;print(json.load(sys.stdin)['result']['url'])") && npx playwright cli -s=sfqa open --browser chrome "$U" | sed -E 's#https://[^ )]*(frontdoor|singleaccess)[^ )]*#<one-time-url>#g'; unset U
npx playwright cli -s=sfqa find "Search this list"
npx playwright cli -s=sfqa generate-locator e314 --raw
npx playwright cli -s=sfqa close && npx playwright cli -s=sfqa delete-data && rm -rf .playwright-cli
```

`goto` needs the full Lightning host, not a bare path. `find` and `snapshot` show the accessibility tree, which is what role and label locators match. To capture a sequence a person clicks through, open with `--headed`, then `recording-start`, and `recording-stop` prints the steps as Playwright code; rewrite them with the helpers before they go into a spec. Only the QA sandbox, never production, and nothing saved with `state-save`.

## When a run fails

A failed test keeps a trace in `test-results/<ticket> <round> <start time>/<test>/trace.zip` (`QA_TRACE=on` keeps one for a passing run too). Each run has its own folder and none is cleared, so earlier runs' traces are still there; they stay on this machine. Read it with the `playwright-trace` skill: `npx playwright trace open <zip>`, then `errors`, `actions`, `console` and `requests`. `trace snapshot` needs Playwright's own headless browser, which the harness doesn't install; for the page itself, open the zip at trace.playwright.dev in Chrome, which reads it locally.

## Rules

- **Traces and `.playwright-cli/` stay on this machine.** They hold the page, the network and the session. Never publish, attach or commit them; both are gitignored.
- **No Playwright Test Agents healer, and no `test.skip`, `test.fixme` or loosened check to make a run pass.** A script change is a `QA_REASON=script-fix` attempt that is rerun and reviewed like any other.
- **No stored sessions or passwords.** Don't add `storageState` files or a setup project that saves one.
- **The script follows the approved Test Steps.** If a run shows a step is wrong, take it to the approver as a change to what's tested; don't change the step in the script on your own.
- Set every subagent's model explicitly, per the project's `CLAUDE.md`.
