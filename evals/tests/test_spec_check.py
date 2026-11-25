import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from evals.lib.spec_check import check_spec, compile_check
from evals.lib.steps_check import parse_steps

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GOOD = (HERE / "data" / "spec-good.ts").read_text()
APPROVED = parse_steps((REPO / "evals/fixtures/acme-support/approved/ACME-11.md").read_text())


def failed(text):
    return sorted(f.rule for f in check_spec(text, APPROVED, "ACME-11") if not f.passed)


class Rules(unittest.TestCase):
    def test_good_spec_passes_all_rules(self):
        self.assertEqual(failed(GOOD), [])

    def test_bad_scenarios_match_tag(self):
        self.assertEqual(failed(GOOD.replace("evidence: ['query']", "evidence: ['screenshot']")), ["scenarios-match"])

    def test_bad_scenarios_match_missing_step(self):
        text = GOOD.replace("  { id: 'S4', title: `Support Agent access to ${FIELD.label}`, expected: 'read and edit (criterion 4)', evidence: ['query'] },\n", "")
        self.assertEqual(failed(text), ["scenarios-match"])

    def test_bad_scenarios_match_flow(self):
        self.assertIn("scenarios-match", failed(GOOD.replace("{ id: 'S3', flow: 'F1'", "{ id: 'S3', flow: 'F2'")))

    def test_bad_opening_card_per_flow(self):
        text = GOOD.replace("  await openingCard(page, run, { video: 1, name: 'The agent records a channel and finds it in the report', steps: '2 and 3', runAs: AGENT });\n", "")
        self.assertEqual(failed(text), ["opening-card-per-flow"])

    def test_bad_chapter_per_video_step(self):
        text = GOOD.replace("      await chapter(page, `Step 3 of ${TOTAL_STEPS}: ${r.S3.title}`, r.S3.expected, `From ${FOLDER}.`);\n", "")
        self.assertEqual(failed(text), ["chapter-per-video-step"])

    def test_bad_no_brittle_locator(self):
        for bad in ["page.locator('xpath=//button')", "page.locator('//div[1]')", "page.getByRole('row').nth(2)",
                    "page.locator('.slds-button')", "page.locator('#saveBtn')"]:
            text = GOOD.replace("await page.getByRole('button', { name: 'Save', exact: true }).click();", f"await {bad}.click();")
            self.assertEqual(failed(text), ["no-brittle-locator"], bad)

    def test_bad_no_skip(self):
        for bad in ["test.skip(", "test.fixme(", "test.only(", "test.use({ storageState: 'x.json' });\ntest("]:
            text = GOOD.replace("test('S4 the permission set", bad + "'S4 the permission set", 1)
            self.assertEqual(failed(text), ["no-skip"], bad)

    def test_bad_record_naming(self):
        self.assertEqual(failed(GOOD.replace("const PREFIX = `QA ${TICKET} ${ROUND}`;", "const PREFIX = `Test ${TICKET}`;")),
                         ["record-naming"])

    def test_record_naming_skipped_without_video_steps(self):
        approved = parse_steps((REPO / "evals/fixtures/acme-support/approved/ACME-13.md").read_text())
        found = {f.rule: f.passed for f in check_spec("const SCENARIOS: Scenario[] = [\n];", approved, "ACME-13")}
        self.assertTrue(found["record-naming"])

    def test_record_naming_applies_to_screenshot_steps(self):
        approved = parse_steps("1. Build check [Build check]\n2. As the agent, open the list. Criterion 1. [Screenshot]\n")
        found = {f.rule: f.passed for f in check_spec("const SCENARIOS: Scenario[] = [\n];", approved, "ACME-99")}
        self.assertFalse(found["record-naming"])

    def test_record_naming_accepts_record_prefix(self):
        self.assertEqual(failed(GOOD.replace("`QA ${TICKET} ${ROUND}`", "`${RECORD_PREFIX} ${TICKET} ${ROUND}`")), [])

    def test_bad_query_per_step(self):
        text = GOOD.replace("      expect(query(`SELECT Id FROM Case WHERE Id = '${id}' AND ${FIELD.api} = '${FIELD.value}'`)).toHaveLength(1);\n", "")
        self.assertEqual(failed(text), ["query-per-step"])

    def test_bad_typed_user(self):
        self.assertEqual(failed(GOOD.replace("testUser('SupportAgent')", "'Support Agent Test User'")), ["no-typed-user", "test-user-by-persona"])

    def test_bad_persona_not_through_test_user(self):
        self.assertEqual(failed(GOOD.replace("testUser('SupportAgent')", "'SupportAgentTest Ana P'")), ["test-user-by-persona"])

    def test_query_through_a_helper_of_a_helper_counts(self):
        text = GOOD.replace("const standalone =", "const channelOf = (id: string) => String(one(id)?.Contact_Channel__c ?? '');\nconst standalone =")
        text = text.replace("expect(one(id)[FIELD.api]).toBe(FIELD.value);", "expect(channelOf(id)).toBe(FIELD.value);")
        self.assertEqual(failed(text), [])

    def test_query_through_local_helper_counts(self):
        # step S2 checks through `one(id)`, a local helper that calls query(); the good spec relies on it.
        self.assertNotIn("query-per-step", failed(GOOD))


class Compile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.harness = cls.tmp / "playwright"
        src = REPO / "templates/qa/playwright"
        shutil.copytree(src, cls.harness, ignore=shutil.ignore_patterns("node_modules", "test-results", "test-users.local.json"))
        shutil.copy(REPO / "evals/fixtures/acme-support/personas.json", cls.harness / "personas.json")
        (cls.harness / "node_modules").symlink_to(src / "node_modules")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def write(self, text):
        (self.harness / "tests" / "ACME-11.spec.ts").write_text(text)

    def test_good_spec_compiles_and_lists(self):
        self.write(GOOD)
        bad = [f"{f.rule}: {f.detail}" for f in compile_check(self.harness, "ACME-11", APPROVED) if not f.passed]
        self.assertEqual(bad, [])

    def test_tsc_fails_unknown_import(self):
        self.write(GOOD.replace("  openReportFromFolder,", "  openReportFromFolder, missingHelper,"))
        found = {f.rule: f.passed for f in compile_check(self.harness, "ACME-11", APPROVED)}
        self.assertFalse(found["tsc"])

    def test_list_fails_when_a_test_is_missing(self):
        self.write(GOOD.split("test('S4 the permission set")[0])
        found = {f.rule: f.passed for f in compile_check(self.harness, "ACME-11", APPROVED)}
        self.assertFalse(found["list"])


if __name__ == "__main__":
    unittest.main()
