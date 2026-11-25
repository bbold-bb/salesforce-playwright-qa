// TEMPLATE. Copy to ../tests/<TICKET>.spec.ts and replace every TODO. Kept at the current rules (README.md, Adding a
// story); when a rule changes, change this file in the same commit. It lives outside tests/ so no run picks it up.
//
// <Epic and story> QA - <name> (<TICKET>): steps 2 to N of the Test Steps (approved by <who approves>, <date>).
// Rehearse: QA_ROUND=R0 QA_REASON=rehearsal npm run qa -- <TICKET>      until every step passes
// Record:   QA_ROUND=R1 QA_REASON=first-run npm run qa -- <TICKET>      once, after the rehearsal is green
//
// Step 1 is the build check (../../build_check.py <TICKET>). Then, in the order of the ticket's Test Steps:
//   S2        [Query]       nothing runs as a user; the rows are saved as the evidence
//   F1 S3 S4  [Video]       one user's session, one video, a card per step, no screenshot on top
//   S5        [Screenshot]  what a different user sees at one moment
// Coverage (copied from the ticket's Test Steps): criterion 1: S3. Criterion 2: S4 and S5. Criterion 3: build check.
// Criterion 4: tested in <other ticket>.
//
// Rules this file follows, so a copy does too:
// - SCENARIOS copies the ticket's steps and evidence tags as approved. A step on video declares no screenshot.
// - Every flow video opens with openingCard, and every step has a chapter card.
// - Every step checks its result by query as well as on screen, and says so in `seen`.
// - Elements are found by role and label, through the helpers in ../lib/salesforce. No position, XPath or CSS class.
// - Records are named "QA <TICKET> <round> S<n> <what>", looked up by name or developer name, and left in the org.
// - A helper needed by a second spec moves to ../lib, with a row in the README's patterns table.
// - A step that sends email wraps the send in withEmailOpen; afterAll then calls closeEmailIfOpen and passes
//   emailTotals() to finishRun as extra.email (README.md, Email sending).
import { test, expect, Page } from '@playwright/test';
import { RECORD_PREFIX } from '../lib/config';
import {
  ORG_ALIAS, qaTicket, orgInfo, query, recordTypeIds, signInAs, pickValue, recordIdFromUrl, fieldSnapshot,
  openReportFromFolder, hideDetailRows, reportGroup,
} from '../lib/salesforce';
import {
  Run, Scenario, ScenarioResult, openRun, keepEarlierEvidence, writeManifest, recordCatalog, finishRun, startFlow, step,
  startVideo, stopVideo, openingCard, chapter, caption, shot, beat, saveQuery,
} from '../lib/evidence';
import { testUser } from '../lib/testUsers';

// TODO: the QA sub-task, its story or Task, and the evidence folders (the QA sub-task's key and title).
const TICKET = qaTicket('PROJ-000');
const PARENT = 'PROJ-000';
const EPIC_FOLDER = 'E0 Epic name';
const TICKET_FOLDER = `${TICKET} E0.0 Story name`;
const ROUND = process.env.QA_ROUND ?? '';
const PREFIX = `${RECORD_PREFIX} ${TICKET} ${ROUND}`;
const TOTAL_STEPS = 5; // the ticket's Test Steps, the build check included
// TODO: the fewest users the criteria need. A second user only when a criterion is about a second person. Each is an entry
// in personas.json and becomes this machine's user for it (README.md, Test users), so never type a user's name.
const SPECIALIST = testUser('Specialist');
const SUPERVISOR = testUser('Supervisor');
// TODO: what the story builds, by label as a user reads it and by API name for queries.
const TYPE = { label: 'Support Request', api: 'Support_Request' }; // a Case record type
const FIELD = { label: 'Product Line', api: 'Product_Line__c', value: 'Hardware' };
const PERMISSION_SET = { label: 'Case Base', api: 'Case_Base' }; // the permission set that grants the field
const FOLDER = 'Service Reports';
const REPORT = { label: 'Cases by Product Line', api: 'Cases_by_Product_Line', grouping: 'Product Line' };

