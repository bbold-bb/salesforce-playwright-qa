# Gotchas

What went wrong while the process was built on a large Salesforce Service Cloud project, how it showed up, and what fixed it. Most fixes are already in the harness as helpers or rules (see the patterns tables in [templates/qa/playwright/README.md](../templates/qa/playwright/README.md)); this list is so you recognize the symptom when you hit something like it. The Cost section applies only if you use the optional ledger add-on in [addons/qa-ledger/](../addons/qa-ledger/README.md).

## Signing in and the browser

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| A passkey on the admin login blocked the agent's browser | Claude's built-in browser couldn't get past the sign-in page, so a person had to sign in by hand every round | Sign in with the sf CLI's one-time URL (`sf org open --url-only`), then Login As. No password or passkey is involved |
| Login As sessions end | Partway through a long round with the browser tool, the test user's session ended and the last scenario had to be checked through the API instead | Playwright signs in fresh at the start of each run, which takes about 14 seconds |
| The test user lands in the wrong app | A specialist opened the standard Service Console instead of the project's custom console, so the screen didn't match the story | Set the custom app as the test user's default, and have the script go straight to a record URL in that app |
| Console tabs carry over between sessions | Tabs from an earlier session, including another ticket's test records and records that weren't test records, reopened and showed in the video | Before recording, the runner closes every console tab that isn't one of this ticket's test records |
| Login As lands on Home or a list view | The video opened on a page of other records before reaching the scenario | The runner signs in straight to the scenario's record, so the video starts there |
| Login As reports an error while it works | Login As can report `net::ERR_ABORTED` and still complete, the "Logged in as" banner doesn't always render, and running Login As again as the test user lands in Salesforce Classic | Run Login As once, and confirm the switch from Lightning's current user, not from the banner |
| "Log out as" ends at the login page | One tab couldn't go back to the admin to sign in as a second user | Get a fresh one-time URL from the sf CLI, then Login As again. One video can then follow several users |
| Lightning caches metadata across Login As | A permission set given through the API didn't show its record type at the next Login As in the same browser, because Lightning reused the object info it keeps in browser storage. A fresh browser showed it | Clear the org's browser storage before switching users when access changed mid-run |
| Two recorded runs at once | Runs from two chats shared the test users, so each video showed the other run's records and tabs | Only one recorded run at a time: the harness takes a lock and a second recorded run stops. Rehearsals don't take the lock |

## Playwright and the sf CLI

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| The sf CLI colours its JSON under Playwright | Playwright sets FORCE_COLOR, so the CLI's JSON came back with colour codes and wouldn't parse | Set `FORCE_COLOR=0`, `NO_COLOR=1` and `SF_DISABLE_COLORS` for CLI calls, and strip colour codes before parsing |
| Setup Audit Trail and fractional seconds | A datetime literal with milliseconds was rejected | Drop the fraction: `2026-01-05T14:00:00Z` |
| Setup Audit Trail can't filter by Section | Logins and Login As swamped the list of Setup changes | Leave out the Manage Users section in code, after the query |
| Validation rule metadata reads one row at a time | A Tooling API query for several rules' `Metadata` failed | Look up the IDs first, then query `Metadata` by ID, one at a time |
| Finding out how a screen behaves inside a recorded round | Recorded rounds filled up with failed attempts while the script learned each screen | Rehearse in round R0, without video, until every step passes, and only then record. A rehearsal saves a failure snapshot (the accessibility tree of every open page) for each failed step, so the fix comes from one read rather than another run |
| The same step failing again and again | Rehearsal after rehearsal tried small changes to one step | A step that fails three rehearsals in a row stops, and goes to the approver with the snapshot and options: another way to do it, proving it by query, or changing the step |
| Traces cleared by the next run | A later run wiped the earlier run's traces before anyone read them | Each run keeps its traces in its own folder under `test-results/`, never cleared, and never published |
| Retries hide flaky steps | Later scenarios use earlier scenarios' records, and an automatic retry would pass a flaky step silently | Run one worker, in order, with no retries. A rerun is a deliberate attempt with a reason |
| Playwright's own traces and videos | Traces capture every page the browser opens, session included | Turn Playwright's video and screenshot settings off, and keep a trace only for a test that fails (`retain-on-failure`), in gitignored `test-results/`, never published. The tests save only the evidence each scenario declares |
| The trace filmstrip takes over the evidence video | A trace with `screenshots: true` starts a screencast of its own, which would replace the one recording the evidence | Keep the trace's `screenshots` off. DOM and accessibility snapshots don't affect the video |
| A run that dies at sign-in | A failed sign-in or manifest step leaves no scenario results, so counting it would only add an empty attempt | A run that stops before its first scenario isn't recorded as an attempt |
| Selectors break after Salesforce releases | Selectors on page position or Salesforce's internal markup break with each release | Find elements by role, label and name, the way a person reads the screen. Salesforce's UTAM is the fallback if label lookups keep breaking |

