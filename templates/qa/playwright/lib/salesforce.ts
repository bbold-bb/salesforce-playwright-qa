import { execFileSync } from 'child_process';
import * as fs from 'fs';
import { Browser, BrowserContext, FrameLocator, Locator, Page, expect } from '@playwright/test';
import { ORG_ALIAS, API_VERSION, RECORD_PREFIX, PRIMARY_ORG_ALIAS, ENVIRONMENT_TICKETS_FILE } from './config';

export { ORG_ALIAS } from './config';

// When each environment has its own QA sub-task with the same Test Steps, a spec names its primary org's ticket
// (PRIMARY_ORG_ALIAS in config.ts); in another org it runs, names its records and files its evidence under that org's
// ticket, from ENVIRONMENT_TICKETS_FILE. Without the file, the spec's ticket is used in every org.
export function qaTicket(primary: string): string {
  if (ORG_ALIAS === PRIMARY_ORG_ALIAS || !fs.existsSync(ENVIRONMENT_TICKETS_FILE)) return primary;
  const map = JSON.parse(fs.readFileSync(ENVIRONMENT_TICKETS_FILE, 'utf8'));
  const ticket = map[ORG_ALIAS]?.[primary];
  if (!ticket) throw new Error(`No ${ORG_ALIAS} QA sub-task for ${primary}: add it to ${ENVIRONMENT_TICKETS_FILE}`);
  return ticket;
}

