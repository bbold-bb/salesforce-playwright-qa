import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { Page, test } from '@playwright/test';
import { ORG_ALIAS, ORG_PREFIX_TO_DROP, EVIDENCE_DIR, TIME_ZONE, LEDGER_ENABLED } from './config';
import { openPages, setupChangesSince, setRunTicket } from './salesforce';

// evidence/<epic>/<QA sub-task>/<date> <org> <round>/{screenshots,videos,queries,attempts,run-summary.md}
// evidence/rehearsal/<QA sub-task>/ holds practice runs, and evidence/qa-ledger/ the optional ledger. A reviewed round
// is published with ../../publish.sh; the folder itself stays out of version control.
export const EVIDENCE = EVIDENCE_DIR;
const LEDGER = path.join(EVIDENCE, 'qa-ledger');
// A rehearsal is a practice run of a script before its recorded run: no video, round R0, its own folder under
// evidence/rehearsal/, and left out of the ledger report's figures. It finds out how the screens behave without
// using up attempts in a real round. Its records are named with R0, so they never collide with a real round's.
const REHEARSAL = 'rehearsal';
const REHEARSAL_ROUND = 'R0';
export const REHEARSING = process.env.QA_REASON === REHEARSAL;
export const VIDEO = process.env.QA_VIDEO !== '0' && !REHEARSING;
const ORG_SHORT = ORG_PREFIX_TO_DROP && ORG_ALIAS.startsWith(ORG_PREFIX_TO_DROP) ? ORG_ALIAS.slice(ORG_PREFIX_TO_DROP.length) : ORG_ALIAS;
// How many rehearsals in a row a step may fail before the run says to stop and take the step to the approver.
const STOP_AFTER = 3;

// Why a run happened (the same lists as the ledger add-on's qa_ledger.py). A new round means something under test
// changed; another attempt in the same round means it didn't. steps-changed is an attempt because the build is the
// same: the approved Test Steps changed, so the script followed them.
const ROUND_REASONS = ['first-run', 'retest-after-fix', 'story-changed', 'regression-after-deployment'];
const ATTEMPT_REASONS = ['script-fix', 'steps-changed', 'flaky', 'tooling-check'];

// What a scenario needs to show it passed: a screenshot for a state (a value list, a message, a layout), a video
// where what happens matters (a rule firing, a record created end to end), or query output where nothing runs as
// a user. Before sharing a round, check each scenario has what it declares (the run summary lists both).
export type Evidence = 'screenshot' | 'video' | 'query';

// A flow is one user's session through several steps, recorded as one video with a title card per step (flow
// "F1" records <ticket>-F1.webm). A step in a flow names it in `flow`; its video is the flow's. Each step still gets
// its own result, plus a screenshot if it's tagged for one, and a step that fails stops the rest of its flow, which
// then show as not run.
export type Scenario = { id: string; title: string; expected: string; evidence: Evidence[]; flow?: string };

export type ScenarioResult = Scenario & {
  seen: string[];
  passed?: boolean;
  seconds?: number;
  links: { label: string; url: string }[];
  screenshots: string[];
  attempt?: number;
  history?: { attempt: number; passed?: boolean; seconds?: number }[];
};

type Attempt = {
  attempt: number;
  reason: string;
  note: string;
  startedLocal: string;
  seconds?: number;
  scenarios: string[];
  method: string;
  changes?: string[];
  closedTabs?: string[];
  evidenceKept?: boolean;
  // Email sending switched on for this attempt's sends (lib/salesforce.ts, withEmailOpen): total seconds and sends.
  email?: { seconds: number; sends: number };
};

type Store = { header: string[]; attempts: Attempt[]; results: ScenarioResult[]; dropped?: ScenarioResult[] };

export type Run = {
  ticket: string;
  title: string;
  specFile: string;
  round: string;
  dir: string;
  ticketDir: string;
  attempt: number;
  reason: string;
  note: string;
  started: Date;
  runId: string;
  store: Store;
};

// Local time in the project's time zone (config.ts): ISO-like for the ledger, readable for the run summary.
const localIso = (d: Date) => d.toLocaleString('sv-SE', { timeZone: TIME_ZONE }).replace(' ', 'T');
const localText = (d: Date) => d.toLocaleString('en-US', { timeZone: TIME_ZONE, timeZoneName: 'short' });

