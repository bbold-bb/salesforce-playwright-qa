// Signs in to a new scratch org once as its admin and waits for Lightning, so the first eval run doesn't spend minutes
// on a new org's first load. Needs NODE_PATH set to the harness's node_modules (org-up.sh does). Usage: node warm.cjs <alias>
const { chromium } = require('@playwright/test');
const { execFileSync } = require('child_process');
(async () => {
  const out = execFileSync('sf', ['org', 'open', '--url-only', '--path', '/lightning/setup/SetupOneHome/home', '-o', process.argv[2], '--json'],
    { encoding: 'utf8', env: { ...process.env, FORCE_COLOR: '0' } });
  const url = JSON.parse(out.replace(/\x1b\[[0-9;]*m/g, '')).result.url;
  const browser = await chromium.launch({ channel: 'chrome' });
  const page = await browser.newPage();
  await page.goto(url);
  await page.waitForURL((u) => u.pathname.startsWith('/lightning'), { timeout: 300_000 });
  await page.waitForTimeout(10_000);
  await browser.close();
})().catch((e) => { console.error('warm-up failed:', e.message.split('\n')[0]); process.exit(1); });