function sf(args: string[]): any {
  // The Playwright runner sets FORCE_COLOR, which makes the CLI colour its JSON. Turn it off, and strip any colour
  // codes that still get through, or JSON.parse fails.
  const env = { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1', SF_DISABLE_COLORS: 'true' };
  const out = execFileSync('sf', [...args, '-o', ORG_ALIAS, '--json'], { encoding: 'utf8', env, maxBuffer: 64 * 1024 * 1024 });
  return JSON.parse(out.replace(/\x1b\[[0-9;]*m/g, '')).result;
}

// Values come back as text, exactly as stored. Queries run as the CLI's admin user, not the test user, so use them to
// confirm what the test user did, never to decide what the test user can see.
export function query(soql: string): Record<string, any>[] {
  return sf(['data', 'query', '-q', soql]).records;
}

// Creates one record through the API, as the signed-in admin, and returns its Id. For test data a step needs in place
// before it runs (not for what the step itself tests).
export function createRecord(sobject: string, values: Record<string, string>): string {
  const pairs = Object.entries(values).map(([k, v]) => `${k}='${v.replace(/'/g, "\\'")}'`).join(' ');
  return sf(['data', 'create', 'record', '-s', sobject, '-v', pairs]).id;
}

export function toolingQuery(soql: string): Record<string, any>[] {
  return sf(['data', 'query', '--use-tooling-api', '-q', soql]).records;
}

// A REST GET through the CLI's session, for the UI API.
export function rest(urlPath: string): any {
  const env = { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1', SF_DISABLE_COLORS: 'true' };
  const out = execFileSync('sf', ['api', 'request', 'rest', urlPath, '-o', ORG_ALIAS], { encoding: 'utf8', env, maxBuffer: 64 * 1024 * 1024 });
  return JSON.parse(out.replace(/\x1b\[[0-9;]*m/g, ''));
}

// --- What the run manifest records about the build, so two runs can be compared. Each returns plain values. ---

export function fieldSnapshot(object: string, field: string) {
  const f = sf(['sobject', 'describe', '-s', object]).fields.find((x: any) => x.name === field);
  if (!f) throw new Error(`${object}.${field} not found`);
  return {
    label: f.label,
    helpText: f.inlineHelpText ?? '',
    activeValues: (f.picklistValues ?? []).filter((v: any) => v.active).map((v: any) => v.value),
  };
}

export function validationRuleSnapshot(object: string, name: string) {
  const row = toolingQuery(
    `SELECT Id FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '${object}' AND ValidationName = '${name}'`,
  );
  if (row.length !== 1) return { exists: false };
  // Metadata can only be read one row at a time, so it's a second query by Id.
  const m = toolingQuery(`SELECT Metadata FROM ValidationRule WHERE Id = '${row[0].Id}'`)[0].Metadata;
  return {
    exists: true,
    active: m.active,
    formula: m.errorConditionFormula,
    message: m.errorMessage,
    field: m.errorDisplayField ?? '',
    description: m.description ?? '',
  };
}

// The values a picklist offers on one record type, from the UI API: what the form should show.
export function recordTypeValues(object: string, field: string, recordTypeId: string): string[] {
  return rest(`/services/data/v${API_VERSION}/ui-api/object-info/${object}/picklist-values/${recordTypeId}/${field}`).values.map(
    (v: any) => v.value,
  );
}

// Setup changes since a time (UTC ISO), skipping user management (logins, Login As, passwords).
export function setupChangesSince(sinceIso: string): { when: string; by: string; section: string; what: string }[] {
  // SOQL datetime literals take no fractional seconds, so 2026-01-05T14:03:11.482Z becomes 2026-01-05T14:03:11Z.
  const since = sinceIso.replace(/\.\d+Z$/, 'Z');
  // Section can't be filtered in SOQL, so user management is left out here, in code.
  return query(
    `SELECT CreatedDate, CreatedBy.Name, Section, Display FROM SetupAuditTrail WHERE CreatedDate > ${since} ORDER BY CreatedDate LIMIT 2000`,
  )
    .filter((r) => r.Section !== 'Manage Users')
    .map((r) => ({ when: r.CreatedDate, by: r.CreatedBy?.Name ?? '', section: r.Section ?? '', what: r.Display ?? '' }));
}

// The org's id and addresses. Record links in the run summary use the Lightning address. If your org's My Domain
// isn't on my.salesforce.com, check the replace below.
export function orgInfo(): { id: string; instanceUrl: string; lightningUrl: string; username: string } {
  const r = sf(['org', 'display']);
  return {
    id: r.id,
    instanceUrl: r.instanceUrl,
    lightningUrl: r.instanceUrl.replace('.my.salesforce.com', '.lightning.force.com'),
    username: r.username,
  };
}

export function userIdByName(name: string): string {
  const rows = query(`SELECT Id FROM User WHERE Name = '${name}' AND IsActive = true`);
  if (rows.length !== 1) throw new Error(`Expected one active user named ${name}, found ${rows.length}`);
  return rows[0].Id;
}

// Record type Ids by developer name, looked up each run, so a script never holds an Id and runs in any sandbox.
export function recordTypeIds(object = 'Case'): Record<string, string> {
  const rows = query(`SELECT Id, DeveloperName FROM RecordType WHERE SobjectType = '${object}' AND IsActive = true`);
  return Object.fromEntries(rows.map((r) => [r.DeveloperName, r.Id]));
}

// --- Signing in. No passwords anywhere. ---

// The browser contexts a run has opened, so a rehearsal can save what each open page showed when a step failed
// (lib/evidence.ts, failureSnapshot). signInAsAdmin tracks its own; a spec that opens a context itself, such as a
// visitor's chat page or a public site, passes it through trackContext.
const contexts: BrowserContext[] = [];
export function trackContext(context: BrowserContext): BrowserContext {
  contexts.push(context);
  return context;
}
export function openPages(): Page[] {
  return contexts.flatMap((c) => { try { return c.pages(); } catch { return []; } }).filter((p) => !p.isClosed());
}

// Signs in as the CLI's admin user with a one-time URL from `sf org open --url-only`, so the script holds no password.
// The URL is used once and never written to disk or logs, and nothing about the session is saved.
export async function signInAsAdmin(browser: Browser, path: string): Promise<{ context: BrowserContext; page: Page }> {
  const url: string = sf(['org', 'open', '--url-only', '--path', path]).url;
  const context = trackContext(await browser.newContext());
  const page = await context.newPage();
  await page.goto(url);
  await page.waitForURL((u) => u.pathname.startsWith('/lightning'), { timeout: 90_000 });
  return { context, page };
}

// Admin session, then Login As the test user (Setup, Login Access Policies, "Administrators Can Log in as Any User"
// must be on). Lands straight on targetPath, so the video starts on the scenario rather than Home or a list view.
// Without an app in targetPath the user lands in whichever app they last used. If the scenario needs a particular
// app, pass appPath(...) and check it with expectApp: a test user sitting in the standard Service Console when the
// story built a custom console app (or the other way round) is an easy detour to miss.
export async function signInAs(browser: Browser, userName: string, targetPath: string) {
  const org = orgInfo();
  const userId = userIdByName(userName);
  const { context, page } = await signInAsAdmin(browser, '/lightning/setup/SetupOneHome/home');
  await loginAs(page, org, userName, userId, targetPath);
  const closedTabs = await closeNonTestTabs(page);
  return { context, page, org, closedTabs };
}

const currentUser = (page: Page) => page.evaluate(() => (window as any).$A?.get?.('$SObjectType.CurrentUser.Id') ?? '').catch(() => '');
const adminIdOf = (org: { username: string }) => query(`SELECT Id FROM User WHERE Username = '${org.username}'`)[0].Id.slice(0, 15);

async function loginAs(page: Page, org: ReturnType<typeof orgInfo>, userName: string, userId: string, targetPath: string) {
  const url = `${org.instanceUrl}/servlet/servlet.su?oid=${org.id}&suorgadminid=${userId}` +
    `&retURL=${encodeURIComponent('/')}&targetURL=${encodeURIComponent(targetPath)}`;
  // Login As fails three ways: net::ERR_ABORTED while its redirects still complete, the "Logged in as" banner not
  // rendering in a console app, and the page staying signed in as the admin. So the switch is confirmed from
  // Lightning's own current user, and Login As is repeated only while that is still the admin: started again as the
  // test user, it lands in Classic.
  const adminId = adminIdOf(org);
  const target = userId.slice(0, 15);
  for (let attempt = 1; ; attempt++) {
    await page.goto(url).catch((e) => {
      if (!/ERR_ABORTED/.test(String(e))) throw e;
    });
    const ok = await expect.poll(() => currentUser(page), { timeout: 45_000 }).toMatch(new RegExp(`^${target}`)).then(() => true, () => false);
    if (ok) break;
    const now = String(await currentUser(page));
    if (attempt >= 3 || !now.startsWith(adminId)) throw new Error(`Login As ${userName} didn't take: the page is signed in as ${now || 'nobody'}`);
  }
}

// Moves a page that's signed in as one test user to another, in the same tab, so one video can follow several sessions:
// a fresh one-time URL makes it the admin again, then Login As. It's a new sign-in for the user. "Log out as" and
// /secur/logout.jsp can't do this: both end at the login page.
export async function switchUser(page: Page, userName: string, targetPath: string) {
  const org = orgInfo();
  await page.goto(sf(['org', 'open', '--url-only', '--path', '/lightning/setup/SetupOneHome/home']).url);
  await expect.poll(() => currentUser(page), { timeout: 60_000 }).toMatch(new RegExp(`^${adminIdOf(org)}`));
  await loginAs(page, org, userName, userIdByName(userName), targetPath);
  await closeNonTestTabs(page);
}

// Clears what the browser keeps for the org's sites (cookies, local storage, IndexedDB, cache storage), so the next
// sign-in starts like one in a fresh browser. Lightning keeps object info, record types included, in persistent browser
// storage, and a new Login As in the same browser can reuse it: a permission set given through the API didn't show its
// record type at the next sign-in, though it showed in a fresh browser. Follow it with switchUser.
export async function clearOrgBrowserData(page: Page) {
  const org = orgInfo();
  // The org's three origins: the instance, Lightning, and Setup (Salesforce's own Setup domain for the My Domain).
  const origins = [org.instanceUrl, org.lightningUrl, org.instanceUrl.replace('.my.salesforce.com', '.my.salesforce-setup.com')];
  const cdp = await page.context().newCDPSession(page);
  for (const origin of origins) await cdp.send('Storage.clearDataForOrigin', { origin, storageTypes: 'all' });
  await cdp.detach();
}

// The QA sub-task this run is for, set by openRun (lib/evidence.ts), so the tab cleanup keeps only this ticket's records.
let runTicket = '';
export function setRunTicket(ticket: string) {
  runTicket = ticket;
}

// Console tabs carry over from earlier sessions, so a video can show records nobody meant to record (including real
// data copied into a partial or full sandbox, or another ticket's test records). Before recording, close every tab
// that isn't one of this ticket's records: a Case whose Subject holds "<RECORD_PREFIX> <ticket>", or a record whose
// tab label does, such as an email "RE: QA PROJ-21 ...". A new ticket's video then starts clear and shows only its own
// records. Without a run ticket (a helper used outside a run), any record named with the prefix or TEST is kept.
// A standard (non-console) app has no workspace tabs, so there's nothing to close.
export async function closeNonTestTabs(page: Page): Promise<string[]> {
  const closed: string[] = [];
  const workspaces = page.getByRole('navigation', { name: 'Workspaces' });
  await workspaces.waitFor({ state: 'attached', timeout: 10_000 }).catch(() => undefined);
  if ((await workspaces.count()) === 0) return closed;
  // Console workspace tabs are the ones with a Close button; pages such as reports have tab strips of their own.
  // A console with nothing open has an empty Workspaces bar and no tabs, which is fine.
  await page.getByRole('tab').first().waitFor({ timeout: 5_000 }).catch(() => undefined);
  if ((await page.getByRole('tab').count()) === 0) return closed;
  // The selected tab is the page the script just opened, so it's left alone. A tab strip Salesforce marks
  // aria-hidden (a standard page's own strip, such as Reports) isn't a console workspace tab, so it's skipped.
  // A selected Case tab is checked too when the run has a ticket: landing on an app reopens the user's last workspace
  // tab, selected, which can be another ticket's record.
  const tabs: { label: string; selected: boolean }[] = await page.locator('[role="tab"][title]').evaluateAll((els) =>
    els
      .filter((e) => e.getBoundingClientRect().width > 0)
      .filter((e) => !e.closest('[aria-hidden="true"]'))
      .filter((e) => [...(e.closest('li')?.querySelectorAll('button') ?? [])].some((b) => /^Close/.test((b.textContent ?? '').trim())))
      .map((e) => ({ label: (e.getAttribute('title') ?? '').trim(), selected: e.getAttribute('aria-selected') === 'true' })),
  );
  const labels = tabs.filter((t) => !t.selected || (runTicket && /^\d{8} \| Case$/.test(t.label))).map((t) => t.label);
  const mine = (text: string) => (runTicket ? text.includes(`${RECORD_PREFIX} ${runTicket}`) : new RegExp(`^(${RECORD_PREFIX}|TEST|Test)\\b`).test(text));
  for (const label of labels) {
    // A Case tab is titled by its number ("00001234 | Case"), so its Subject is looked up to decide.
    const caseNo = label.match(/^(\d{8}) \| Case$/)?.[1];
    let isTest = mine(label);
    if (caseNo) {
      const subject: string = query(`SELECT Subject FROM Case WHERE CaseNumber = '${caseNo}'`)[0]?.Subject ?? '';
      isTest = mine(subject);
    }
    if (!label || isTest) continue;
    const tab = page.locator(`[role="tab"][title="${label.replace(/"/g, '\\"')}"]`).first();
    await tab.locator('xpath=ancestor::li[1]').getByRole('button', { name: /^Close/ }).first().click();
    closed.push(label);
  }
  return closed;
}

// --- Lightning helpers. Find things by label and name, the way a person reads the screen, never by position or by
// Salesforce's internal page code. ---

export const escapeRegExp = (x: string) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Picks a value in a Lightning picklist (base combobox), on the page or inside one form. The label is the one on the
// page, which can differ from the story's wording (a relabelled standard field keeps its old label on the form until
// someone renames it).
// The combobox has to be open before its value is clicked: a click that lands while the previous field's list is still
// closing can leave this one shut, and the option click then waits out its timeout. So it opens the list, waits for it
// to show it's expanded, opens it once more if not, then clicks the visible option.
export async function pickValue(scope: Page | Locator, label: string, value: string) {
  const box = scope.getByRole('combobox', { name: label, exact: true });
  await box.click();
  try {
    await expect(box).toHaveAttribute('aria-expanded', 'true', { timeout: 3_000 });
  } catch {
    await box.click();
    await expect(box).toHaveAttribute('aria-expanded', 'true', { timeout: 5_000 });
  }
  // The list can still be drawing when it reports itself open, leaving the option present but not yet clickable.
  // Wait for the option and bring it into view; if it still won't take the click, close the list and open it once more.
  const option = scope.getByRole('option', { name: value, exact: true }).filter({ visible: true }).first();
  try {
    await option.waitFor({ timeout: 10_000 });
    await option.scrollIntoViewIfNeeded();
    await option.click({ timeout: 10_000 });
  } catch {
    await box.press('Escape');
    await box.click();
    await expect(box).toHaveAttribute('aria-expanded', 'true', { timeout: 5_000 });
    await option.scrollIntoViewIfNeeded();
    await option.click();
  }
}

// Picks a record in a lookup field: types the name, then chooses the suggestion whose title is that name.
export async function pickLookup(scope: Page | Locator, label: string, name: string) {
  const box = scope.getByRole('combobox', { name: label, exact: true });
  await box.click();
  await box.fill(name);
  // A `has` locator is matched from inside each option, so it's built from the page, not from the form.
  const page = 'page' in scope ? scope.page() : scope;
  await scope.getByRole('option').filter({ has: page.getByTitle(name, { exact: true }) }).first().click();
}

// The values a Lightning picklist offers, in the order shown. It leaves the list open; press Escape to close it.
// Take the screenshot with windowOnly while it's open.
export async function picklistOptions(page: Page, label: string): Promise<string[]> {
  const box = page.getByRole('combobox', { name: label, exact: true });
  await box.click();
  const listId = await box.getAttribute('aria-controls');
  const list = listId ? page.locator(`[id="${listId}"]`) : page.getByRole('listbox');
  await expect(list.getByRole('option').first()).toBeVisible();
  const names = await list.getByRole('option').allInnerTexts();
  return names.map((n) => n.trim());
}

// Change Owner on a record page, to a queue. The dialog searches Users until Queues is picked, and offers only queues
// that take the record's object: a queue set up only for another object (Messaging Session, say) doesn't appear.
export async function changeOwnerToQueue(page: Page, queue: string) {
  await page.getByRole('button', { name: 'Change Owner' }).first().click();
  const dialog = page.getByRole('dialog').filter({ has: page.getByRole('combobox', { name: 'Select New Owner' }) });
  await dialog.getByRole('button', { name: /^Select New Owner.*Pick an object/ }).click();
  await page.getByRole('menuitem', { name: 'Queues', exact: true }).click();
  const box = dialog.getByRole('combobox', { name: 'Select New Owner' });
  await box.click();
  await box.pressSequentially(queue, { delay: 40 });
  await page.getByRole('option', { name: new RegExp(`^${escapeRegExp(queue)}`) }).first().click();

  await page.getByRole('dialog').getByRole('button', { name: 'Submit', exact: true }).click();
}

// --- The console and related lists. README.md, "Console and report patterns". ---

// A related list on the open record, by its title ("Case Contact Roles"). The console keeps earlier records in the
// page, hidden, so only the visible list counts.
export function relatedList(page: Page, title: string): Locator {
  return page.locator('article')
    .filter({ has: page.getByRole('heading', { name: new RegExp(`^${escapeRegExp(title)}`) }) })
    .filter({ visible: true }).first();
}

// A console form by its heading ("New Case Contact Role"). In a console app, New opens a subtab, not a modal.
export function consoleForm(page: Page, heading: string): Locator {
  return page.getByRole('tabpanel')
    .filter({ has: page.getByRole('heading', { name: heading, level: 2 }) })
    .filter({ visible: true }).last();
}

// Clicks New on a related list and returns the form, open in its subtab and not yet saved. objectLabel is the
// object's label as the form heading shows it ("Case Contact Role" for "New Case Contact Role").
export async function newFromRelatedList(page: Page, listTitle: string, objectLabel: string): Promise<Locator> {
  const list = relatedList(page, listTitle);
  await list.scrollIntoViewIfNeeded();
  // A narrow related list can keep New under its "Show actions" menu instead of showing the button. Use the button
  // when it shows, otherwise the menu.
  const button = list.getByRole('button', { name: 'New', exact: true });
  if (await button.isVisible()) await button.click();
  else {
    await list.getByRole('button', { name: `Show actions for ${listTitle}` }).click();
    await page.getByRole('menuitem', { name: 'New', exact: true }).filter({ visible: true }).first().click();
  }
  const form = consoleForm(page, `New ${objectLabel}`);
  await expect(form).toBeVisible();
  return form;
}

// A row in a related list, by the name in its first column and, optionally, other text in the row. The grid's cells
// render in shadow DOM, so a row is matched by its row header and its text rather than by cell.
// It also matches the same record shown as a card, as an enhanced related list draws it in a narrow column: an article
// named for the record, with each column as a term and its value. text then has to be one of the card's values
// exactly, so "Lead" doesn't match a user named "Lead Test User".
export function relatedRow(list: Locator, header: string, text?: string): Locator {
  const page = list.page();
  const row = list.getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: new RegExp(`^${escapeRegExp(header)}( Preview)?$`) }) });
  const card = list.getByRole('article', { name: header, exact: true });
  if (!text) return row.or(card);
  return row.filter({ hasText: text })
    .or(card.filter({ has: page.getByRole('definition').filter({ hasText: new RegExp(`^${escapeRegExp(text)}$`) }) }));
}