// One recorded run at a time. Recorded runs from two sessions at once share the test users, so each could see the
// other's records, tabs and changes in its videos. A recorded (non-rehearsal) run takes this lock in openRun and gives
// it up when its process ends; another recorded run started meanwhile stops with who holds it. A lock left by a run
// that died is taken over, since its process is gone. Rehearsals don't take it.
const LOCK = path.join(EVIDENCE, '.recording.lock');
function takeRecordingLock(ticket: string, round: string) {
  if (fs.existsSync(LOCK)) {
    const held = JSON.parse(fs.readFileSync(LOCK, 'utf8'));
    let alive = false;
    // kill(pid, 0) only asks whether the process exists; EPERM means it does, under another user.
    try { process.kill(held.pid, 0); alive = held.pid !== process.pid; } catch (e: any) { alive = e?.code === 'EPERM'; }
    if (alive) {
      throw new Error(`Another recorded run is in progress (${held.ticket} ${held.round}, started ${held.started}). ` +
        'Record one ticket at a time: wait for it to finish, then run this again.');
    }
  }
  fs.mkdirSync(EVIDENCE, { recursive: true });
  fs.writeFileSync(LOCK, JSON.stringify({ ticket, round, pid: process.pid, started: localText(new Date()) }));
  process.on('exit', () => {
    try {
      if (JSON.parse(fs.readFileSync(LOCK, 'utf8')).pid === process.pid) fs.unlinkSync(LOCK);
    } catch { /* already gone */ }
  });
}

// Opens this run's round folder. A first-run, retest-after-fix, story-changed or regression-after-deployment
// run starts a new round folder; a script-fix, steps-changed, flaky or tooling-check run is another attempt in the
// round's existing folder. A rehearsal (QA_ROUND=R0 QA_REASON=rehearsal) goes to evidence/rehearsal/ instead.
// The wrong kind of reason for the round (a new-round reason on a round that already ran, or an attempt reason on one
// that hasn't) stops the run before it starts, so a retest can't quietly overwrite an earlier round.
// Pass specFile: __filename, so the run manifest can record the script's commit.
export function openRun(opts: { ticket: string; epicFolder: string; ticketFolder: string; round: string; specFile: string }): Run {
  const { ticket, round } = opts;
  if (!/^R\d+$/.test(round)) throw new Error('Set QA_ROUND to this round, for example QA_ROUND=R3');
  const reason = process.env.QA_REASON ?? '';
  if (![...ROUND_REASONS, ...ATTEMPT_REASONS, REHEARSAL].includes(reason)) {
    throw new Error(`Set QA_REASON to one of: ${[...ROUND_REASONS, ...ATTEMPT_REASONS, REHEARSAL].join(', ')}`);
  }
  if ((reason === REHEARSAL) !== (round === REHEARSAL_ROUND)) {
    throw new Error(
      `${REHEARSAL_ROUND} is the rehearsal round. A rehearsal runs as QA_ROUND=${REHEARSAL_ROUND} QA_REASON=${REHEARSAL}; ` +
        'a real run uses R1 or later and another reason.',
    );
  }
  if (reason !== REHEARSAL) takeRecordingLock(ticket, round);
  setRunTicket(ticket);
  const ticketDir = path.join(EVIDENCE, opts.epicFolder, opts.ticketFolder);
  fs.mkdirSync(ticketDir, { recursive: true });
  const existing = fs.readdirSync(ticketDir).find((d) => d.endsWith(` ${ORG_SHORT} ${round}`));
  const started = new Date();
  let dir: string;
  let store: Store;
  if (reason === REHEARSAL) {
    // Outside the ticket's folder, so it is never taken for a round, compared with as the last run, or published.
    // Rehearsals of one script share the folder, and each is the next attempt, so a script's "first attempt creates
    // the records" logic works as it does in a real round.
    dir = path.join(EVIDENCE, 'rehearsal', opts.ticketFolder, `${ORG_SHORT} ${REHEARSAL_ROUND}`);
    const saved = path.join(dir, 'results.json');
    store = fs.existsSync(saved) ? JSON.parse(fs.readFileSync(saved, 'utf8')) : { header: [], attempts: [], results: [] };
  } else if (existing) {
    if (ROUND_REASONS.includes(reason)) {
      throw new Error(
        `${round} already ran in ${ORG_SHORT} (${existing}). A ${reason} run is a new round: use the next QA_ROUND. ` +
          `To try again in ${round}, use QA_REASON=${ATTEMPT_REASONS.join(', ')}.`,
      );
    }
    dir = path.join(ticketDir, existing);
    store = JSON.parse(fs.readFileSync(path.join(dir, 'results.json'), 'utf8'));
  } else {
    if (ATTEMPT_REASONS.includes(reason)) {
      throw new Error(`Nothing to try again: ${round} hasn't run in ${ORG_SHORT}. Use a new-round reason: ${ROUND_REASONS.join(', ')}`);
    }
    const date = started.toLocaleDateString('en-CA', { timeZone: TIME_ZONE });
    dir = path.join(ticketDir, `${date} ${ORG_SHORT} ${round}`);
    store = { header: [], attempts: [], results: [] };
  }
  fs.mkdirSync(path.join(dir, 'screenshots'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'videos'), { recursive: true });
  const attempt = store.attempts.length + 1;
  current = {
    ticket, title: opts.ticketFolder, specFile: path.relative(path.join(__dirname, '..'), opts.specFile), round, dir, ticketDir,
    attempt, reason, note: process.env.QA_NOTE ?? '', started, runId: `${ticket}-${round}-A${attempt}`, store,
  };
  return current;
}

