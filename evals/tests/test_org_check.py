import json
import shutil
import tempfile
import unittest
from pathlib import Path

from evals.lib import org_check

HERE = Path(__file__).resolve().parent
GOOD_SPEC = (HERE / "data" / "spec-good.ts").read_text()


def result(sid, history):
    return {"id": sid, "title": sid, "passed": history[-1], "history": [
        {"attempt": i + 1, "passed": p} for i, p in enumerate(history)]}


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        (self.ws / "tests").mkdir()
        (self.ws / "tests" / "ACME-11.spec.ts").write_text(GOOD_SPEC)

    def tearDown(self):
        shutil.rmtree(self.ws)

    def write(self, results, attempts=1):
        d = self.ws / "evidence" / "rehearsal" / "ACME-11 E1.1 Contact Channel" / "scratch R0"
        d.mkdir(parents=True)
        (d / "results.json").write_text(json.dumps({
            "header": [], "attempts": [{"attempt": i + 1} for i in range(attempts)], "results": results}))

    def failed(self):
        return sorted(f.rule for f in org_check.rehearsal_findings(self.ws, "ACME-11") if not f.passed)

    def test_all_passed(self):
        self.write([result("S2", [True]), result("S3", [True]), result("S4", [True])])
        self.assertEqual(self.failed(), [])

    def test_one_failed_step(self):
        self.write([result("S2", [True]), result("S3", [False]), result("S4", [True])])
        self.assertEqual(self.failed(), ["all-steps-passed"])

    def test_a_step_never_run_fails(self):
        self.write([result("S2", [True]), result("S3", [True])])
        self.assertEqual(self.failed(), ["all-steps-passed"])

    def test_stop_rule_fires_after_three_failures(self):
        self.write([result("S2", [False, False, False]), result("S3", [True]), result("S4", [True])], attempts=3)
        self.assertEqual(self.failed(), ["all-steps-passed", "no-stop-rule"])

    def test_recovered_after_two_failures_is_fine(self):
        self.write([result("S2", [False, False, True]), result("S3", [True]), result("S4", [True])], attempts=3)
        self.assertEqual(self.failed(), [])

    def test_missing_results_json_fails(self):
        found = org_check.rehearsal_findings(self.ws, "ACME-11")
        self.assertEqual([(f.rule, f.passed) for f in found], [("rehearsal-ran", False)])
        self.assertIn("no rehearsal ran", found[0].detail)

    def test_forbidden_fix_fails(self):
        (self.ws / "tests" / "ACME-11.spec.ts").write_text(GOOD_SPEC.replace("test('S4 the", "test.skip('S4 the"))
        self.write([result("S2", [True]), result("S3", [True]), result("S4", [True])])
        self.assertEqual(self.failed(), ["no-forbidden-fix"])

    def test_final_spec_must_follow_every_spec_rule(self):
        (self.ws / "tests" / "ACME-11.spec.ts").write_text(
            GOOD_SPEC.replace("page.getByRole('button', { name: 'Save', exact: true })", "page.locator('xpath=//button')"))
        self.write([result("S2", [True]), result("S3", [True]), result("S4", [True])])
        self.assertEqual(self.failed(), ["no-brittle-locator"])

    def test_attempts_counts_attempts(self):
        self.write([result("S2", [False, True]), result("S3", [True]), result("S4", [True])], attempts=2)
        self.assertEqual(org_check.attempts(self.ws, "ACME-11"), 2)

    def test_attempts_zero_without_rehearsal(self):
        self.assertEqual(org_check.attempts(self.ws, "ACME-11"), 0)


if __name__ == "__main__":
    unittest.main()
