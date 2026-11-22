import json
import tempfile
import unittest
from pathlib import Path

from evals.lib import runs

DATA = Path(__file__).parent / "data"


class LoadRuns(unittest.TestCase):
    def test_load_runs_reads_arms_and_paths(self):
        found = runs.load_runs(DATA / "aggregate-sample.json")
        self.assertEqual([r.arm for r in found], ["with", "without"])
        self.assertEqual(found[0].case, "smoke")
        self.assertEqual(found[0].index, 0)
        self.assertEqual(found[0].runner_score, 1)
        self.assertEqual(found[0].kept, Path("/kept/e-with"))

    def test_errored_run_has_no_workspace(self):
        d = json.loads((DATA / "aggregate-sample.json").read_text())
        run = d["cases"][0]["arms"]["with"][0]
        run["error"] = "timed out"
        run.pop("tracePath")
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "r.json"
            p.write_text(json.dumps(d))
            found = runs.load_runs(p)
        self.assertIsNone(found[0].kept)
        self.assertIsNone(runs.workspace(found[0]))
        self.assertEqual(found[0].error, "timed out")

    def test_missing_kept_folder_gives_no_workspace(self):
        found = runs.load_runs(DATA / "aggregate-sample.json")
        self.assertIsNone(runs.workspace(found[0]))  # /kept/e-with doesn't exist

    def test_workspace_opens_sealed_folder(self):
        with tempfile.TemporaryDirectory() as t:
            kept = Path(t) / "e-x"
            cwd = kept / "sealed" / "home" / "cwd"
            cwd.mkdir(parents=True)
            (cwd / "out.txt").write_text("hi")
            (kept / "sealed").chmod(0)
            kept.chmod(0o500)
            r = runs.RunRef(case="c", arm="with", index=0, kept=kept, runner_score=1.0, error=None)
            ws = runs.workspace(r)
            self.assertEqual((ws / "out.txt").read_text(), "hi")
            runs.cleanup(r)
            self.assertFalse(kept.exists())

    def test_direct_workspace_is_used_and_never_deleted(self):
        with tempfile.TemporaryDirectory() as t:
            ws = Path(t) / "run-1"
            ws.mkdir()
            data = {"cases": [{"name": "org-ACME-11", "arms": {"with": [
                {"score": 1, "error": None, "workspacePath": str(ws)}]}}]}
            p = Path(t) / "r.json"
            p.write_text(json.dumps(data))
            r = runs.load_runs(p)[0]
            self.assertEqual(runs.workspace(r), ws)
            runs.cleanup(r)
            self.assertTrue(ws.exists())

    def test_cleanup_removes_kept_folder(self):
        with tempfile.TemporaryDirectory() as t:
            kept = Path(t) / "e-y"
            (kept / "out").mkdir(parents=True)
            r = runs.RunRef(case="c", arm="with", index=0, kept=kept, runner_score=1.0, error=None)
            runs.cleanup(r)
            self.assertFalse(kept.exists())

    def test_cleanup_tolerates_missing_folder(self):
        r = runs.RunRef(case="c", arm="with", index=0, kept=None, runner_score=0.0, error="x")
        runs.cleanup(r)  # no exception


if __name__ == "__main__":
    unittest.main()
