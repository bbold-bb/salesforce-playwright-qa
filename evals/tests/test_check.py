import unittest

from evals import check
from evals.lib import runs


class CheckRun(unittest.TestCase):
    def setUp(self):
        check.HARD_CHECKS["steps-"] = lambda run, ws: []

    def tearDown(self):
        check.HARD_CHECKS.pop("steps-", None)

    def test_errored_run_fails_with_no_output(self):
        r = runs.RunRef(case="steps-ACME-11", arm="with", index=0, kept=None, runner_score=0.8, error="timed out")
        findings, _ = check.check_run(r)
        self.assertEqual([(f.rule, f.passed) for f in findings], [("output", False)])
        self.assertIn("timed out", findings[0].detail)

    def test_crashing_check_fails_the_run_only(self):
        def boom(run, ws):
            raise ValueError("bad file")
        check.HARD_CHECKS["steps-"] = boom
        r = runs.RunRef(case="steps-ACME-11", arm="with", index=0, kept=None, runner_score=0.8, error=None)
        # no workspace still wins over the crash: output is checked first
        findings, _ = check.check_run(r)
        self.assertEqual(findings[0].rule, "output")

    def test_case_without_hard_checks_has_no_findings(self):
        r = runs.RunRef(case="smoke", arm="with", index=0, kept=None, runner_score=1, error=None)
        self.assertEqual(check.check_run(r), ([], ""))


if __name__ == "__main__":
    unittest.main()


class Register(unittest.TestCase):
    def test_a_broken_checks_module_stops_the_report(self):
        import sys
        saved = sys.modules.get("evals.lib.tiers")
        sys.modules["evals.lib.tiers"] = None  # makes the import fail
        try:
            with self.assertRaises(ImportError):
                check._register()
        finally:
            if saved is not None:
                sys.modules["evals.lib.tiers"] = saved
            else:
                sys.modules.pop("evals.lib.tiers", None)


class TimedOut(unittest.TestCase):
    def test_a_timed_out_run_is_labelled_in_the_table(self):
        import json
        import tempfile
        from pathlib import Path
        d = {"suite": {}, "cases": [{"name": "smoke", "arms": {"with": [
            {"score": 0, "error": "timed out after 600s"}]}}]}
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "result.json"
            p.write_text(json.dumps(d))
            check.main([str(p)])
            table = (Path(t) / "scores.md").read_text()
        self.assertIn("1 timed out", table)


class JudgeInCheck(unittest.TestCase):
    def setUp(self):
        import json
        import shutil
        import tempfile
        from pathlib import Path
        from evals.lib.judge import Verdict
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        ws = self.tmp / "ws"
        (ws / "qa-steps").mkdir(parents=True)
        fix = Path(check.REPO) / "evals/fixtures/acme-support/approved/ACME-12.md"
        (ws / "qa-steps" / "ACME-12.md").write_text(fix.read_text())
        self.result = self.tmp / "result.json"
        self.result.write_text(json.dumps({"suite": {}, "cases": [{"name": "steps-ACME-12", "arms": {"with": [
            {"score": 1.0, "error": None, "workspacePath": str(ws),
             "graders": [{"name": "a", "passed": True, "scored": True}, {"name": "b", "passed": True, "scored": True},
                         {"name": "skill", "passed": False, "scored": False}]}]}}]}))
        self.calls = []

        def fake(rubric, content, **kw):
            self.calls.append((rubric, content))
            return Verdict(passed=False, votes=["FAIL", "FAIL", "PASS"], reasons=["step 3 is vague", "x", "ok"], cost=0.03)
        self.saved = check.JUDGE
        check.JUDGE = fake
        self.addCleanup(setattr, check, "JUDGE", self.saved)

    def test_judge_runs_on_the_draft_with_the_cases_rubric(self):
        check.main([str(self.result)])
        self.assertEqual(len(self.calls), 1)
        self.assertIn("ACME-12", self.calls[0][0])           # the case's own rubric.md
        self.assertIn("Resolution Summary", self.calls[0][1])  # the draft

    def test_failed_judge_counts_as_one_soft_check_and_keeps_its_reasons(self):
        import json
        check.main([str(self.result)])
        rows = json.loads((self.result.parent / "hard-checks.json").read_text())
        self.assertAlmostEqual(rows[0]["score"], 2 / 3)
        self.assertEqual(rows[0]["judge"]["votes"], ["FAIL", "FAIL", "PASS"])
        self.assertIn("step 3 is vague", (self.result.parent / "outputs/steps-ACME-12/with-1/judge.md").read_text())

    def test_unavailable_judge_leaves_the_runner_score(self):
        import json
        from evals.lib.judge import Verdict
        check.JUDGE = lambda rubric, content, **kw: Verdict(passed=None, failed_calls=["x", "x", "x"])
        check.main([str(self.result)])
        rows = json.loads((self.result.parent / "hard-checks.json").read_text())
        self.assertEqual(rows[0]["score"], 1.0)
        self.assertIn("judge unavailable", (self.result.parent / "scores.md").read_text())

    def test_no_judge_flag_skips_it(self):
        check.main([str(self.result), "--no-judge"])
        self.assertEqual(self.calls, [])
