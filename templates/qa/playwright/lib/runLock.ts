import fs from 'fs';
import path from 'path';
import { EVIDENCE_DIR, TIME_ZONE } from './config';

// One run at a time on a machine, rehearsal or recorded. Runs from two sessions share this machine's test users, so two at once would see each other's records, tabs and changes. This is Playwright's global setup
// (playwright.config.ts): it runs in the main process before any spec, so a spec that never calls openRun is covered, and
// the lock is held by the main process until the whole command ends, across worker restarts. A run that finds the lock
// held names the run that holds it and waits its turn, up to QA_WAIT minutes (30), then stops. QA_WAIT=0 stops at once.
// A lock left by a run that died is taken over. One lock for every org.
const EVIDENCE = EVIDENCE_DIR;
const LOCK = path.join(EVIDENCE, '.recording.lock');
type Lock = { run: string; pid: number; started: string };

const localText = (d: Date) => d.toLocaleString('en-US', { timeZone: TIME_ZONE, timeZoneName: 'short' });
// kill(pid, 0) only asks whether the process exists; EPERM means it does, under another user.
function alive(pid: number) {
  try { process.kill(pid, 0); return true; } catch (e: any) { return e?.code === 'EPERM'; }
}
function readLock(file: string): Lock | undefined {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e: any) { if (e?.code === 'ENOENT') return undefined; throw e; }
}
// Written to a file of its own and linked into place, so two starts at the same moment can't both take the lock.
function tryTake(run: string): boolean {
  const mine = `${LOCK}.${process.pid}`;
  fs.writeFileSync(mine, JSON.stringify({ run, pid: process.pid, started: localText(new Date()) }));
  try { fs.linkSync(mine, LOCK); return true; } catch (e: any) { if (e?.code !== 'EEXIST') throw e; return false; } finally { fs.unlinkSync(mine); }
}
// A dead run's lock is moved aside, not deleted: if another waiting run took it over first, what moved is its live
// lock and goes back.
function clearDead(dead: Lock) {
  const aside = `${LOCK}.${process.pid}.old`;
  try { fs.renameSync(LOCK, aside); } catch (e: any) { if (e?.code === 'ENOENT') return; throw e; }
  if (readLock(aside)?.pid !== dead.pid) { try { fs.linkSync(aside, LOCK); } catch { /* taken meanwhile */ } }
  fs.unlinkSync(aside);
}

export default async function runLock() {
  const limit = Number(process.env.QA_WAIT ?? 30);
  if (!(limit >= 0)) throw new Error('QA_WAIT is the most minutes to wait for another run, for example QA_WAIT=30. QA_WAIT=0 stops at once.');
  const args = process.argv.slice(process.argv.indexOf('test') + 1);
  const run = [...args, process.env.QA_ROUND, process.env.QA_REASON].filter(Boolean).join(' ');
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const asked = Date.now();
  let told = 0;
  while (!tryTake(run)) {
    const held = readLock(LOCK);
    if (!held) continue;
    if (!alive(held.pid)) { clearDead(held); continue; }
    const who = `${held.run}, started ${held.started}, process ${held.pid}`;
    const waited = Date.now() - asked;
    if (waited >= limit * 60_000) {
      throw new Error(`Another QA run is in progress (${who})${limit ? `, and it hasn't finished in ${limit} minutes` : ''}. ` +
        "Runs share the test users, so only one goes at a time: wait for it to finish, then run this again. Don't delete the lock.");
    }
    if (!told || Date.now() - told >= 60_000) {
      told = Date.now();
      console.log(`Waiting for another QA run to finish (${who}). Waited ${Math.floor(waited / 60_000)} of ${limit} minutes; QA_WAIT=0 stops instead.`);
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  const release = () => { try { if (readLock(LOCK)?.pid === process.pid) fs.unlinkSync(LOCK); } catch { /* already gone */ } };
  process.on('exit', release);
  return release;
}
