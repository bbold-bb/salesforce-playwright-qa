import fs from 'fs';
import path from 'path';
import { ORG_ALIAS, PERSONAS_FILE, TEST_USERS_FILE } from './config';
import { query } from './salesforce';

// The test users this machine signs in as. Who a spec tests as is an entry in personas.json (usually a persona), which
// the team shares. testUser('Specialist') gives this machine's user for it, from test-users.local.json, which is this
// machine's own and gitignored (README.md, Test users). ../../test_users.py creates the users and writes that file:
//   { "my-partial-sandbox": { "Specialist": "SpecialistTest Ana P", "Supervisor": "SupervisorTest Ana P" } }
// It goes by org, since a tester's users exist only where they were created. Reading it never asks the org, so
// `playwright test --list` works anywhere. The global setup below checks the users before any spec starts.
export type TestUserSet = Record<string, string>;
const NOT_SET_UP = ' (no test user on this machine)';
const HOW = `From the qa folder: python3 test_users.py --org ${ORG_ALIAS} --tester "<your name>" (README.md, Test users).`;

function readJson(file: string): any {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e: any) { throw new Error(`${path.basename(file)} can't be read: ${e.message}`); }
}
export const personas: string[] = fs.existsSync(PERSONAS_FILE) ? Object.keys(readJson(PERSONAS_FILE).personas ?? {}) : [];

function read(): TestUserSet {
  if (!fs.existsSync(TEST_USERS_FILE)) return {};
  const entry = readJson(TEST_USERS_FILE)?.[ORG_ALIAS];
  if (entry === undefined) return {};
  const bad = (why: string) => new Error(`${path.basename(TEST_USERS_FILE)}, ${ORG_ALIAS}: ${why}. ${HOW}`);
  if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) throw bad("isn't a list of personas and users");
  for (const [k, v] of Object.entries(entry)) {
    if (!personas.includes(k)) throw bad(`${k} isn't in personas.json (${personas.join(', ')})`);
    if (typeof v !== 'string' || !v.trim() || v !== v.trim()) throw bad(`no user for ${k}`);
  }
  if (new Set(Object.values(entry)).size !== Object.keys(entry).length) throw bad('one user stands for two personas');
  return entry as TestUserSet;
}
export const testUserSet: TestUserSet = read();

// This machine's user for a persona. With none set up it's a name no user has, so a spec still lists, and signIn stops.
export function testUser(persona: string): string {
  if (!personas.includes(persona)) throw new Error(`${persona} isn't in personas.json (${personas.join(', ')})`);
  return testUserSet[persona] ?? `${persona}${NOT_SET_UP}`;
}

// Called before every sign-in as a test user (lib/salesforce.ts).
export function checkSetUp(userName: string) {
  if (userName.endsWith(NOT_SET_UP)) throw new Error(`No test user for ${userName.slice(0, -NOT_SET_UP.length)} in ${ORG_ALIAS} on this machine. ${HOW}`);
}

// The personas two sets give to different users. A set from before this was recorded can't be compared, and a persona in
// only one of them isn't a change.
export function usersDiffer(a: TestUserSet | undefined, b: TestUserSet | undefined): string[] {
  if (!a || !b) return [];
  return Object.keys(a).filter((k) => b[k] !== undefined && a[k] !== b[k]).map((k) => `${a[k]} to ${b[k]}`);
}

// Playwright global setup (playwright.config.ts): before any spec starts, this machine's users are there and active, one
// user to a name. It never falls back to another user.
export default async function checkTestUsers() {
  if (!personas.length) return;
  const names = Object.values(testUserSet);
  if (!names.length) throw new Error(`No test users for ${ORG_ALIAS} on this machine, so nothing ran. ${HOW}`);
  const found = query(`SELECT Name FROM User WHERE IsActive = true AND Name IN (${names.map((n) => `'${n.replace(/'/g, "\\'")}'`).join(', ')})`).map((r) => r.Name);
  const wrong = names.filter((n) => found.filter((f) => f === n).length !== 1);
  if (wrong.length) throw new Error(`${path.basename(TEST_USERS_FILE)}, ${ORG_ALIAS}: expected one active user named ${wrong.join(', ')}. Nothing ran. ${HOW}`);
  console.log(`Test users in ${ORG_ALIAS}: ${names.join(', ')}`);
}