// The run in progress, for what a rehearsal saves as it goes: the storyboard and the failure snapshots.
let current: Run | undefined;

// A rehearsal's storyboard: every card and screenshot in the order a viewer would meet them, so the wording and the
// framing are approved before anything is recorded. finishRun writes it to storyboard.md in the rehearsal folder.
const storyboard: string[] = [];
const board = (line: string) => { if (REHEARSING) storyboard.push(line); };

// What each open page showed when a rehearsal step failed: its address, its accessibility tree (the role and name of
// everything on it, frames included, which is what role and label locators match) and a screenshot, saved to
// failures/ in the rehearsal folder. The fix is read from there rather than from a trace or another run. It never
// hides the step's own error. Rehearsals only: a recorded round's folder is published.
async function failureSnapshot(r: ScenarioResult, error: string) {
  if (!REHEARSING || !current) return;
  const dir = path.join(current.dir, 'failures');
  const pages = openPages();
  for (let i = 0; i < pages.length; i++) {
    const page = pages[i];
    const name = `A${current.attempt}-${r.id}${pages.length > 1 ? `-page${i + 1}` : ''}`;
    try {
      fs.mkdirSync(dir, { recursive: true });
      const parts = [`# ${r.id} ${r.title}`, `# Failed: ${error}`, `# Page: ${new URL(page.url()).pathname}`, ''];
      for (const frame of page.frames()) {
        const tree = await frame.locator('body').ariaSnapshot({ timeout: 5_000 }).catch(() => '');
        if (!tree) continue;
        if (frame !== page.mainFrame()) parts.push('', `# Frame: ${frame.name() || new URL(frame.url()).pathname}`);
        parts.push(tree);
      }
      fs.writeFileSync(path.join(dir, `${name}.aria.yml`), parts.join('\n') + '\n');
      await page.screenshot({ path: path.join(dir, `${name}.png`), timeout: 10_000 }).catch(() => undefined);
      r.seen.push(`What the page showed: failures/${name}.aria.yml and .png`);
    } catch {
      // A page that can't be read leaves no snapshot; the step's own error still stands.
    }
  }
}

// Before a scenario (or a flow) saves new evidence in a later attempt, its earlier files move to attempts/A<n>/, so
// nothing is overwritten. Without this, a rerun of one flaky step replaces the evidence of the run that failed.
export function keepEarlierEvidence(run: Run, scenarioId: string) {
  if (run.attempt === 1) return;
  const from = run.store.results.find((r) => r.id === scenarioId || r.flow === scenarioId)?.attempt ?? run.attempt - 1;
  const pattern = new RegExp(`^${run.ticket}-${scenarioId}[a-z]?\\.(png|webm|json)$`);
  for (const kind of ['screenshots', 'videos', 'queries']) {
    const src = path.join(run.dir, kind);
    if (!fs.existsSync(src)) continue;
    for (const f of fs.readdirSync(src).filter((x) => pattern.test(x))) {
      const dest = path.join(run.dir, 'attempts', `A${from}`, kind);
      fs.mkdirSync(dest, { recursive: true });
      fs.renameSync(path.join(src, f), path.join(dest, f));
    }
  }
}

