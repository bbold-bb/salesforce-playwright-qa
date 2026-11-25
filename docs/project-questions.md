# Project questions

Everything someone has to decide to set the kit up for their project and way of working. The starter prompt ([starter-prompt.md](starter-prompt.md)) has Claude run this as an interview, one group at a time. You can also answer it on your own first and hand Claude the answers.

How Claude runs it:

- Ask one group at a time, and wait for the answers before the next group.
- Never guess an answer. Where an answer names something in the org or Jira (an alias, a field, a user, an app), check it against the live system before writing it anywhere.
- After each group, show where each answer will go (the file and the line, or the `CLAUDE.md` rule) and write it only after the person agrees.
- An answer of "not sure yet" is fine. Note it as open and move on; the kit's default stands until it's answered.

## 1. Org, sandboxes and aliases

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Which sandbox does QA run in first, and what is its sf CLI alias? | Every script, build check and sign-in reads the org from this alias | `ORG_ALIAS` in `qa/playwright/lib/config.ts`; the default org in `build_check.py`; the `CLAUDE.md` QA rules |
| What path does a build take through environments (for example partial sandbox, then full sandbox, then UAT, then production)? | Decides which environments get a QA sub-task, and whether each one gets a recorded round or a build check and a rehearsal only | `CLAUDE.md` rule "Testing path"; a per-environment QA plan when you reach the second environment |
| What are the aliases of the later sandboxes? | Runs there use `SF_ORG=<alias>`, and evidence folders are named by org | Each run's `SF_ORG`; `ORG_PREFIX_TO_DROP` in `config.ts` if the aliases share a prefix |
| Is production ever in scope for QA? | The kit is built for sandboxes. Login As, test records and email changes don't belong in production | `CLAUDE.md`: "QA never runs against production" unless you decide otherwise |
| What time zone does the team work in? | Dates in folder names, run summaries and the ledger use it, so a late run doesn't land in tomorrow's folder | `TIME_ZONE` (`QA_TZ`) in `config.ts`; `QA_TZ` for the ledger add-on |

## 2. Jira project and fields

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| What is the Jira project key? | Ticket keys name specs, test records and evidence folders | The spec config block (`TICKET`, `PARENT`); `jira_snapshot.py` in the ledger add-on |
| Which issue types do you use for a story, a build item and a QA item? Is QA a sub-task of the story, of the build, or its own issue? | Claude needs to find the QA sub-task, its story and its build sub-task from any one of them | `CLAUDE.md` QA rules |
| Does every build get a QA sub-task, including shared Tasks? Which items get none (deployments, for example)? | Sets what "every build is tested" means on your project | `CLAUDE.md` QA rules |
| Which field holds the QA Test Steps, and which holds the results (for example Test Steps and Testing Feedback)? Is there a yes/no field for criteria met? | Claude reads the approved steps from one and drafts the results for the other | `CLAUDE.md` QA rules; [tech-stack.md](tech-stack.md) "In Jira" table |
| Are those fields rich text? | Through the API, rich-text custom fields need Atlassian Document Format, not markdown | `CLAUDE.md`: "rich-text custom fields need ADF; read every write back" |
| What happens on a failure: reopen the build sub-task, or open a bug? On a pass, which statuses change? | Decides the Jira update Claude drafts after each round | `CLAUDE.md` QA rules |
| How are QA sub-tasks named and labelled? | Keeps new QA items consistent with the rest of the board | `CLAUDE.md` naming rule |
| Will the client see Jira? | If so, Testing Feedback states results only, with no mention of how the testing was done or the tools | `CLAUDE.md` approvals rule |

## 3. Roles and approvals

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Who owns the story (description, user story, acceptance criteria)? | No one else edits those fields; a change is proposed in a comment | `CLAUDE.md`, by role |
| Who approves the QA sub-task's Test Steps before any script is written? | The script implements that approved text, so this is the main handoff (see [how-test-steps-flow.md](how-test-steps-flow.md)) | `CLAUDE.md` "Test Steps first" rule |
| Who watches the videos and approves the storyboard before a recorded run, and the evidence before it's shared? | First of the two human approvals | `CLAUDE.md` approvals rule |
| When a second tester runs QA, is their own review of their videos and Testing Feedback enough, or does the approver review those too? | With two or more testers, waiting on one approver holds up passing rounds. The default is that the approver reviews everything | `CLAUDE.md` approvals rule |
| Who approves the exact Testing Feedback text before it goes to Jira? | Second approval. Often the same person as above | `CLAUDE.md` approvals rule |
| Who builds (the Salesforce Administrator), and do they run their own smoke test? | The build sub-task's spec feeds the build check; the builder's smoke test is separate from QA | `CLAUDE.md` QA rules |
| Who settles an unclear evidence tag? | Each answer becomes a row in the decided-cases table | Harness README, Adding a story; [writing-test-steps.md](writing-test-steps.md) |

Write roles in `CLAUDE.md`, not names, unless your team prefers names. People change; roles don't.

