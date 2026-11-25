// Example QA sub-task (PROJ-21): one flow, three steps, on the standard Case object. A working demo of the harness;
// for a new story, start from ../templates/story.spec.ts instead, which has every kind of step.
// Rehearse: QA_ROUND=R0 QA_REASON=rehearsal npm run qa -- example   until every step passes
// Record:   QA_ROUND=R1 QA_REASON=first-run npm run qa -- example   (see README.md)
//
// Flow F1 is one session as the test user: they land in the app, open New Case and see which Status values it
// offers, then save a Case with Case Origin picked. One video (PROJ-21-F1.webm) that opens with an opening card and
// has a chapter card per step; each step keeps its own result, and a step that fails stops the rest of the flow,
// which show as not run. Every step is tagged [Video], so none takes a screenshot on top.
// The Case it saves is named "QA PROJ-21 <round> S3 Case" and stays in the org as the record of the test.
// Only standard objects and fields, so it runs in any sandbox with Cases and the app below.
import { test, expect, BrowserContext, Page } from '@playwright/test';
import { ORG_ALIAS, RECORD_PREFIX } from '../lib/config';
import {
  orgInfo, query, fieldSnapshot, signInAs, appPath, expectApp, pickValue, picklistOptions, recordIdFromUrl, qaTicket,
} from '../lib/salesforce';
import {
  Run, Scenario, ScenarioResult, openRun, writeManifest, recordCatalog, finishRun, startFlow, step,
  startVideo, stopVideo, openingCard, chapter, beat,
} from '../lib/evidence';
import { testUser } from '../lib/testUsers';

// --- This story's settings ---------------------------------------------------------------------------------------
const TICKET = qaTicket('PROJ-21');                       // the QA sub-task (qaTicket: see lib/salesforce.ts)
const PARENT = 'PROJ-20';                                 // its story or Task, for the run manifest
const EPIC_FOLDER = 'E1 Example Epic';                    // evidence folder for the epic
const TICKET_FOLDER = 'PROJ-21 E1.1 Example Case intake'; // evidence folder for the QA sub-task
const TEST_USER = testUser('Specialist');                 // this machine's user for the persona (personas.json)
// The app's label as users see it (appPath also takes its developer name). If the project builds a custom console
// app, use its label, not the standard one's.
const APP = 'Service Console';
const ORIGIN = 'Phone';                                   // a Case Origin value to save with
// The Status values the story says New Case offers. Left null, the step only checks that every value offered is an
// active Status value, so the example runs in any sandbox. Whether closed values show on the form depends on
// Support Settings, so list exactly what the story says the user sees.
const EXPECTED_STATUSES = null as string[] | null;
// ---------------------------------------------------------------------------------------------------------------

const ROUND = process.env.QA_ROUND ?? '';
const PREFIX = `${RECORD_PREFIX} ${TICKET} ${ROUND}`;

// The steps in the QA sub-task's Test Steps, with each one's evidence tag as approved. A step on video declares no
// screenshot. With the ledger add-on on, its catalog is written from this list.
const SCENARIOS: Scenario[] = [
  { id: 'S1', flow: 'F1', title: `The specialist lands in ${APP}`, expected: `${APP} opens`, evidence: ['video'] },
  {
    id: 'S2', flow: 'F1', title: 'New Case offers the expected Status values',
    expected: EXPECTED_STATUSES ? `Status offers ${EXPECTED_STATUSES.join(', ')}` : 'Status offers only active Status values',
    evidence: ['video'],
  },
  {
    id: 'S3', flow: 'F1', title: 'A Case saves with Case Origin picked',
    expected: `the Case saves with Case Origin ${ORIGIN}, created by ${TEST_USER}`, evidence: ['video'],
  },
];

// What the run manifest records about the build, so the next run can say what changed. Collect the metadata the
// story builds: fields, validation rules (validationRuleSnapshot), picklist values per record type (recordTypeValues).
function buildSnapshot(): Record<string, unknown> {
  return {
    'Case.Origin': fieldSnapshot('Case', 'Origin'),
    'Case.Status': fieldSnapshot('Case', 'Status'),
  };
}

test.describe.configure({ mode: 'serial' });

let run: Run;
let dir: string;
let changes: string[] = [];
let lightningUrl: string;
let closedTabs: string[] = [];
const results: ScenarioResult[] = [];
const caseUrl = (id: string) => `${lightningUrl}/lightning/r/Case/${id}/view`;

test.beforeAll(async () => {
  run = openRun({ ticket: TICKET, epicFolder: EPIC_FOLDER, ticketFolder: TICKET_FOLDER, round: ROUND, specFile: __filename });
  dir = run.dir;
  lightningUrl = orgInfo().lightningUrl;
  changes = writeManifest(run, PARENT, buildSnapshot());
  recordCatalog(TICKET, SCENARIOS, run.specFile);
});

