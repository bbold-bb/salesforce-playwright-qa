import { defineConfig } from '@playwright/test';

// One worker, scenarios in order: later scenarios use records the earlier ones create.
// No retries: a retry would hide a flaky step and replace its evidence. Rerun it as another attempt (QA_REASON=flaky).
// Video and screenshots are written by the tests themselves into evidence/ (see lib/evidence.ts),
// so Playwright's own video and screenshot options stay off.
// A trace is kept only when a test fails (QA_TRACE=on keeps one for every run), in test-results/, which is
// gitignored and never published: it holds the page, the console and the network, session included. Its filmstrip
// (screenshots) stays off because it would start a screencast of its own and take over the evidence video.
// Read one with `npx playwright trace open "test-results/<run>/<test>/trace.zip"` (see README.md).
// channel 'chrome' uses the installed Google Chrome, so no Playwright browser is downloaded.
// deviceScaleFactor 2 gives screenshots 3200 px wide, sharp enough to read a picklist value.
//
// Each run writes to its own folder under test-results/, named by ticket, round and start time, and nothing clears
// it: Playwright empties its output folder when a run starts, so one shared folder would lose every earlier trace and
// let two sessions' runs clear each other's. The start time is fixed once in the main process and passed to the
// worker through the environment, since the worker loads this file again. Tickets are found in the command line's
// arguments by their Jira key shape (PROJ-21).
if (!process.env.QA_RUN_STAMP) {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  process.env.QA_RUN_STAMP = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`;
}
const runTickets = [...new Set(process.argv.slice(2).flatMap((a) => a.match(/\b[A-Z][A-Z0-9]+-\d+\b/g) ?? []))];
const runFolder = [runTickets.join(' ') || 'run', process.env.QA_ROUND, process.env.QA_RUN_STAMP].filter(Boolean).join(' ');

export default defineConfig({
  testDir: './tests',
  // Before any spec starts: checks this machine's test users, then takes the run lock or waits for it.
  globalSetup: ['./lib/testUsers.ts', './lib/runLock.ts'],
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 20 * 60 * 1000,
  expect: { timeout: 30 * 1000 },
  reporter: [['list']],
  outputDir: `./test-results/${runFolder}`,
  use: {
    channel: 'chrome',
    headless: process.env.QA_HEADED !== '1',
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 2,
    actionTimeout: 30 * 1000,
    navigationTimeout: 90 * 1000,
    video: 'off',
    trace: {
      mode: process.env.QA_TRACE === 'on' ? 'on' : 'retain-on-failure',
      snapshots: { dom: true, aria: true, screen: false },
      screenshots: false,
      sources: true,
    },
    screenshot: 'off',
  },
});