// Starts a flow's steps: one result per step, each "not run" until it finishes. Earlier evidence for the flow and its
// steps moves aside first. Run each step with `step`; finishRun records them all.
export function startFlow(run: Run, scenarios: Scenario[], flow: string, results: ScenarioResult[]): Record<string, ScenarioResult> {
  keepEarlierEvidence(run, flow);
  const out: Record<string, ScenarioResult> = {};
  for (const s of scenarios.filter((x) => x.flow === flow)) {
    keepEarlierEvidence(run, s.id);
    const r: ScenarioResult = { ...s, seen: [], links: [], screenshots: [] };
    results.push(r);
    out[s.id] = r;
  }
  return out;
}

// Runs one step of a flow and records its result and time. A failure is recorded and stops the flow.
// It runs as a boxed Playwright step, so a trace or report lists the flow's steps by scenario ID and a failure
// points at the step in the spec rather than inside a helper.
export async function step(r: ScenarioResult, body: () => Promise<void>) {
  const started = Date.now();
  board(`\n## ${r.id} ${r.title}\n\nExpected: ${r.expected}\n`);
  try {
    await test.step(`${r.id} ${r.title}`, body, { box: true, subtitle: `Expected: ${r.expected}` });
    r.passed = true;
  } catch (e) {
    r.passed = false;
    // A failed sign-in can carry the one-time frontdoor or singleaccess URL in its message; it never reaches evidence.
    const message = String((e as Error).message).replace(/\x1b\[[0-9;]*m/g, '')
      .replace(/https:\/\/[^\s)]*(frontdoor|singleaccess)[^\s)]*/g, '<one-time sign-in URL removed>');
    const error = message.split('\n')[0];
    r.seen.push(`Failed: ${error}`);
    board(`- **Failed here:** ${error}`);
    // The snapshot's heading keeps the locator and what was expected, which sit on the message's next lines.
    await failureSnapshot(r, message.split('\n').filter((l) => l.trim()).slice(0, 8).join('\n# '));
    throw e;
  } finally {
    r.seconds = Math.round((Date.now() - started) / 1000);
  }
}

// Pauses only matter for the video, so a run without video (QA_VIDEO=0, or a rehearsal) goes at full speed, about
// five times faster. The video is slowed this way to a pace a person can follow.
export async function beat(page: Page, ms = 1200) {
  if (VIDEO) await page.waitForTimeout(ms);
}

// One video per standalone scenario or per flow. Playwright's screencast writes WebM with VP9, which Chrome plays;
// check your shared storage's preview plays it before you rely on it. The overlay puts a pointer and an outline on
// each element as it's used.
export async function startVideo(page: Page, dir: string, name: string) {
  if (!VIDEO) return;
  await page.screencast.start({ path: path.join(dir, 'videos', `${name}.webm`), size: { width: 1600, height: 1000 } });
  await page.screencast.showActions({
    duration: 1200,
    position: 'top-right',
    style: {
      highlight: 'outline: 3px solid #e8590c; background: rgba(232, 89, 12, .08)',
      title: 'font-size: 18px',
    },
  });
}

export async function stopVideo(page: Page) {
  if (!VIDEO) return;
  await page.screencast.stop();
}

// How long a card stays up: about 4 words a second, at least 6 seconds.
function readingMs(text: string, minMs = 6000): number {
  return Math.max(minMs, Math.ceil(text.split(/\s+/).length / 4) * 1000);
}

// Title card at the start of a scenario, or a chapter card for each step of a flow: what it does, then what should
// happen. It stays up long enough to read; showChapter returns once the card is gone, so no extra wait.
export async function chapter(page: Page, title: string, expected: string, intro = '') {
  const description = `${intro ? `${intro} ` : ''}Expected: ${expected}`;
  board(`- **Card:** ${title}. ${description}`);
  if (!VIDEO) return;
  const duration = readingMs(`${title} ${description}`);
  await page.screencast.showChapter(title, { description, duration });
}

