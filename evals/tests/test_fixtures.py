import json
import re
import unittest
from pathlib import Path

from evals.lib.steps_check import parse_steps, check_steps

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "acme-support"
TICKETS = [f"ACME-{n}" for n in range(11, 17)]
# Words that would mean real client, employer or project content leaked into the invented fixtures. Kept out of the
# public repo: each person lists their own in evals/tests/deny-words.txt (gitignored, one word per line). Without the
# file, the name scan is skipped.
DENY_FILE = Path(__file__).resolve().parent / "deny-words.txt"
DENY = [w.strip().lower() for w in DENY_FILE.read_text().splitlines() if w.strip()] if DENY_FILE.is_file() else []


class Fixtures(unittest.TestCase):
    def test_every_ticket_has_all_four_files(self):
        for t in TICKETS:
            for p in (FIX / "stories" / f"{t}.md", FIX / "builds" / f"{t}-build.md",
                      FIX / "approved" / f"{t}.md", FIX / "keys" / f"{t}.json"):
                self.assertTrue(p.is_file(), p)

    def test_every_approved_passes_its_key(self):
        for t in TICKETS:
            text = (FIX / "approved" / f"{t}.md").read_text()
            key = json.loads((FIX / "keys" / f"{t}.json").read_text())
            bad = [f"{f.rule}: {f.detail}" for f in check_steps(parse_steps(text), key, text) if not f.passed]
            self.assertEqual(bad, [], t)

    def test_key_criteria_match_the_story(self):
        for t in TICKETS:
            story = (FIX / "stories" / f"{t}.md").read_text()
            ac = story.split("## Acceptance criteria", 1)[1].split("\n## ", 1)[0]
            numbers = [int(n) for n in re.findall(r"^(\d+)\.", ac, re.M)]
            key = json.loads((FIX / "keys" / f"{t}.json").read_text())
            self.assertEqual(sorted(int(k) for k in key["criteria"]), numbers, t)

    @unittest.skipUnless(DENY, "no evals/tests/deny-words.txt")
    def test_no_real_names(self):
        for p in FIX.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.relative_to(FIX).parts):
                text = p.read_text().lower()
                for w in DENY:
                    self.assertIsNone(re.search(rf"\b{w}\b", text), f"{w} in {p}")


if __name__ == "__main__":
    unittest.main()
