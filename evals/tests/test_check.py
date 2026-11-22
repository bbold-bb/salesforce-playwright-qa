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
