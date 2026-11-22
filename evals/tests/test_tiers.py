import shutil
import tempfile
import unittest
from pathlib import Path

from evals.lib import tiers
from evals.lib.runs import RunRef

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "acme-support"


def run(case):
    return RunRef(case=case, arm="with", index=0, kept=None, runner_score=1.0, error=None)


class StepsTier(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.ws)

    def test_registers_steps_prefix(self):
        checks, notes = {}, {}
        tiers.register(checks, notes)
        self.assertIn("steps-", checks)

    def test_approved_draft_passes(self):
        (self.ws / "qa-steps").mkdir()
        shutil.copy(FIX / "approved" / "ACME-12.md", self.ws / "qa-steps" / "ACME-12.md")
        bad = [f.rule for f in tiers.check_steps_run(run("steps-ACME-12"), self.ws) if not f.passed]
        self.assertEqual(bad, [])

    def test_missing_draft_fails_output_file(self):
        found = tiers.check_steps_run(run("steps-ACME-12"), self.ws)
        self.assertEqual([(f.rule, f.passed) for f in found], [("output-file", False)])

    def test_key_comes_from_the_repo_not_the_workspace(self):
        (self.ws / "qa-steps").mkdir()
        shutil.copy(FIX / "approved" / "ACME-16.md", self.ws / "qa-steps" / "ACME-16.md")
        (self.ws / "keys").mkdir()
        (self.ws / "keys" / "ACME-16.json").write_text("{}")  # a planted key is ignored
        bad = [f.rule for f in tiers.check_steps_run(run("steps-ACME-16"), self.ws) if not f.passed]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()


class SpecTier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Path(tempfile.mkdtemp())
        src = FIX.parent.parent.parent / "templates" / "qa" / "playwright"
        shutil.copytree(src, cls.ws, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", "test-results"))
        (cls.ws / "node_modules").symlink_to(src / "node_modules")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws)

    def test_registers_spec_prefix(self):
        checks, notes = {}, {}
        tiers.register(checks, notes)
        self.assertIn("spec-", checks)

    def test_good_spec_passes(self):
        good = (Path(__file__).parent / "data" / "spec-good.ts").read_text()
        (self.ws / "tests" / "ACME-11.spec.ts").write_text(good)
        bad = [f"{f.rule}: {f.detail}" for f in tiers.check_spec_run(run("spec-ACME-11"), self.ws) if not f.passed]
        self.assertEqual(bad, [])

    def test_missing_spec_fails_output_file(self):
        found = tiers.check_spec_run(run("spec-ACME-12"), self.ws)
        self.assertEqual([(f.rule, f.passed) for f in found], [("output-file", False)])


class Outputs(unittest.TestCase):
    def test_outputs_lists_draft_spec_and_rehearsal(self):
        ws = Path(tempfile.mkdtemp())
        try:
            (ws / "qa-steps").mkdir()
            (ws / "qa-steps" / "ACME-11.md").write_text("x")
            (ws / "tests").mkdir()
            (ws / "tests" / "ACME-11.spec.ts").write_text("x")
            d = ws / "evidence" / "rehearsal" / "ACME-11 x" / "o R0"
            d.mkdir(parents=True)
            (d / "results.json").write_text("{}")
            (ws / "claude.json").write_text("{}")
            got = sorted(str(p.relative_to(ws)) for p in tiers.outputs(run("spec-ACME-11"), ws))
            self.assertEqual(got, ["claude.json", "evidence/rehearsal/ACME-11 x/o R0/results.json",
                                   "qa-steps/ACME-11.md", "tests/ACME-11.spec.ts"])
        finally:
            shutil.rmtree(ws)


class OrgTier(unittest.TestCase):
    def test_registers_org_check_and_note(self):
        checks, notes = {}, {}
        tiers.register(checks, notes)
        self.assertIn("org-", checks)
        self.assertIn("org-", notes)

    def test_note_reports_attempts(self):
        ws = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(tiers.org_note(run("org-ACME-11"), ws), "0 rehearsal attempts")
        finally:
            shutil.rmtree(ws)
