# QA

QA tooling for Salesforce build tickets in Jira. It answers two questions, each with its own evidence:

- **Was it built as specified?** A build check compares the org's metadata, read-only, with the build sub-task's spec. One row per component and property, by metadata type and API name, with expected and actual. No Setup screenshots.
- **Does it behave right?** Each QA scenario gets the evidence that shows it: a screenshot for a state (a value list, a message, a layout), a video where the behaviour matters (a rule firing, a record created end to end), or query output where nothing runs as a user. The Playwright scripts that produce it live in [`playwright/`](playwright/README.md).

Copy this folder into your project (for example as `qa/`), set the project settings below, and gitignore `evidence/` and `.drive-dir`. For effort and cost figures, add the optional [QA ledger](../../addons/qa-ledger/README.md) as `ledger/` in this folder.

## What's in this folder

| File | What it is |
| --- | --- |
| [build_check.py](build_check.py) | The build check: what a build ticket specifies against what the org has. Writes `<ticket>-build-check-<date>.md` and `.json` here. Ships with one worked example on Case Origin and Case Status that runs in any org |
| [data_hygiene.py](data_hygiene.py) | The hygiene audit: text-only CSV readers, a matching key, and an audit that flags trailing spaces, odd dashes and quotes, hidden whitespace and NA-like values. Run `python3 data_hygiene.py selftest` once after copying |
| [value_quirks.py](value_quirks.py) | The allow list for the audit: values someone has checked and explained. Starts empty |
| [evidence_index.py](evidence_index.py) | Writes a round's `evidence-index.csv`: the evidence each scenario needs and what the round folder has. Stops a publish when anything is missing |
| [publish.sh](publish.sh) | Copies a reviewed, complete round and its newest build check to the QA Evidence folder in Google Drive. Refuses rehearsals. Never deletes anything there |
| [shared_summary.py](shared_summary.py) | Writes the shared copy of a round's run summary for `publish.sh`: each step's result and what was seen, without the attempts, what changed between them or the test tooling |
| [test_users.py](test_users.py) | Creates a tester's own test users from `playwright/personas.json`, named for the tester: plan, rehearse, apply, check, rollback (see the playwright README, Test users) |
| `tests/` | Unit tests for `test_users.py` that need no org: `python3 -m unittest discover -s tests` |
| [playwright/](playwright/README.md) | The click-through scenarios: sign-in and Login As, rehearsals, flows, screenshots, video, the run summary and the ledger rows, with a spec template and an example on the standard Case object |
| `capture_chrome_window.sh` | Full-resolution screenshots of the test's Chrome window (documented in its own header) |
| `environment-tickets.json` | Optional. Maps the primary org's QA sub-tasks to another org's, when each environment has its own (see the playwright README, Rounds and attempts) |
| `ledger/` | Optional: the [QA ledger add-on](../../addons/qa-ledger/README.md), copied here. Turned on for runs with `QA_LEDGER=1` |
| `evidence/` | Local only (gitignore it): run evidence by epic, QA sub-task and round, rehearsals, and the ledger's data |

## Project settings