// TODO: one entry per step after the build check, in the ticket's words, with the ticket's evidence tag.
const SCENARIOS: Scenario[] = [
  { id: 'S2', title: `Who can edit ${FIELD.label}`, expected: `${PERMISSION_SET.label} gives edit access (criterion 3)`, evidence: ['query'] },
  { id: 'S3', flow: 'F1', title: `Log a case and pick ${FIELD.value}`, expected: `it saves as ${FIELD.value} (criterion 1)`, evidence: ['video'] },
  { id: 'S4', flow: 'F1', title: `Run ${REPORT.label}`, expected: `the new case is counted under ${FIELD.value} (criterion 2)`, evidence: ['video'] },
  { id: 'S5', title: `The supervisor runs ${REPORT.label}`, expected: `it runs, grouped by ${REPORT.grouping} (criterion 2)`, evidence: ['screenshot'] },
];

// TODO: the metadata this story builds, as plain values, so the next run's manifest can say what changed.
function buildSnapshot(): Record<string, unknown> {
  const snap: Record<string, unknown> = { [`Field Case.${FIELD.api}`]: fieldSnapshot('Case', FIELD.api) };
  for (const r of query(`SELECT DeveloperName, FolderName, LastModifiedDate FROM Report WHERE DeveloperName = '${REPORT.api}'`)) {
    snap[`Report ${r.DeveloperName}`] = { folder: r.FolderName, lastModified: r.LastModifiedDate };
  }
  return snap;
}

test.describe.configure({ mode: 'serial' });

let run: Run;
let changes: string[] = [];
const closedTabs: string[] = [];
let lightningUrl: string;
let recordTypes: Record<string, string>;
const results: ScenarioResult[] = [];

const caseUrl = (id: string) => `${lightningUrl}/lightning/r/Case/${id}/view`;
const one = (id: string) => query(`SELECT Id, CaseNumber, ${FIELD.api} FROM Case WHERE Id = '${id}'`)[0];
// A step that stands alone (a query, or a different user's screenshot): its own result, with earlier evidence kept.
const standalone = (id: string): ScenarioResult => {
  keepEarlierEvidence(run, id);
  const r: ScenarioResult = { ...SCENARIOS.find((s) => s.id === id)!, seen: [], links: [], screenshots: [] };
  results.push(r);
  return r;
};
// A name a later attempt in the round can still use: records stay in the org.
const subjectFor = (what: string) => {
  const s = `${PREFIX} ${what}`;
  return query(`SELECT Id FROM Case WHERE Subject = '${s}'`).length ? `${s} A${run.attempt}` : s;
};

async function newCase(page: Page, subject: string) {
  await page.goto(`${lightningUrl}/lightning/o/Case/new?recordTypeId=${recordTypes[TYPE.api]}`);
  await expect(page.getByRole('heading', { name: `New Case: ${TYPE.label}` })).toBeVisible();
  await page.getByRole('textbox', { name: 'Subject', exact: true }).fill(subject);
  await pickValue(page, 'Case Origin', 'Phone'); // TODO: any other field the form requires on save
}

async function save(page: Page, subject: string): Promise<string> {
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.waitForURL(/\/lightning\/r\/Case\/500\w{15}\/view/);
  await expect(page.getByText(subject).first()).toBeVisible();
  return recordIdFromUrl(page.url());
}

test.beforeAll(async () => {
  run = openRun({ ticket: TICKET, epicFolder: EPIC_FOLDER, ticketFolder: TICKET_FOLDER, round: ROUND, specFile: __filename });
  lightningUrl = orgInfo().lightningUrl;
  recordTypes = recordTypeIds('Case');
  changes = writeManifest(run, PARENT, buildSnapshot());
  recordCatalog(TICKET, SCENARIOS, run.specFile);
});

test.afterAll(async () => {
  // TODO: if a step changes anything it must put back (a setting, an assignment), restore it here first.
  if (!run || !results.length) return;
  finishRun(run, [
    `- **Org:** ${ORG_ALIAS}`,
    `- **Run as:** a query for step 2; ${SPECIALIST} for flow F1 (steps 3 and 4); ${SUPERVISOR} for step 5`,
    `- **Records:** cases named "${PREFIX} S<step> <what>", left in the org as the record of the test`,
    '- **Step 1** is the build check, published with the round',
  ], results, { changes, closedTabs });
});