// The card that opens every flow video, so a reader who opens one video on its own knows what it is about: the
// ticket and its title, what the video shows, the steps of the ticket's Test Steps it covers, who it runs as, and the
// org and round. It says only what this video covers: no count of videos and no pointer to other videos or evidence.
// `video` numbers it in the rehearsal storyboard only.
export async function openingCard(page: Page, run: Run, o: { name: string; steps: string; runAs: string; video?: number }) {
  const title = run.title;
  const description = `${o.name}. Step${/\D/.test(o.steps) ? 's' : ''} ${o.steps}, as ${o.runAs}, in ${ORG_SHORT}, round ${run.round}.`;
  board(`\n# ${o.video ? `Video ${o.video}` : o.name}\n\n- **Opening card:** ${title}. ${description}`);
  if (!VIDEO) return;
  await page.screencast.showChapter(title, { description, duration: readingMs(`${title} ${description}`, 8000) });
}

// A short card inside a scenario, for example as it moves to the next record.
export async function caption(page: Page, text: string, ms = 2500) {
  board(`- **Caption:** ${text}`);
  if (!VIDEO) return;
  await page.screencast.showChapter(text, { duration: ms });
}

// One screenshot, without any video overlay on it. The result stays on screen for a few seconds
// in the video. Full page when the page is at the top; when it has scrolled (an inline edit, an open
// picklist), the visible window, because Lightning's fixed header lands mid-image in a full-page capture.
// Pass windowOnly when a picklist is open, since a full-page capture resizes the page and can close it.
export async function shot(page: Page, dir: string, name: string, opts: { windowOnly?: boolean } = {}) {
  if (VIDEO) await page.screencast.hideOverlays();
  const atTop = (await page.evaluate(() => window.scrollY)) === 0;
  await page.screenshot({ path: path.join(dir, 'screenshots', `${name}.png`), fullPage: atTop && !opts.windowOnly });
  board(`- **Screenshot:** [${name}.png](screenshots/${name}.png)`);
  if (VIDEO) await page.screencast.showOverlays();
  await beat(page, 3000);
}

// Query output as evidence, for a scenario where nothing runs as a user: what was asked and the rows that came back.
export function saveQuery(dir: string, name: string, query: string, rows: Record<string, unknown>[]) {
  fs.mkdirSync(path.join(dir, 'queries'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'queries', `${name}.json`), JSON.stringify({ query, rows }, null, 2));
}

// --- The run manifest: what was under test, and what changed since the last run -------------------------

function git(args: string[]): string {
  try {
    return execFileSync('git', args, { cwd: path.join(__dirname, '..'), encoding: 'utf8' }).replace(/\n+$/, '');
  } catch {
    return '';
  }
}

function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); rows.push(row); row = []; cell = '';
    } else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows;
  return body.filter((r) => r.length > 1 || r[0]).map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ''])));
}

// The ledger's Jira snapshot: qa-ledger/jira-items.csv with columns key, updated, sprint, snapshot_local, refreshed by
// a read-only Jira search before a run. Read only when the ledger add-on is on (LEDGER_ENABLED in config.ts); without
// it the manifest records the Jira items as null.
function jiraItem(key: string): Record<string, string> | undefined {
  if (!LEDGER_ENABLED) return undefined;
  const file = path.join(LEDGER, 'jira-items.csv');
  if (!fs.existsSync(file)) return undefined;
  return parseCsv(fs.readFileSync(file, 'utf8')).find((r) => r.key === key);
}

type Manifest = {
  runId: string;
  startedUtc: string;
  org: string;
  reason: string;
  note: string;
  script: { commit: string; uncommittedEdits: string[] };
  jira: Record<string, { updated: string; sprint: string; snapshot: string } | null>;
  metadata: Record<string, unknown>;
  setupChangesSinceLastRun: { when: string; by: string; section: string; what: string }[];
  comparedWith: string;
  changes: string[];
};

function previousManifest(run: Run): Manifest | undefined {
  const found: Manifest[] = [];
  for (const d of fs.readdirSync(run.ticketDir)) {
    const folder = path.join(run.ticketDir, d);
    if (!fs.statSync(folder).isDirectory()) continue;
    for (const f of fs.readdirSync(folder).filter((x) => /^run-manifest-A\d+\.json$/.test(x))) {
      const m: Manifest = JSON.parse(fs.readFileSync(path.join(folder, f), 'utf8'));
      if (m.org === ORG_ALIAS) found.push(m);
    }
  }
  return found.sort((a, b) => a.startedUtc.localeCompare(b.startedUtc)).pop();
}