## 4. Personas, test users and the app

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Who do the stories need tested as? Usually personas (specialist, supervisor, manager), but also anyone else: a specialist with an add-on, a person with no access | Each flow runs as the person the story is about. Each gets an entry, named in a word or two with no spaces | `playwright/personas.json`; each spec's `testUser('<entry>')` |
| For each of them: which profile, role, permission set groups, permission sets, licenses, public groups and queues? Or is there a user who already holds the right access? | The script creates every tester's users from this list. Keep one entry on the base access only, so the plain persona is tested | `playwright/personas.json`. `test_users.py --from-user` prints an entry from an existing user's access |
| Who will run QA, and how should each tester's name show? | Each tester gets a set of users named for them (`SpecialistTest Ana P`), so testers don't see each other's records | `test_users.py --tester "<name>"`, run by each tester |
| Are there enough free user licenses in each QA sandbox for one user per entry per tester? | A small sandbox can run out. The script's plan shows what's free and stops when short | Fewer entries, or `--persona` for the ones a tester needs |
| Which sandboxes need the users? | Users are data, not metadata, so they don't move with a deployment, and a refresh can remove them | Your deployment checklist; the per-environment QA plan |
| Which app does each persona work in, and is it their default? | A user who lands in the wrong app makes the video show the wrong screen | The test users' default app; `appPath` in specs |

## 5. Signing in and Login As

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Is "Administrators Can Log in as Any User" on in each QA sandbox? | The harness signs in as the admin through the sf CLI, then uses Login As. No script holds a password | Setup, Login Access Policies; [setup-guide.md](setup-guide.md) part 3 |
| Which admin user is the sf CLI authorized as? Does it have a passkey or MFA that blocks browser sign-in? | The one-time URL from `sf org open --url-only` gets past both | `sf org login web` once per sandbox |
| Will more than one person run QA in the same sandbox at the same time? | Each has users of their own, but org-wide settings a test changes (email deliverability, a config record) are still shared, so agree before those runs. On one machine the harness runs one at a time and the rest wait | Team practice; the run lock |

## 6. Evidence and who can see it

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Where does published evidence go: a Google Drive folder, SharePoint, Confluence, or nowhere (local only)? | `publish.sh` copies to a synced folder; other targets need a change to it | `qa/.drive-dir`; `CLAUDE.md` approvals rule |
| Who can open that folder? The client? | Anything in it can be read by everyone with access, so the shared run summary leaves out attempts and tooling | `CLAUDE.md` approvals rule |
| Do you want video evidence at all, or screenshots and queries only? | Video needs ffmpeg and slows runs; some teams only need screenshots | `QA_VIDEO=0` per run, or the evidence tags you approve |
| Is the reviewer's player able to play WebM (VP9)? | Chrome plays it; check your sharing tool's preview on the first published round | First published round |

## 7. Sensitive data in the sandbox

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Is the QA sandbox a full copy or a partial copy of production data? Does it hold real names, emails or phone numbers? | Videos and screenshots capture whatever is on screen, and list views and reports show other records | `CLAUDE.md` evidence rule: what evidence may and may not show |
| Are there objects or fields that must never appear in evidence? | The review before publishing checks for them; reports used as evidence leave those columns out | `CLAUDE.md` evidence rule |
| Is sandbox email deliverability on? Should it be? | Sandboxes default to system email only. A step that sends email needs it turned on, briefly, and off again | `CLAUDE.md`; the harness's email switch |
| Is there client data on this machine that must never leave it? | Evidence, traces and the ledger stay local unless a rule says otherwise | `CLAUDE.md` hard rules; `.gitignore` |

## 8. Test records

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| What prefix do test records start with? The kit uses `QA <ticket> <round> S<n> <what>` | Lists and reports are narrowed to a round's records by this prefix, and the console tab guard keeps other records out of videos | `RECORD_PREFIX` in `config.ts`; `CLAUDE.md` test records rule |
| Do test records stay in the sandbox after QA? | The kit keeps them as the record of the testing, so anyone can open a record in its tested state from the Testing Feedback link | `CLAUDE.md` test records rule |
| Does a duplicate rule or matching rule stop records with the same name or email? | Repeated rounds then fail on the rule rather than the build; make values unique per round or attempt | Each spec |

## 9. Optional add-ons and extras

| Question | Why it matters | Where the answer goes |
| --- | --- | --- |
| Do you want to track what QA costs and how often it reruns? | The ledger add-on in [addons/qa-ledger/](../addons/qa-ledger/README.md) records every scenario run and each block of AI work at API list price | Copy the add-on into `qa/ledger/`; add the ledger rule to `CLAUDE.md` |
| Will the build check's figures go into documents others read? | Counts get a data hygiene audit and an independent recompute before they're shared | `CLAUDE.md` numbers rule |
| Which Claude model runs subagents (for example a recompute)? | Subagents may not inherit the parent's model | `CLAUDE.md` working rules |
| Who may run anything that writes to the org beyond test records (a Setup change, a data load)? | QA reads the org and creates test records only, unless someone with authority says otherwise | `CLAUDE.md` hard rules |

## After the interview

Claude should end with:

1. A table of every answer and where it was written.
2. The open questions, with the default the kit uses until each is answered.
3. The `CLAUDE.md` rules block from [starter-prompt.md](starter-prompt.md) with the answers filled in, shown in full before it's written.