## Lightning pages

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| A field's label on the page differs from what the story calls it | The story used the field's new business name, but the page still showed the standard label Case Origin, so a lookup by the story's word would fail | Find fields by the label the page shows, and note the difference for the story owner |
| Full-page screenshots of a scrolled Lightning page | The sticky header was drawn in the middle of the image | When a picklist is open or the page has scrolled, scroll to the top and capture the visible window instead of the full page |
| A report with detail rows turned off | The script looked for the test records' names in the report and failed, though the report was right | Check the report's totals, or turn detail rows on, and confirm the count by SOQL |
| A list view opens in split view | A new user's list opened in split view, which has no grid and no row menu, and sometimes drew nothing. A user's list opens the way they last left it | Switch the list to Table before searching it, and reload once if it never draws. Table can show as a radio or as a checkbox item |
| An enhanced related list draws cards | In a narrow column, an enhanced related list drew each record as a card, not a table row, so a row lookup found nothing | Match the card (an article named for the record) as well as the row |
| Related-list cells in shadow DOM | Cells couldn't be read one by one | Match the row by its first column and other text in the row |
| New on a related list in a console | The form opened as a console subtab, not a modal, and the saved record opened another subtab that Lightning redrew while it loaded, so one close often missed | Fill the form inside the subtab, and retry closing a subtab until it's gone |
| A picklist says it's open too early | The list reported itself open before its options took a click | Wait for the option, scroll to it, and reopen the list once if the click doesn't land |
| A new record isn't searchable at once | A search for a record the script had just created found nothing | Wait until search finds it, with a time limit, before the step that searches |
| A hidden section isn't on the page at all | A Dynamic Forms section hidden by a visibility rule isn't rendered, so it can't be "not visible" | Find the section by its heading and expect a count of zero |
| Change Record Type's radio can't be checked | The real radio input is a hidden 1 by 1 pixel element | Click the option's label, as a user would, and confirm it's checked before Next |
| A flow screen's data table radio | A one-row-selection table draws its own radio over the real one; a click only focuses the cell, and the row is selected with Space | Click the radio's position, press Space if it isn't checked, and confirm it's checked |
| Inline edit pencils drawn late | On a long Dynamic Forms page, a plain click on the pencil sometimes timed out after the record had opened | Bring the section into view and retry until the pencil is there |
| List view column headers have no height | Headers never counted as visible | Check a column by its "Sort by: <column>" button |
| A report groups a lookup by its own name | The grouping showed as "User: Full Name", not the field label | Check the grouping by the name the report shows |
| A report draws rows as they scroll | A later group wasn't on the page yet | Switch Detail Rows off for the run (not saved) so every group shows |
| Some pages have no `/lightning` path | A page opened by a guessed Lightning address said "Page doesn't exist" or stuck on "Loading..." | Open it from its link in the app's navigation, by role and name |
| A full-page capture with a picklist open | The page resized and the open list closed before the capture | Capture the visible window only while a list is open |
| Inline edit scrolls the page | The header and record type dropped out of the screenshot | Scroll to the top and wait until the page reports it's there before the capture |
| The video's pointer and outline in screenshots | The markers that guide the viewer in the video showed in the evidence images | Hide the overlays for each screenshot and show them again after |
| The New URL skips the record type chooser | `/lightning/o/Case/new` opened a form for the default record type, and clicking New on a list after a save was unreliable | Open `/lightning/o/Case/new?useRecordTypeCheck=1` |
| The record type chooser in a console | It opens as a "New Case" tab, each option's name is its label plus its description, and the label covers the radio button | Match the option by its label at the start of the name, click the label as a user would, and close the tab by "Close New Case" |
| Actions hide in the overflow menu | A check that Delete was missing passed only because Delete was under "Show more actions" | Open the overflow menu and read its items before checking an action is absent |
| An inline-edit save is asynchronous | A query straight after the save read the old value | Poll the query until the value changes, with a time limit |
| A report counts every round's records | A report built for the test showed every round's records, not just this round's | Open the report with a filter value for the round's prefix (`?fv0=<prefix>`), which narrows that view without changing the saved report |
| A report exists in one org only | A scenario that reads a report fails in the next sandbox | Copy the report into each sandbox before that scenario runs there |
| Hard-coded IDs | Record type IDs from one sandbox broke in another | Look up record types, users and reports by name or developer name |
| Getting to a page through menus | A step that wasn't testing navigation failed on the App Launcher or the list view switcher | Open the page by URL (`listViewPath`, `reportPath`, `recordPath`, then `goTo`) |
| A list view shows every run's records | Rows from earlier rounds pushed the round's records off screen, and checks matched the wrong row | Type the round's record prefix into the list's search box (`listSearch`) and wait until every row matches |
| List view checkboxes are labelled by position | Each row checkbox is named "Select Item 2", not after its record, so a checkbox picked by label picks whatever row is second | Find the row by its text (`listRow`), then its checkbox |
| Every check by screen alone can pass on a broken script | A script that clicks the wrong thing can still take a screenshot | Every scenario also confirms its result by query, so a broken script fails rather than passes |