// A key that one run has and the other doesn't (a component added or deleted) has no value, and stringifies to nothing.
const short = (v: unknown) => {
  const s = v === undefined ? 'not collected' : JSON.stringify(v);
  return s.length > 160 ? `${s.slice(0, 157)}...` : s;
};

// Records the script version, the Jira items' last update (from the ledger's Jira snapshot, if you keep one), the
// build's metadata (whatever the spec collects) and Setup changes since the last run of this QA sub-task in this org,
// then lists what differs. That list is how a failed retest tells a build change from a script change.
export function writeManifest(run: Run, parent: string, metadata: Record<string, unknown>): string[] {
  const prev = previousManifest(run);
  const specFiles = [run.specFile, 'lib'];
  const status = git(['status', '--porcelain', '--', ...specFiles]);
  const jira: Manifest['jira'] = {};
  for (const key of [run.ticket, parent]) {
    const it = jiraItem(key);
    jira[key] = it ? { updated: it.updated, sprint: it.sprint, snapshot: it.snapshot_local } : null;
  }
  const m: Manifest = {
    runId: run.runId,
    startedUtc: run.started.toISOString(),
    org: ORG_ALIAS,
    reason: run.reason,
    note: run.note,
    script: {
      commit: git(['log', '-1', '--format=%h %cs', '--', ...specFiles]),
      uncommittedEdits: status ? status.split('\n').map((l) => l.slice(3)) : [],
    },
    jira,
    metadata,
    setupChangesSinceLastRun: prev ? setupChangesSince(prev.startedUtc) : [],
    comparedWith: prev?.runId ?? '',
    changes: [],
  };

  const changes: string[] = [];
  if (!prev) {
    changes.push(`First recorded run of ${run.ticket} in ${ORG_SHORT}; nothing to compare with.`);
  } else {
    changes.push(`Compared with ${prev.runId}.`);
    if (prev.script.commit !== m.script.commit) changes.push(`Script changed: ${prev.script.commit || 'none'} to ${m.script.commit}.`);
    if (m.script.uncommittedEdits.length) changes.push(`Script has uncommitted edits: ${m.script.uncommittedEdits.join(', ')}.`);
    for (const [key, now] of Object.entries(m.jira)) {
      const before = prev.jira[key];
      if (now && before && now.updated !== before.updated) changes.push(`Jira ${key} updated since the last run (${now.updated}).`);
      if (now && before && now.sprint !== before.sprint) changes.push(`Jira ${key} moved sprint: ${before.sprint || 'none'} to ${now.sprint || 'none'}.`);
    }
    for (const key of new Set([...Object.keys(prev.metadata), ...Object.keys(m.metadata)])) {
      const a = JSON.stringify(prev.metadata[key]);
      const b = JSON.stringify(m.metadata[key]);
      if (a !== b) changes.push(`Metadata changed, ${key}: ${short(prev.metadata[key])} to ${short(m.metadata[key])}.`);
    }
    const setup = m.setupChangesSinceLastRun;
    if (setup.length) {
      changes.push(`${setup.length} Setup change${setup.length === 1 ? '' : 's'} in the org since the last run (Setup Audit Trail, user management left out):`);
      for (const s of setup.slice(-15)) changes.push(`  ${s.when.slice(0, 16)} ${s.section}: ${s.what} (${s.by})`);
    }
    if (changes.length === 1) changes.push('Nothing recorded changed: same script, same Jira update times, same metadata, no Setup changes.');
  }
  m.changes = changes;
  fs.writeFileSync(path.join(run.dir, `run-manifest-A${run.attempt}.json`), JSON.stringify(m, null, 2));
  return changes;
}

// --- The run summary and the ledger --------------------------------------------------------------------

