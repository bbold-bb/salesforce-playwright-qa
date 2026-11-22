import json
import shutil
import tempfile
import unittest
from pathlib import Path

from evals.org.write_result import build_result
from evals.lib import runs


class OrgResult(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.out)

    def run_dir(self, t, n, claude):
        d = self.out / "ws" / t / f"run-{n}"
        d.mkdir(parents=True)
        if claude is not None:
            (d / "claude.json").write_text(json.dumps(claude))
        return d

    def test_builds_cases_in_runner_shape(self):
        self.run_dir("ACME-11", 1, {"is_error": False, "total_cost_usd": 1.5, "num_turns": 40})
        self.run_dir("ACME-11", 2, {"is_error": True, "subtype": "error_max_budget_usd", "total_cost_usd": 8})
        self.run_dir("ACME-12", 1, None)
        res = build_result(self.out, model="opus")
        self.assertEqual([c["name"] for c in res["cases"]], ["org-ACME-11", "org-ACME-12"])
        a11 = res["cases"][0]["arms"]["with"]
        self.assertEqual([r["score"] for r in a11], [1, 0])
        self.assertEqual(a11[1]["error"], "error_max_budget_usd")
        self.assertEqual(res["cases"][1]["arms"]["with"][0]["error"], "no claude.json: the run didn't finish")
        self.assertEqual(res["costUsd"], 9.5)
        self.assertEqual(res["suite"]["modelOverride"], "opus")

    def test_working_folders_can_live_elsewhere(self):
        elsewhere = Path(tempfile.mkdtemp())
        try:
            d = elsewhere / "ACME-12" / "run-1"
            d.mkdir(parents=True)
            (d / "claude.json").write_text(json.dumps({"is_error": False, "total_cost_usd": 2}))
            res = build_result(self.out, model="opus", ws_root=elsewhere)
            self.assertEqual(res["cases"][0]["arms"]["with"][0]["workspacePath"], str(d))
        finally:
            shutil.rmtree(elsewhere)

    def test_check_reads_it(self):
        d = self.run_dir("ACME-11", 1, {"is_error": False, "total_cost_usd": 1})
        p = self.out / "result.json"
        p.write_text(json.dumps(build_result(self.out, model="opus")))
        r = runs.load_runs(p)[0]
        self.assertEqual(runs.workspace(r), d)


if __name__ == "__main__":
    unittest.main()