## Evidence

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| The browser tool's screenshots are downscaled | Saved images were about 960 pixels wide, too blurry for evidence | Playwright saves at twice screen resolution (3200 pixels wide). For browser-tool sessions, `capture_chrome_window.sh` captures the Chrome window at full Retina resolution |
| Screen Recording permission off | Window titles read blank and the capture found no window | Turn on Screen Recording for the app running the shell, in System Settings, Privacy & Security |
| `sips` can't crop on current macOS | The crop step failed | The capture script crops in Swift with CoreGraphics |
| Chrome's "debugging this browser" banner | A dark bar across the top of every capture while Claude's browser tools were attached | The capture script finds the banner by its colour and trims it |
| Chrome's toolbar height varies by machine | The capture script's default of 87 points was measured on one Mac, with one Chrome layout | Measure it once on your machine (window height less the page's `innerHeight`) and pass it to the capture script |
| Reruns overwrote earlier evidence | A failed attempt's screenshots and video were lost once a later attempt passed | Each attempt's evidence moves to `attempts/A<n>/` before the next attempt runs |
| Duplicate test records in a round | Rerunning a scenario that creates records made a second set | A scenario refuses to create records if that round's already exist |
| A duplicate rule blocks the next attempt | A contact created with the same email in an earlier attempt tripped the org's duplicate rule | Make values a matching rule checks unique per attempt |
| Video format | Playwright 1.64 records WebM with VP9. Chrome plays it. Whether Google Drive's preview plays VP9 wasn't confirmed | Watch the videos in Chrome before publishing. Check Drive's preview on your first published round |
| One video per step is too many | A story with several steps meant a short video per step for the client to review, each one signing in again | Group steps into flows: one user session, one video, a chapter card per step |
| A video opened on its own made no sense | A reviewer who opened one flow video didn't know which ticket or user it was about | Every flow video starts with an opening card: the ticket, what it shows, the steps, the user, the org and round. It says only what this video covers, with no count of videos or pointer to other evidence |
| Card wording redone after recording | A recorded round was run again only to fix a card's wording | Approve the storyboard from the last green rehearsal (every card, caption and screenshot in order) before recording |
| A screenshot on top of a video | Steps declared both, doubling what the reviewer checked | Choose one evidence tag per step when the steps are drafted. A step with a video gets no screenshot |

## Sharing

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| Claude's Bash tool can't write to Drive | `Operation not permitted` on `~/Library/CloudStorage`, because the agent's shell is sandboxed | Run `publish.sh` from your own terminal or the Claude desktop app's Terminal panel. Don't grant Full Disk Access to Claude to get around it: that opens your mail, messages and every cloud folder |
| Run manifests name people | The Setup Audit Trail section lists who changed what in the org | Manifests stay local. Only the final evidence is published |
| The ledger holds cost figures | The evidence folder was shared with the client | The ledger stays on your machine. Only evidence goes to Drive |
| Testing Feedback that explains the method | When the client can read Jira, attempts or tool names invite questions about the testing rather than the result | Post only the final passing round: who it ran as, the result per step, the evidence and record links |
| Sandbox email is off by default | A step that sent an email did nothing: new sandboxes set Access to Send Email to System email only | Turn email to All email right before the send and back straight after, in a browser context of its own so it's not in the video, and restore it if a step fails. Use `example.com` addresses only |
| The Deliverability page is a frame | Setup's Deliverability page runs in a frame, and a Lightning pop-up covered its Save | Open the frame's own page on the Setup domain directly, save, and read the value back after a reload |

## Test Steps and build checks

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| Tickets rarely fix the order of values | An exact list comparison failed on order alone | Compare value lists as sets, and show the org's order in the row |
| A retired picklist value can still be offered | The value set had it inactive, but the field describe still offered it, and existing records keep it | Check both the value set and the field describe, and note it in the row |
| Some specs are behaviours, not values | A formula or a validation rule's condition can't match a ticket's sentence | Record the org's value (whitespace collapsed) as Recorded, and let a QA scenario prove the behaviour |
| Salesforce doesn't keep a profile's clone source | "Cloned from Standard User" can't be checked | Record the profile's license as Recorded |
| Description limits | Profile descriptions stop at 255 characters, so a longer ticket wording can never match | Ask for the ticket's wording to be shortened rather than calling it a Mismatch |
| Extra or missing components are easy to miss | A check that only looks for what the ticket names passes an org with extra values or grants | Add "(any other)" rows, "Exists: No" rows for anything the ticket dropped, and an "Other permissions" row for grants outside the expected set |
| A hidden space looks right in Setup | An org value with a trailing space or curly quote reads correctly on screen | The build check treats any hygiene flag in an org value as a Mismatch |
| Test steps written from the build | A flow copied the build sub-task, so a build that drifted from the story passed | Draft the user steps from the story's acceptance criteria. The build spec feeds only the build check |
| A criterion nobody tested | A criterion was dropped between story and script, and no one noticed until review | End the Test Steps with a Coverage section, one bullet per criterion, saying where each is proven |
| A later sandbox fails on what wasn't deployed yet | A build check in the second sandbox failed on items built after the deployment | Outside the first sandbox, check only what the deployment carried |
| Test users don't deploy | The second sandbox had the metadata but no test users | Users are data. Make the test users a step in the deployment, with the same profiles and permission sets |
| Names shared across types | A queue and a public group with the same API name were read as one | Read each by its type |
| Testing the plain persona | Every test user had extra permission sets, so nobody tested the base access | Keep one test user on the base permission set only |

## Counts and data

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| pandas turns real values into blanks | By default it reads "None", "N/A", "NA" and "NULL" as missing, so a real picklist value counted as zero | Read every file as text exactly as written (pandas `dtype=str, keep_default_na=False, na_filter=False`; Polars `infer_schema_length=0`). `data_hygiene.py` does this |
| Trailing and double spaces | Values with a trailing space looked unused because they didn't match | The hygiene audit flags leading, trailing and double spaces, odd dashes and quotes, and hidden whitespace, and stops on anything not in the allow list |
| Polars guesses types from the first rows | A column guessed as numbers from its first rows can fail or change values further down | Read with `infer_schema_length=0` so everything is text |
| A blank test by string | A helper like `str(v) in ("", "nan", "None")` treated the real value "None" as blank | Never test for blank by comparing strings. Read as text and test for an empty string only |
| The allow list matches exact values | Allowing "None" didn't cover "none" or "None " | Add each exact variant you've explained, so a new one still stops the script |
| Zero from a grouped count | A source system's grouped report suppressed small groups, so zero meant "a few" | Say so next to any figure from a grouped count |
| SOQL ignores case and Python doesn't | A comparison that passed in a query failed in the script | Match on a normalized key, but display and build the original value |
| 15-character record IDs | Joins between data from different sources quietly missed rows | Normalize every ID to 18 characters before a join |
| Metadata on disk goes stale | The admin keeps building, so a retrieve from earlier in the day can describe a page that has since changed | Retrieve fresh before every build check |
| Wrong figures in write-ups | Counts came out wrong more than once, for the reasons in this table | No figure leaves the ledger or a build check until the hygiene audit is clean and an independent subagent has recomputed it from the raw data |

## Jira

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| Rich-text custom fields need ADF | Through the API, custom rich-text fields such as Test Steps and Testing Feedback don't take markdown the way the description does | Write custom rich-text fields as Atlassian Document Format. Descriptions accept markdown |
| Writes that don't land | A write can succeed and still not show what was intended | Read every Jira write back |

## Cost

| Gotcha | How it showed up | Fix |
| --- | --- | --- |
| Long conversations cost more per step | Each model call re-reads the whole conversation, so later steps in a long session cost more | Start a fresh session for each story |
| Scripting looks expensive the first time | Scripting a story costs several times what one round costs by hand with a browser tool | Script stories that will be rerun. Each story runs at least twice (partial sandbox, then full sandbox), so a script pays for itself by its third round |
| Session logs repeat a model call | Claude Code writes one model call across several log lines, so tokens double-counted | `session_cost.py` dedupes by message ID |
| Tool results look like prompts | The log records tool results as "user" lines, which would start the clock again | Only user text without a tool result counts as a prompt |
| The last call falls outside the window | Log times have fractions of a second, so an end time on the minute missed the final call | The end of a window is inclusive. Add a second if in doubt |
| A subagent on another model | A model missing from the price list would be costed wrongly | `session_cost.py` stops on any model not in `PRICES`. Check the prices against Anthropic's pricing page before you rely on them |
| Ledger CSVs opened in Excel | Saving from Excel reformats dates and IDs | Read the ledger through `qa_report.py`, or open the CSVs read-only |
| Tooling checks skew the averages | Runs that only tested a change to the QA tooling inflated the cost per scenario | Tag them `tooling-check`. The report leaves them out of the figures and lists them separately |