| Setting | Where | Default |
| --- | --- | --- |
| The org QA runs in | `--org`, else `SF_ORG`, else `DEFAULT_ORG` in `build_check.py` | `my-partial-sandbox` |
| Who to test as, and the access each holds | `playwright/personas.json` (shared, committed) | two examples on Standard User |
| This machine's test users | `playwright/test-users.local.json` (gitignored; `test_users.py --apply` writes it) | none; a run stops and says what to run |
| Playwright settings (org alias, record prefix, evidence folder, time zone, ledger on or off) | `playwright/lib/config.ts` | see the playwright README |
| Jira project key and Sprint field (ledger add-on) | `JIRA_PROJECT` and `SPRINT` in `ledger/jira_snapshot.py` | `PROJ`, `customfield_10020` |
| The Drive QA Evidence folder | `.drive-dir` here, or `QA_DRIVE_DIR` | none; `publish.sh` asks |
| Where publishes are logged | `QA_SYNC_LOG` | a reminder only |
| Time zone for ledger times (ledger add-on) | `QA_TZ` (`session_cost.py`), `ET` (`jira_snapshot.py`) | `UTC` (set `QA_TZ` to your team's zone) |
| Model prices (ledger add-on) | `PRICES` in `ledger/session_cost.py` | API list prices as of 2026-10; check them |

## The build check

```bash
sf project retrieve start --metadata StandardValueSet:CaseOrigin StandardValueSet:CaseStatus \
    --target-metadata-dir build-check-retrieve --unzip --target-org my-partial-sandbox
python3 build_check.py PROJ-21 --retrieve <the folder in build-check-retrieve that holds package.xml>
```

Results are **Match**, **Mismatch** or **Recorded**. Recorded is for a ticket that states a behaviour rather than a value, such as a validation rule's formula: the org's value is shown for the reader, and a QA scenario shows the behaviour. The summary counts only compared rows.

Values are compared exactly as the org holds them. A value list is compared as a set, since tickets rarely fix the order, and the org's order is shown. Every value list is audited, so a trailing space or curly quote in an org value is a Mismatch even when it looks right on screen.

### Adding a check for a new ticket

1. Read the build sub-task. For each component, write down the properties it fixes and their exact values.
2. In `build_check.py`, add a `SPEC_<ticket>` constant and a `check_<ticket>(c, R)` function. `R` is the retrieve folder. Parse the files you need with `ET.parse(R / "<folder>/<name>.<suffix>")` and read elements with `t(el, "tag")`.
3. Call `c.row(type, api_name, property, expected, actual)` for one value, `c.values(...)` for a value list, and pass `"Recorded"` as the result for a behaviour. Use the `note` for anything a reader needs, such as "the page itself is built under another ticket".
4. Add the ticket to `CHECKS` with its spec ticket, a title, the function, and what it reads.
5. Retrieve what it needs and run it. Read every Mismatch before you believe it: some are the check, not the build.
6. The file's `Verified` line says "not yet independently recomputed" until an independent recompute matches. Then rerun with `--verified "figures verified <date> by independent recompute"`. `publish.sh --build-check-only` refuses an unverified check.

Things that catch people out when writing checks:

- **A removed picklist value can still be offered.** Check the value set and the field describe (`sf sobject describe`). Records that already hold the value keep it either way, so say so in the note.
- **Some things the metadata doesn't keep.** Salesforce doesn't record which profile a profile was cloned from. Record what you can see (its license) and mark it Recorded.
- **Some limits shape the spec.** A profile description holds at most 255 characters, and only one business hours can be the org default. Check the ticket's wording fits before calling a shortened value a Mismatch, and get the ticket updated.
- **Check what shouldn't be there too.** Add an "(any other)" row for extra record types, holidays or permissions, and an "Exists: No" row for anything the ticket dropped.
- **Users are checked by query**, with the `sf(["data", "query", "-q", ...], c.org)` helper. Test users should have `example.com` email addresses.

## Publishing a round

Run `publish.sh` yourself, from a real terminal, once a round is complete and you've watched every video:

```bash
./publish.sh "evidence/<epic>/PROJ-21 Case Origin values/2026-01-05 my-partial-sandbox R2"
./publish.sh --build-check-only "evidence/<epic>/PROJ-61 Business hours"
```

- **Complete rounds only.** It stops unless every scenario has the evidence it declares (`evidence_index.py`).
- **Never a rehearsal.** A folder under `evidence/rehearsal/` is refused.
- **Final evidence only.** Earlier attempts, run manifests and `results.json` stay on this machine. The manifests can list names from the org's Setup Audit Trail. The run summary goes as its shared copy (`shared_summary.py`), without the attempts or the test tooling.
- **The shared build check leaves out its Verified line.** The local copy keeps it.
- **The ledger stays local.** It holds your team's cost figures, and the Drive folder may be shared with the client.
- **It never deletes in Drive.** It adds and updates files only.
- **Run it from a real terminal.** A sandboxed agent shell may be unable to write to `~/Library/CloudStorage`, where Google Drive for desktop keeps its folders. Don't grant the agent Full Disk Access to get around it.

Then link the QA sub-task's Drive folder from its Testing Feedback entry. Attach nothing in Jira.

## The numbers gate

No count from these tools goes into a write-up, ticket, page, workbook or client message until two things are true:

1. The script that produced it ran the hygiene audit on every value list it loaded, with each flag explained in `value_quirks.py`.
2. An independent recompute, by someone or an agent that hasn't seen the conclusions, rebuilt the figures from the raw data and they match.

The document then says so in one line, for example "Figures verified 2026-01-05 by independent recompute".

What the hygiene audit protects you from:

- **Read values as text, exactly as written.** pandas turns "None", "N/A", "NA" and "NULL" into blanks by default, so a real picklist value counts as zero. Use `read_csv_polars` (or `read_csv_pandas` when a library needs pandas).
- **Trailing and double spaces.** "Pending Review " never equals "Pending Review" in an exact match, so a used value reads as unused.
- **Match on a normalized key, display the original.** Use `canon()` to decide two values are the same. Build and show the value exactly as the source has it, and report pairs that match only after normalizing.
- **SOQL is case-insensitive; Python isn't.** A count that agrees in the org and differs in a script is often this.
- **15 and 18 character IDs.** The 15-character form is case-sensitive. Convert every ID to 18 characters before a join or comparison.
- **Zero can mean few.** A grouped count from a source system or report may hide small groups, so a zero there isn't proof of none. Say so next to the figure.
