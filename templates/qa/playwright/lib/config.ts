import path from 'path';

// Project settings, in one place. Each story's own settings (ticket, epic folder, test users) go in the settings block
// at the top of its spec. Change these once when you start a project.

// The sf CLI alias of the org to test, so the same script runs against a partial sandbox, then a full sandbox.
// Override per run with SF_ORG=my-full-sandbox.
export const ORG_ALIAS = process.env.SF_ORG ?? 'my-partial-sandbox';

// Dropped from the alias in evidence folder names, so "acme-partial" files as "partial". Leave empty to keep the alias.
export const ORG_PREFIX_TO_DROP: string = '';

// The org whose QA sub-tasks the specs name. When each environment has its own QA sub-task with the same Test Steps
// (one for the partial sandbox, another for the full sandbox), a spec names this org's ticket, and qaTicket() in
// salesforce.ts maps it to the other org's ticket from ENVIRONMENT_TICKETS_FILE. Without that file, a spec's ticket is
// used in every org.
export const PRIMARY_ORG_ALIAS = process.env.QA_PRIMARY_ORG ?? 'my-partial-sandbox';

// { "<other org alias>": { "<primary org's QA sub-task>": "<that org's QA sub-task>" } }. Optional.
export const ENVIRONMENT_TICKETS_FILE = path.join(__dirname, '..', '..', 'environment-tickets.json');

// The API version for REST calls (the UI API). Any org answers versions up to its own release, so an older version is
// the safe default. Raise it if a call needs something newer.
export const API_VERSION = process.env.SF_API_VERSION ?? '62.0';

// Every record a script creates starts with this, then the ticket, round and scenario: "QA PROJ-21 R1 S3 Phone".
// The console tab guard keeps a tab only when it's one of this ticket's records ("QA PROJ-21" in its label or Subject).
export const RECORD_PREFIX = 'QA';

// Where run output goes: one folder per epic, QA sub-task and round, plus rehearsals and the ledger. It captures org
// pages, so keep it out of version control (the qa folder's .gitignore covers evidence/). The default is the qa
// folder's evidence/, beside this playwright folder, where the build check, publish script and ledger also look.
// Override with QA_EVIDENCE_DIR.
export const EVIDENCE_DIR = process.env.QA_EVIDENCE_DIR ?? path.join(__dirname, '..', '..', 'evidence');

// The time zone for dates in folder names, the run summary and the ledger. Use the team's working time zone, so a
// late-evening run doesn't land in tomorrow's folder.
export const TIME_ZONE = process.env.QA_TZ ?? 'UTC'  // set QA_TZ (or this default) to your team's zone, for example 'America/Chicago';

// The QA ledger is an optional add-on (addons/qa-ledger in the kit, copied to <qa folder>/ledger/). Off by default:
// runs write no ledger rows and read no Jira snapshot. QA_LEDGER=1 turns it on. Everything else works without it.
export const LEDGER_ENABLED = process.env.QA_LEDGER === '1';