// Opens a related-list row's action menu and chooses an action ("Edit", "Delete").
export async function rowAction(row: Locator, action: string) {
  await row.getByRole('button', { name: /Show.*actions/i }).click();
  await row.page().getByRole('menuitem', { name: action, exact: true }).click();
}

const subtabBar = (page: Page) => page.getByRole('navigation', { name: 'Active Workspace Subtabs' });

// Closes a console subtab by its label ("CR-0001 | Case Contact Role"). A save opens the new record in a subtab of
// its own; Lightning re-renders the tab while it loads, so the close is retried until the tab is gone.
export async function closeSubtab(page: Page, label: string) {
  const bar = subtabBar(page);
  const tab = bar.getByRole('tab', { name: label, exact: true });
  await expect(tab).toBeVisible();
  await expect(async () => {
    const close = bar.getByRole('button', { name: `Close ${label}`, exact: true });
    if (await close.count()) await close.click({ timeout: 3_000 });
    await expect(tab).toHaveCount(0, { timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
}

// Selects a console subtab by its label ("00001234 | Case"). With only the record's own tab left open, the console
// drops the subtab bar, so a tab that isn't shown is already the one in view.
export async function selectSubtab(page: Page, label: string) {
  const tab = subtabBar(page).getByRole('tab', { name: label, exact: true });
  if (!(await tab.count())) return;
  await expect(async () => {
    if ((await tab.getAttribute('aria-selected')) !== 'true') await tab.click({ timeout: 3_000 });
    await expect(tab).toHaveAttribute('aria-selected', 'true', { timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
}

// --- Record pages. ---

// A Dynamic Forms section on the open record, by its heading ("Case Details"). A section hidden by a visibility rule
// isn't rendered at all, so toHaveCount(0) means the record type doesn't show it.
export function recordSection(page: Page, label: string): Locator {
  return page.getByRole('heading', { name: label, exact: true }).filter({ visible: true });
}

// A field's inline edit pencil on a long Dynamic Forms page: Lightning can draw it late, or only once its section has
// been on screen, so this brings the section into view and retries until the pencil is really there, then clicks it.
export async function editFieldInline(page: Page, section: string, field: string) {
  const pencil = page.getByRole('button', { name: `Edit ${field}`, exact: true }).filter({ visible: true }).first();
  await expect(async () => {
    await recordSection(page, section).first().scrollIntoViewIfNeeded({ timeout: 5_000 });
    await expect(pencil).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 60_000 });
  await pencil.click();
}

// Starts an inline edit on a short record page (the edit button is named "Edit <field label>"). Inline edit scrolls
// the page, so this goes back to the top, where the page header (and the record type in it) shows in the screenshot.
// On a long Dynamic Forms page, use editFieldInline.
export async function startInlineEdit(page: Page, fieldLabel: string) {
  await page.getByRole('button', { name: `Edit ${fieldLabel}` }).click();
  await page.waitForTimeout(800);
  await scrollToTop(page);
}

export async function scrollToTop(page: Page) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
}

// Changes the open record's type the way a user does: Change Record Type in the highlights panel, choose the type,
// Next, then Save on the edit form that follows. Values in fields the new type hides stay on the record. The chooser
// is titled "Change <object> Record Type"; each radio is named by the type's label then its description, the current
// type is disabled, and another type is preselected, so the choice is checked rather than assumed.
export async function changeRecordType(page: Page, recordType: string) {
  await page.getByRole('button', { name: 'Change Record Type', exact: true }).filter({ visible: true }).first().click();
  const choose = page.getByRole('dialog').filter({ hasText: 'Record Type' }).filter({ visible: true });
  await expect(choose).toBeVisible();
  const radio = choose.getByRole('radio', { name: new RegExp(`^${escapeRegExp(recordType)}\\b`) });
  // The real input is a hidden 1 by 1 pixel element under Salesforce's drawn radio, so Playwright's check() can't act on
  // it. A mouse click at that spot is what a person's click does; toBeChecked still proves it took. The dialog is still
  // opening at first, so it waits for the position to hold still, and tries again until it's checked.
  await expect(async () => {
    const first = await radio.boundingBox();
    await page.waitForTimeout(500);
    const box = await radio.boundingBox();
    if (!first || !box || first.x !== box.x || first.y !== box.y) throw new Error(`The ${recordType} radio is still moving`);
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await expect(radio).toBeChecked({ timeout: 1_500 });
  }).toPass({ timeout: 30_000 });
  await choose.getByRole('button', { name: 'Next', exact: true }).click();
  const form = page.getByRole('dialog').filter({ has: page.getByRole('button', { name: 'Save', exact: true }) }).filter({ visible: true }).last();
  await expect(form).toBeVisible();
  await form.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(form).toBeHidden();
}

// Opens New with the record type check, which is what the New button does, so Salesforce shows the record type
// chooser, and returns the types it offers and the one selected. Plain /lightning/o/<object>/new skips the chooser
// and uses the user's default type, and clicking New on a list view after a save proved unreliable. In a console the
// chooser opens as a "New <object>" tab (close it with the "Close New <object>" button), each option a radio named by
// the type's label and description. `labels` is every type that could appear; the check that every radio is one of
// them catches a type nobody expected. `object` is the API name; pass objectLabel when the label differs.
export async function recordTypeChooser(
  page: Page, lightningUrl: string, object: string, labels: string[], objectLabel = object,
): Promise<{ offered: string[]; selected: string }> {
  await page.goto(`${lightningUrl}/lightning/o/${object}/new?useRecordTypeCheck=1`);
  await expect(page.getByRole('heading', { name: `New ${objectLabel}`, exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('radio').first()).toBeVisible();
  const offered: string[] = [];
  let selected = '';
  for (const label of labels) {
    if ((await typeRadio(page, label).count()) === 0) continue;
    offered.push(label);
    if (await typeRadio(page, label).isChecked()) selected = label;
  }
  expect(offered.length, 'every radio is one of the expected types').toBe(await page.getByRole('radio').count());
  return { offered, selected };
}

export const typeRadio = (page: Page, label: string) => page.getByRole('radio', { name: new RegExp(`^${escapeRegExp(label)} `) });

// Picks a type in the chooser. The radio's label covers the radio itself, so click the label, as a user does.
export async function chooseRecordType(page: Page, label: string) {
  await page.locator('label').filter({ has: typeRadio(page, label) }).click();
  await expect(typeRadio(page, label)).toBeChecked();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
}

// What a record page offers: its action buttons, and the overflow menu's items when there is one (left open; press
// Escape). Use it to show an action is or isn't offered, such as Delete.
export async function recordActions(page: Page): Promise<string[]> {
  const bar = page.locator('records-highlights2, .slds-page-header').first();
  await expect(bar).toBeVisible();
  const names = (await bar.getByRole('button').allInnerTexts()).map((x) => x.trim()).filter(Boolean);
  const more = bar.getByRole('button', { name: /Show more actions/ });
  if (await more.count()) {
    await more.first().click();
    await page.getByRole('menuitem').first().waitFor({ timeout: 5_000 }).catch(() => undefined);
    names.push(...(await page.getByRole('menuitem').allInnerTexts()).map((x) => x.trim()).filter(Boolean));
  }
  return names;
}

// The record Id from a record page's address, after a save. Wait for the address first:
// await page.waitForURL(/\/lightning\/r\/Case\/\w{18}\/view/).
export function recordIdFromUrl(url: string, object = 'Case'): string {
  const m = url.match(new RegExp(`/lightning/r/${object}/([A-Za-z0-9]{18})/view`));
  if (!m) throw new Error(`Not on a ${object} record page: ${new URL(url).pathname}`);
  return m[1];
}

// --- Reports. ---

// A report's body renders in the Report Viewer frame.
export const reportViewer = (page: Page): FrameLocator => page.frameLocator('iframe[title="Report Viewer"]');

// From Reports home, opens a report the way a user would (All Folders, the folder, the report) and waits for it to
// run. Grouping buttons are named as the report shows them: a group on a lookup's field reads "Owner: Full Name".
export async function openReportFromFolder(page: Page, folder: string, report: string): Promise<FrameLocator> {
  await page.getByRole('tab', { name: 'All Folders', exact: true }).click();
  await page.getByRole('link', { name: folder, exact: true }).first().click();
  await page.getByRole('link', { name: report, exact: true }).click();
  const v = reportViewer(page);
  await expect(v.getByText('Total Records', { exact: true })).toBeVisible({ timeout: 60_000 });
  return v;
}

// A report draws its rows as they scroll into view, so a later group isn't on the page yet. Switching off Detail Rows
// (it isn't saved) leaves one row per group, all drawn. Each group cell is named "<grouping>: <value>", such as
// "Case Origin: Phone"; reportGroup finds one.
export async function hideDetailRows(v: FrameLocator) {
  const toggle = v.getByRole('switch', { name: /^Detail Rows/ });
  await v.getByText('Detail Rows', { exact: true }).click();
  await expect(toggle).not.toBeChecked();
}

export const reportGroup = (v: FrameLocator, grouping: string, value: string) =>
  v.getByLabel(`${grouping}: ${value}`, { exact: true }).first();

// The "Total Records" a report shows. A report with detail rows switched off shows only groups and subtotals, so check
// its total (and confirm the grouping by query) rather than looking for record names on the page. Open the report
// with ?fv0=<value> to narrow its first filter to this round's records for that view only; the saved report is
// unchanged. A report is metadata in one org: each sandbox needs its own copy before the scenario can run there.
export async function reportTotal(page: Page, waitForText: string): Promise<number | undefined> {
  const frame = reportViewer(page);
  await expect(frame.getByText(waitForText).first()).toBeVisible({ timeout: 90_000 });
  const text = await frame.locator('body').innerText();
  const total = text.match(/Total Records\s*\n?\s*(\d+)/);
  return total ? Number(total[1]) : undefined;
}

// --- URL-first navigation. When getting to a page isn't what a step tests, open it by URL, so the step doesn't depend
// on the App Launcher, the list view switcher or scrolling. Each returns a path for signInAs or goTo, looked up each
// run so it works in any sandbox. A console app's URL reopens it on the last workspace tab it had open, and
// filterName takes a list view's Id or developer name. ---

// The address of a Lightning app, by its developer name or, failing that, its label. Pass it to signInAs so Login As
// lands straight in the app the scenario needs, then check the header with expectApp. If two apps share a label (a
// custom app labelled like a standard one), use the developer name; this stops and says so.
export function appPath(nameOrLabel: string): string {
  let apps = query(`SELECT DurableId FROM AppDefinition WHERE DeveloperName = '${nameOrLabel}'`);
  if (!apps.length) apps = query(`SELECT DurableId FROM AppDefinition WHERE Label = '${nameOrLabel}'`);
  if (apps.length !== 1) throw new Error(`Expected one app named or labelled ${nameOrLabel}, found ${apps.length}`);
  return `/lightning/app/${apps[0].DurableId}`;
}

export async function expectApp(page: Page, appLabel: string) {
  await expect(page.getByRole('heading', { name: appLabel, level: 1 })).toBeVisible({ timeout: 30_000 });
}

export function listViewPath(object: string, developerName: string): string {
  const rows = query(`SELECT Id FROM ListView WHERE SobjectType = '${object}' AND DeveloperName = '${developerName}'`);
  if (rows.length !== 1) throw new Error(`Expected one ${object} list view named ${developerName}, found ${rows.length}`);
  return `/lightning/o/${object}/list?filterName=${rows[0].Id}`;
}

export function reportPath(developerName: string): string {
  const rows = query(`SELECT Id FROM Report WHERE DeveloperName = '${developerName}'`);
  if (rows.length !== 1) throw new Error(`Expected one report named ${developerName}, found ${rows.length}`);
  return `/lightning/r/Report/${rows[0].Id}/view`;
}

export const recordPath = (object: string, id: string) => `/lightning/r/${object}/${id}/view`;

// Opens a path in the session the page already has (the test user's, after Login As). A list view is switched to
// table display on arrival (tableView).
export async function goTo(page: Page, urlPath: string) {
  await page.goto(new URL(urlPath, page.url()).toString());
  if (/\/lightning\/o\/[^/]+\/list/.test(urlPath)) await tableView(page);
}

// A list view in table display. A new user's console opens lists in split view, whose grid has a generic name
// ("Select an item from this list to open it."), so the list is switched to Table first.
export async function tableView(page: Page) {
  const display = page.getByRole('button', { name: /^Select list display/ }).filter({ visible: true }).first();
  // A new user's console can open the list in split view and draw nothing at all. Then split view is turned off and
  // the page reloaded, once.
  try {
    await display.waitFor({ timeout: 20_000 });
  } catch {
    const splitMode = page.getByRole('button', { name: 'Split view mode', exact: true }).filter({ visible: true }).first();
    if ((await splitMode.getAttribute('aria-expanded').catch(() => null)) === 'true') await splitMode.click();
    await page.reload();
    await display.waitFor({ timeout: 30_000 });
  }
  const split = page.getByRole('grid', { name: 'Select an item from this list to open it.' }).filter({ visible: true });
  // Decide only once a list has drawn, or a split view still loading reads as table display.
  await page.getByRole('grid').filter({ visible: true }).first().waitFor({ timeout: 30_000 });
  if (await split.first().isVisible().catch(() => false)) {
    await display.click();
    // The menu draws its choices as radio items in one place and checkbox items in another.
    await page.getByRole('menuitemradio', { name: 'Table', exact: true })
      .or(page.getByRole('menuitemcheckbox', { name: 'Table', exact: true })).filter({ visible: true }).first().click();
    await expect(split).toHaveCount(0, { timeout: 15_000 });
  }
}

// A list view's grid is named after the list view ("All Open Cases"). listSearch narrows it with the list's own
// search box to the rows matching text, such as the round's record prefix ("QA PROJ-21 R2"), so no step depends on
// scrolling or on records other runs left behind, and waits for the count to settle.
export function listGrid(page: Page, listViewLabel: string): Locator {
  return page.getByRole('grid', { name: listViewLabel, exact: true }).filter({ visible: true }).first();
}

export async function listSearch(page: Page, listViewLabel: string, text: string): Promise<Locator> {
  await tableView(page);
  const box = page.getByRole('searchbox', { name: 'Search this list...' }).filter({ visible: true }).first();
  await box.fill(text);
  await box.press('Enter');
  const grid = listGrid(page, listViewLabel);
  const others = grid.getByRole('row').filter({ has: page.getByRole('rowheader') }).filter({ hasNotText: text });
  await expect(others).toHaveCount(0, { timeout: 30_000 });
  return grid;
}

// A list view row by text in it (a Subject or Name). The row checkboxes are labelled by position ("Select Item 2"),
// so select a row with listRow(...).getByRole('checkbox'), never by the checkbox's label.
export function listRow(grid: Locator, text: string): Locator {
  return grid.getByRole('row').filter({ hasText: text });
}

// --- Email sending in a sandbox. ---
// A sandbox's Access to Send Email is usually "System email only", so a send from a record is refused. A step that
// sends an email wraps the send in withEmailOpen: it turns access to All email right before the send and back straight
// after, in rehearsals and recorded rounds alike, never in the video, and times how long it was on. The switch runs on
// Setup's Deliverability page in a browser context of its own; the saved value is read back after a reload. Every
// window is timed into emailWindows, for the run summary and Testing Feedback (emailWindowSummary, emailTotals).
// A spec calls closeEmailIfOpen in afterAll, so a step that fails mid-send still leaves email off.
export type EmailLevel = 'All email' | 'System email only';
export type EmailWindow = { why: string; opened: string; closed: string; seconds: number };
export const emailWindows: EmailWindow[] = [];
let emailOpenedAt: Date | null = null;
let emailOpenWhy = '';

export async function setEmailAccess(browser: Browser, level: EmailLevel) {
  const { context, page } = await signInAsAdmin(browser, '/lightning/setup/OrgEmailSettings/home');
  const access = () => page.frameLocator('iframe').first().getByRole('cell', { name: /^Access level/ }).getByRole('combobox');
  try {
    await access().selectOption(level, { timeout: 60_000 });
    await page.frameLocator('iframe').first().getByRole('button', { name: 'Save', exact: true }).first().click();
    await page.waitForTimeout(3_000);
    await page.reload();
    await expect(access(), `Access to Send Email saved as ${level}`).toHaveValue(/./, { timeout: 60_000 });
    const saved = await access().evaluate((el: HTMLSelectElement) => el.options[el.selectedIndex].text);
    expect(saved, 'Access to Send Email').toBe(level);
  } finally {
    await context.close();
  }
}

// Email on, the send, email off. `why` names the step ("S4 reply to the customer").
export async function withEmailOpen<T>(browser: Browser, why: string, send: () => Promise<T>): Promise<T> {
  await setEmailAccess(browser, 'All email');
  emailOpenedAt = new Date();
  emailOpenWhy = why;
  try {
    return await send();
  } finally {
    await closeEmailIfOpen(browser);
  }
}

export async function closeEmailIfOpen(browser: Browser) {
  if (!emailOpenedAt) return;
  await setEmailAccess(browser, 'System email only');
  const closed = new Date();
  emailWindows.push({
    why: emailOpenWhy, opened: emailOpenedAt.toISOString(), closed: closed.toISOString(),
    seconds: Math.round((closed.getTime() - emailOpenedAt.getTime()) / 1000),
  });
  emailOpenedAt = null;
}

// One line for the run summary: the total, then each window.
export function emailWindowSummary(): string {
  if (!emailWindows.length) return '- **Email sending:** not switched on in this run';
  const total = emailWindows.reduce((s, w) => s + w.seconds, 0);
  const each = emailWindows.map((w) => `${w.why} ${w.seconds}s (${w.opened} to ${w.closed})`).join('; ');
  return `- **Email sending:** on for ${total} seconds in all, across ${emailWindows.length} send${emailWindows.length === 1 ? '' : 's'}: ${each}. Back to System email only after each`;
}

// This attempt's email time for finishRun's extra.email, so the run summary keeps it per attempt.
export function emailTotals(): { seconds: number; sends: number } | undefined {
  if (!emailWindows.length) return undefined;
  return { seconds: emailWindows.reduce((s, w) => s + w.seconds, 0), sends: emailWindows.length };
}
