// Acme Support QA - Contact Channel (ACME-11): steps 2 to 4 of the Test Steps.
import { test, expect, Page } from '@playwright/test';
import {
  ORG_ALIAS, orgInfo, query, recordTypeIds, signInAs, pickValue, recordIdFromUrl, fieldSnapshot,
  openReportFromFolder, hideDetailRows, reportGroup,
} from '../lib/salesforce';
import {
  Run, Scenario, ScenarioResult, openRun, keepEarlierEvidence, writeManifest, recordCatalog, finishRun, startFlow, step,
  startVideo, stopVideo, openingCard, chapter, caption, beat, saveQuery,
} from '../lib/evidence';
import { testUser } from '../lib/testUsers';

const TICKET = 'ACME-11';
const PARENT = 'ACME-11';
const EPIC_FOLDER = 'E1 Case intake';
const TICKET_FOLDER = 'ACME-11 E1.1 Contact Channel';
const ROUND = process.env.QA_ROUND ?? '';
const PREFIX = `QA ${TICKET} ${ROUND}`;
const TOTAL_STEPS = 4;
const AGENT = testUser('SupportAgent');
const TYPE = { label: 'Support Request', api: 'Support_Request' };
const FIELD = { label: 'Contact Channel', api: 'Contact_Channel__c', value: 'Email' };
const FOLDER = 'Support Reports';
const REPORT = { label: 'Cases by Contact Channel', api: 'Cases_by_Contact_Channel', grouping: 'Contact Channel' };

const SCENARIOS: Scenario[] = [
  { id: 'S2', flow: 'F1', title: `Create a ${TYPE.label} with ${FIELD.value}`, expected: `it saves with ${FIELD.value} (criterion 1)`, evidence: ['video'] },
  { id: 'S3', flow: 'F1', title: `Run ${REPORT.label}`, expected: `the new case is counted under ${FIELD.value} (criterion 3)`, evidence: ['video'] },
  { id: 'S4', title: `Support Agent access to ${FIELD.label}`, expected: 'read and edit (criterion 4)', evidence: ['query'] },
];

function buildSnapshot(): Record<string, unknown> {
  return { [`Field Case.${FIELD.api}`]: fieldSnapshot('Case', FIELD.api) };
}

test.describe.configure({ mode: 'serial' });

let run: Run;
let changes: string[] = [];
const closedTabs: string[] = [];
let lightningUrl: string;
let recordTypes: Record<string, string>;
const results: ScenarioResult[] = [];

const one = (id: string) => query(`SELECT Id, CaseNumber, ${FIELD.api} FROM Case WHERE Id = '${id}'`)[0];
const standalone = (id: string): ScenarioResult => {
  keepEarlierEvidence(run, id);
  const r: ScenarioResult = { ...SCENARIOS.find((s) => s.id === id)!, seen: [], links: [], screenshots: [] };
  results.push(r);
  return r;
};

async function newCase(page: Page, subject: string) {
  await page.goto(`${lightningUrl}/lightning/o/Case/new?recordTypeId=${recordTypes[TYPE.api]}`);
  await page.getByRole('textbox', { name: 'Subject', exact: true }).fill(subject);
}

test.beforeAll(async () => {
  run = openRun({ ticket: TICKET, epicFolder: EPIC_FOLDER, ticketFolder: TICKET_FOLDER, round: ROUND, specFile: __filename });
  lightningUrl = orgInfo().lightningUrl;
  recordTypes = recordTypeIds();
  changes = writeManifest(run, PARENT, buildSnapshot());
  recordCatalog(TICKET, SCENARIOS, `qa/playwright/tests/${TICKET}.spec.ts`);
});

test.afterAll(async () => {
  if (!run || !results.length) return;
  finishRun(run, [`- **Org:** ${ORG_ALIAS}`], results, { changes, closedTabs });
});

test('F1 the agent records a channel and finds it in the report', async ({ browser }) => {
  const r = startFlow(run, SCENARIOS, 'F1', results);
  const { context, page, closedTabs: closed } = await signInAs(browser, AGENT, '/lightning/o/Case/list');
  closedTabs.push(...closed);
  await startVideo(page, run.dir, `${TICKET}-F1`);
  await openingCard(page, run, { video: 1, name: 'The agent records a channel and finds it in the report', steps: '2 and 3', runAs: AGENT });
  let id = '';
  try {
    await step(r.S2, async () => {
      const subject = `${PREFIX} S2 ${FIELD.value}`;
      await chapter(page, `Step 2 of ${TOTAL_STEPS}: ${r.S2.title}`, r.S2.expected, `As ${AGENT}.`);
      await newCase(page, subject);
      await pickValue(page, FIELD.label, FIELD.value);
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      await page.waitForURL(/\/lightning\/r\/Case\/500\w{15}\/view/);
      id = recordIdFromUrl(page.url());
      expect(one(id)[FIELD.api]).toBe(FIELD.value);
      r.S2.seen.push(`saved with ${FIELD.value} (checked by query)`);
    });
    await step(r.S3, async () => {
      await chapter(page, `Step 3 of ${TOTAL_STEPS}: ${r.S3.title}`, r.S3.expected, `From ${FOLDER}.`);
      const v = await openReportFromFolder(page, FOLDER, REPORT.label);
      await caption(page, 'Detail Rows off, to show only the counts');
      await hideDetailRows(v);
      await expect(reportGroup(v, REPORT.grouping, FIELD.value)).toBeVisible();
      expect(query(`SELECT Id FROM Case WHERE Id = '${id}' AND ${FIELD.api} = '${FIELD.value}'`)).toHaveLength(1);
      r.S3.seen.push(`counted under ${FIELD.value} (checked by query)`);
      await beat(page, 2500);
    });
  } finally {
    await stopVideo(page);
    await context.close();
  }
});

test('S4 the permission set gives edit access', async () => {
  const r = standalone('S4');
  await step(r, async () => {
    const soql = `SELECT Parent.Name, PermissionsEdit FROM FieldPermissions WHERE Field = 'Case.${FIELD.api}' AND Parent.Name = 'Support_Agent'`;
    const rows = query(soql);
    saveQuery(run.dir, `${TICKET}-S4`, soql, rows);
    expect(rows[0].PermissionsEdit).toBe(true);
    r.seen.push('Support Agent can edit (checked by query)');
  });
});
