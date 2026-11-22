import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "org" / "guard" / "sf"


class SfGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fake = self.tmp / "real-sf"
        self.fake.write_text("#!/bin/bash\necho REAL \"$@\"\n")
        self.fake.chmod(0o755)
        self.env = {**os.environ, "QA_EVALS_REAL_SF": str(self.fake), "QA_EVALS_ORG_ALIAS": "qa-evals-1"}

    def sf(self, *args):
        return subprocess.run([str(GUARD), *args], env=self.env, capture_output=True, text=True)

    def test_allows_harness_commands_on_the_scratch_org(self):
        for args in (["data", "query", "-q", "SELECT Id FROM Case", "-o", "qa-evals-1", "--json"],
                     ["org", "open", "--url-only", "--path", "/x", "-o", "qa-evals-1", "--json"],
                     ["sobject", "describe", "-s", "Case", "--target-org", "qa-evals-1"],
                     ["api", "request", "rest", "/services", "-o", "qa-evals-1"]):
            r = self.sf(*args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("REAL "), args)

    def test_blocks_another_org(self):
        r = self.sf("data", "query", "-q", "SELECT Id FROM Case", "-o", "Client-Prod")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("REAL", r.stdout)

    def test_blocks_equals_form_of_another_org(self):
        r = self.sf("data", "query", "-q", "x", "--target-org=Client-Prod")
        self.assertNotEqual(r.returncode, 0)

    def test_blocks_a_second_target_org(self):
        r = self.sf("data", "query", "-q", "x", "-o", "qa-evals-1", "-o", "Client-Prod")
        self.assertNotEqual(r.returncode, 0)

    def test_no_target_org_goes_to_the_scratch_org(self):
        r = self.sf("data", "query", "-q", "x")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.rstrip().endswith("-o qa-evals-1"), r.stdout)

    def test_blocks_other_commands(self):
        for args in (["org", "delete", "scratch", "-o", "qa-evals-1"], ["project", "deploy", "start", "-o", "qa-evals-1"],
                     ["org", "list"], ["data", "delete", "record", "-o", "qa-evals-1"]):
            self.assertNotEqual(self.sf(*args).returncode, 0, args)


if __name__ == "__main__":
    unittest.main()