test.afterAll(async () => {
  // A run that stopped before any scenario started (sign-in, the manifest) isn't recorded as an attempt.
  if (!run || !results.length) return;
  const header = [
    `- **Org:** ${ORG_ALIAS}`,
    `- **Run as:** ${TEST_USER}`,
    `- **Records:** a Case named "${PREFIX} S3 Case", left in the org as the record of the test`,
  ];
  finishRun(run, header, results, { changes, closedTabs });
});

// One test per flow. A step that stands alone (a different user, or its own records) can be its own test, as in
// ../templates/story.spec.ts.
test('F1 the test user opens a new Case and saves it', async ({ browser }) => {
  const steps = startFlow(run, SCENARIOS, 'F1', results);
  // Records stay in the org, so a later attempt in the same round adds the attempt to the name when it's taken.
  // (The stricter choice, for a scenario whose records must be made once per round: expect no records with this
  // round's name and stop if there are.)
  const base = `${PREFIX} S3 Case`;
  const subject = query(`SELECT Id FROM Case WHERE Subject = '${base}'`).length ? `${base} A${run.attempt}` : base;

  let context: BrowserContext | undefined;
  let page: Page | undefined;
  try {
    // Login As lands straight in the app, so the video starts there rather than on Home or a list view.
    ({ context, page, closedTabs } = await signInAs(browser, TEST_USER, appPath(APP)));
    const p = page;
    await startVideo(p, dir, `${TICKET}-F1`);
    await openingCard(p, run, { video: 1, name: 'The test user opens a new Case and saves it', steps: '1 to 3', runAs: TEST_USER });

    await step(steps.S1, async () => {
      await chapter(p, `Step 1 of 3: ${steps.S1.title}`, steps.S1.expected);
      await expectApp(p, APP);
      steps.S1.seen.push(`${TEST_USER} lands in ${APP}`);
      await beat(p, 1500);
    });

    await step(steps.S2, async () => {
      await chapter(p, `Step 2 of 3: ${steps.S2.title}`, steps.S2.expected);
      // Plain /new uses the user's default record type and skips the record type chooser. To test the chooser,
      // use recordTypeChooser in lib/salesforce.ts.
      await p.goto(`${lightningUrl}/lightning/o/Case/new`);
      await expect(p.getByRole('heading', { name: /^New Case/ })).toBeVisible();
      const offered = (await picklistOptions(p, 'Status')).filter((o) => o !== '--None--');
      // The list stays open for a few seconds, so the video shows what it offers.
      await beat(p, 3000);
      await p.keyboard.press('Escape');
      steps.S2.seen.push(`Status offers: ${offered.join(', ')}`);
      expect(offered.length, 'Status offers at least one value').toBeGreaterThan(0);
      if (EXPECTED_STATUSES) {
        expect([...offered].sort()).toEqual([...EXPECTED_STATUSES].sort());
      } else {
        const active = fieldSnapshot('Case', 'Status').activeValues;
        expect(offered.filter((v) => !active.includes(v)), 'values that are not active Status values').toEqual([]);
      }
    });

    await step(steps.S3, async () => {
      await chapter(p, `Step 3 of 3: ${steps.S3.title}`, steps.S3.expected);
      await p.getByRole('textbox', { name: 'Subject', exact: true }).fill(subject);
      // The label on the form, which can differ from the story's wording for a relabelled field.
      await pickValue(p, 'Case Origin', ORIGIN);
      await beat(p);
      await p.getByRole('button', { name: 'Save', exact: true }).click();
      await p.waitForURL(/\/lightning\/r\/Case\/\w{18}\/view/);
      const id = recordIdFromUrl(p.url());
      await expect(p.getByText(subject).first()).toBeVisible();
      await beat(p, 2500);
      steps.S3.links.push({ label: subject, url: caseUrl(id) });
      // Confirm by query, so a script that clicked the wrong thing fails rather than passes.
      const row = query(`SELECT Origin, Status, CreatedBy.Name FROM Case WHERE Id = '${id}'`)[0];
      expect(row?.Origin, 'Case Origin saved').toBe(ORIGIN);
      expect(row?.CreatedBy?.Name, 'created by the test user').toBe(TEST_USER);
      steps.S3.seen.push(`Saved with Case Origin ${row.Origin}, Status ${row.Status}, created by ${row.CreatedBy.Name} (checked by query)`);
    });
  } finally {
    if (page) await stopVideo(page);
    await context?.close();
  }
});