const csvCell = (v: unknown) => {
  const s = v === undefined || v === null ? '' : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function appendCsv(name: string, columns: string[], rows: Record<string, unknown>[]) {
  fs.mkdirSync(LEDGER, { recursive: true });
  const file = path.join(LEDGER, name);
  if (!fs.existsSync(file)) fs.writeFileSync(file, columns.join(',') + '\n');
  fs.appendFileSync(file, rows.map((r) => columns.map((c) => csvCell(r[c])).join(',') + '\n').join(''));
}

// The catalog holds each QA sub-task's current scenarios, so planned scenarios can be counted before they run.
// Written only when the ledger add-on is on.
export function recordCatalog(ticket: string, scenarios: Scenario[], source: string) {
  if (!LEDGER_ENABLED) return;
  const columns = ['qa_subtask', 'scenario', 'title', 'expected', 'evidence', 'source'];
  const file = path.join(LEDGER, 'scenarios.csv');
  const others = fs.existsSync(file) ? parseCsv(fs.readFileSync(file, 'utf8')).filter((r) => r.qa_subtask !== ticket) : [];
  const mine = scenarios.map((s) => ({ qa_subtask: ticket, scenario: s.id, title: s.title, expected: s.expected, evidence: s.evidence.join(' + '), source }));
  fs.mkdirSync(LEDGER, { recursive: true });
  fs.writeFileSync(file, [columns.join(','), ...[...others, ...mine].map((r: any) => columns.map((c) => csvCell(r[c])).join(','))].join('\n') + '\n');
}

// The ledger is private to your team (run times feed effort and cost figures), so it stays on this machine and isn't copied with
// the evidence. Rows are written only when the ledger add-on is on.
const RUN_COLUMNS = [
  'run_id', 'started_local', 'qa_subtask', 'scenario', 'round', 'attempt', 'reason', 'note', 'method', 'org',
  'sprint', 'result', 'seconds', 'run_folder',
];

// Saves this attempt: results.json (every attempt, every scenario's history), run-summary.md, a rehearsal's
// storyboard, and, with the ledger on, one ledger row per scenario run. extra.dropped names steps taken off the Test
// Steps since an earlier attempt; extra.email is emailTotals() from lib/salesforce.ts when a step sent email.
export function finishRun(
  run: Run, header: string[], fresh: ScenarioResult[],
  extra: { changes: string[]; closedTabs: string[]; dropped?: string[]; email?: { seconds: number; sends: number } },
) {
  const seconds = Math.round((Date.now() - run.started.getTime()) / 1000);
  const store = run.store;
  if (!store.header.length) store.header = header;
  store.attempts.push({
    attempt: run.attempt, reason: run.reason, note: run.note, startedLocal: localText(run.started), seconds,
    scenarios: fresh.map((r) => r.id), method: 'playwright', changes: extra.changes, closedTabs: extra.closedTabs,
    evidenceKept: true, ...(extra.email ? { email: extra.email } : {}),
  });
  for (const r of fresh) {
    let before = store.results.find((e) => e.id === r.id);
    // A step renumbered onto an ID an earlier attempt used for another step starts its own history; the old step's
    // result moves to dropped, so one ID never carries two steps' attempts.
    if (before && before.title !== r.title) {
      store.dropped = [...(store.dropped ?? []).filter((e) => e.id !== r.id || e.title !== before!.title), before];
      store.results = store.results.filter((e) => e !== before);
      before = undefined;
    }
    r.attempt = run.attempt;
    r.history = [...(before?.history ?? []), { attempt: run.attempt, passed: r.passed, seconds: r.seconds }];
  }
  store.results = [...store.results.filter((e) => !fresh.some((f) => f.id === e.id)), ...fresh].sort((a, b) => a.id.localeCompare(b.id));
  // A step taken off the Test Steps since an earlier attempt leaves the round's results, so the evidence index and the
  // published summary carry only the steps on the ticket. Its history stays in results.json under dropped.
  for (const id of extra.dropped ?? []) {
    const gone = store.results.filter((e) => e.id === id);
    if (!gone.length) continue;
    store.dropped = [...(store.dropped ?? []).filter((e) => e.id !== id), ...gone];
    store.results = store.results.filter((e) => e.id !== id);
  }
  fs.writeFileSync(path.join(run.dir, 'results.json'), JSON.stringify(store, null, 2));
  writeSummary(run.dir, run.title, run.round, store);
  if (REHEARSING) {
    fs.writeFileSync(path.join(run.dir, 'storyboard.md'), [
      `# ${run.title}: storyboard, rehearsal A${run.attempt}`, '',
      'Every card and screenshot in the order a viewer meets them. In a recorded round the opening card reads the real round, not R0.',
      ...storyboard, '',
    ].join('\n'));
    // The stop rule: a step that keeps failing isn't fixed by another try. It goes to the approver with options.
    for (const r of fresh) {
      const h = r.history ?? [];
      let fails = 0;
      for (let i = h.length - 1; i >= 0 && h[i].passed === false; i--) fails++;
      if (fails >= STOP_AFTER) {
        console.log(`\nSTOP: ${r.id} "${r.title}" has failed ${fails} rehearsals in a row. Don't try again: take the step to ` +
          'the approver with what the page showed (failures/) and the options, such as another way to do it or proving it by query.');
      }
    }
  }

  if (!LEDGER_ENABLED) return;
  const sprint = jiraItem(run.ticket)?.sprint ?? '';
  appendCsv('scenario-runs.csv', RUN_COLUMNS, fresh.map((r) => ({
    run_id: run.runId, started_local: localIso(run.started), qa_subtask: run.ticket, scenario: r.id, round: run.round,
    attempt: run.attempt, reason: run.reason, note: run.note, method: 'playwright', org: ORG_ALIAS, sprint,
    result: r.passed === undefined ? 'not-run' : r.passed ? 'pass' : 'fail', seconds: r.seconds ?? '',
    run_folder: path.relative(EVIDENCE, run.dir),
  })));
}

export function writeSummary(dir: string, title: string, round: string, store: Store) {
  const lines = [`# ${title}, ${round}`, '', ...store.header];
  const emailed = store.attempts.filter((a) => a.email);
  if (emailed.length) {
    const secs = emailed.reduce((n, a) => n + a.email!.seconds, 0);
    const sends = emailed.reduce((n, a) => n + a.email!.sends, 0);
    lines.push(`- **Email sending:** on for ${secs} seconds in all across ${sends} send${sends === 1 ? '' : 's'} in this round, switched on right before each send and back to System email only straight after; each attempt's time is in its note`);
  }
  lines.push('');
  lines.push('## Attempts', '', '| Attempt | When | Reason | Scenarios | Took | Note |', '| --- | --- | --- | --- | --- | --- |');
  for (const a of store.attempts) {
    const note = a.note && !a.note.endsWith('.') ? `${a.note}.` : a.note;
    const mail = a.email ? `${note ? ' ' : ''}Email on ${a.email.seconds} s for ${a.email.sends} send${a.email.sends === 1 ? '' : 's'}.` : '';
    lines.push(`| A${a.attempt} | ${a.startedLocal} | ${a.reason} | ${a.scenarios.join(', ')} | ${a.seconds ?? '-'} s | ${note}${mail} |`);
  }
  lines.push('', '## Results', '', '| Scenario | Result | Attempts | Time | Evidence needed | Screenshots |', '| --- | --- | --- | --- | --- | --- |');
  for (const r of store.results) {
    const result = r.passed === undefined ? 'Not run' : r.passed ? 'Pass' : 'Fail';
    const tries = (r.history ?? []).map((h) => `A${h.attempt} ${h.passed === undefined ? 'not run' : h.passed ? 'pass' : 'fail'}`).join(', ');
    lines.push(`| ${r.id} ${r.title} | ${result} | ${tries} | ${r.seconds ?? '-'} s | ${(r.evidence ?? []).join(', ') || '-'}${r.flow ? ` (flow ${r.flow})` : ''} | ${r.screenshots.join(', ')} |`);
  }
  const latest = store.attempts[store.attempts.length - 1];
  if (latest?.changes?.length) {
    lines.push('', `## What changed before A${latest.attempt}`, '');
    for (const c of latest.changes) lines.push(c.startsWith('  ') ? `  - ${c.trim()}` : `- ${c}`);
    lines.push('', 'Earlier attempts list theirs in results.json, and each attempt\'s run-manifest file holds the full record.');
  }
  for (const r of store.results) {
    lines.push('', `## ${r.id} ${r.title}`, '', `Expected: ${r.expected}`, '');
    for (const s of r.seen) lines.push(`- ${s}`);
    if (r.links.length) {
      lines.push('', 'Records:');
      for (const l of r.links) lines.push(`- [${l.label}](${l.url})`);
    }
  }
  fs.writeFileSync(path.join(dir, 'run-summary.md'), lines.join('\n') + '\n');
}