// [Query] Nothing runs as a user. Save what was asked and the rows that came back, then check them.
test('S2 who can edit the field', async () => {
  const r = standalone('S2');
  await step(r, async () => {
    const soql = `SELECT Parent.Name, PermissionsEdit FROM FieldPermissions WHERE Field = 'Case.${FIELD.api}' AND Parent.Name = '${PERMISSION_SET.api}'`;
    const rows = query(soql);
    saveQuery(run.dir, `${TICKET}-S2`, soql, rows);
    expect(rows, `${PERMISSION_SET.label} has a row for the field`).toHaveLength(1);
    expect(rows[0].PermissionsEdit, `${PERMISSION_SET.label} can edit it`).toBe(true);
    r.seen.push(`${PERMISSION_SET.label} gives edit access to ${FIELD.label} (checked by query)`);
  });
});

// [Video] One user's session, one video. The opening card, then a chapter card and a step per Test Step.
test('F1 the specialist logs a case and finds it in the report', async ({ browser }) => {
  const r = startFlow(run, SCENARIOS, 'F1', results);
  const { context, page, closedTabs: closed } = await signInAs(browser, SPECIALIST, '/lightning/o/Case/list');
  closedTabs.push(...closed);
  await startVideo(page, run.dir, `${TICKET}-F1`);
  await openingCard(page, run, { video: 1, name: 'The specialist logs a case and finds it in the report', steps: '3 and 4', runAs: SPECIALIST });
  let id = '';
  try {
    await step(r.S3, async () => {
      const subject = subjectFor(`S3 ${FIELD.value} picked`);
      await chapter(page, `Step 3 of ${TOTAL_STEPS}: ${r.S3.title}`, r.S3.expected, `As ${SPECIALIST}, a ${TYPE.label} case.`);
      await newCase(page, subject);
      await pickValue(page, FIELD.label, FIELD.value);
      await beat(page);
      id = await save(page, subject);
      const row = one(id);
      expect(row[FIELD.api], 'saved value').toBe(FIELD.value);
      r.S3.seen.push(`${row.CaseNumber} "${subject}": ${FIELD.value} picked and saved (checked by query)`);
      r.S3.links.push({ label: `${row.CaseNumber} ${subject}`, url: caseUrl(id) });
      await beat(page, 1500);
    });

    await step(r.S4, async () => {
      await chapter(page, `Step 4 of ${TOTAL_STEPS}: ${r.S4.title}`, r.S4.expected, `Open the report from ${FOLDER}.`);
      await page.goto(`${lightningUrl}/lightning/o/Report/home`);
      const v = await openReportFromFolder(page, FOLDER, REPORT.label);
      await caption(page, 'Detail Rows off, to show only the counts');
      await hideDetailRows(v);
      await expect(reportGroup(v, REPORT.grouping, FIELD.value), `${FIELD.value} group`).toBeVisible();
      const counted = query(`SELECT Id FROM Case WHERE Id = '${id}' AND ${FIELD.api} = '${FIELD.value}'`);
      expect(counted, 'the step 3 case holds the value the report groups on').toHaveLength(1);
      r.S4.seen.push(`${REPORT.label} runs from ${FOLDER} and shows a ${FIELD.value} group; the step 3 case holds ${FIELD.value} (checked by query)`);
      await beat(page, 2500);
    });
  } finally {
    await stopVideo(page);
    await context.close();
  }
});

// [Screenshot] What a different user sees at one moment, with no process to follow. No video.
test('S5 the supervisor runs the report', async ({ browser }) => {
  const r = standalone('S5');
  const { context, page, closedTabs: closed } = await signInAs(browser, SUPERVISOR, '/lightning/o/Report/home');
  closedTabs.push(...closed);
  try {
    await step(r, async () => {
      const v = await openReportFromFolder(page, FOLDER, REPORT.label);
      await expect(v.getByRole('button', { name: REPORT.grouping, exact: true })).toBeVisible();
      const report = query(`SELECT Id, FolderName FROM Report WHERE DeveloperName = '${REPORT.api}'`);
      expect(report[0]?.FolderName, 'the report is in the folder').toBe(FOLDER);
      r.seen.push(`${REPORT.label} runs for ${SUPERVISOR}, grouped by ${REPORT.grouping}; it sits in ${FOLDER} (checked by query)`);
      r.screenshots.push(`${TICKET}-S5.png`);
      await shot(page, run.dir, `${TICKET}-S5`, { windowOnly: true });
    });
  } finally {
    await context.close();
  }
});
