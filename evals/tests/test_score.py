import unittest

from evals.lib.score import Finding, run_score, case_table, Row


class RunScore(unittest.TestCase):
    def test_run_score_zero_on_any_failed_finding(self):
        self.assertEqual(run_score(0.9, [Finding("a", True, ""), Finding("b", False, "x")]), 0)

    def test_run_score_keeps_runner_score_when_all_pass(self):
        self.assertEqual(run_score(0.9, [Finding("a", True, "")]), 0.9)

    def test_run_score_no_findings_keeps_runner_score(self):
        self.assertEqual(run_score(0.5, []), 0.5)


class CaseTable(unittest.TestCase):
    def rows(self, case, arm, scores):
        return [Row(case=case, arm=arm, index=i, score=s, failed=[]) for i, s in enumerate(scores)]

    def test_case_table_marks_pass_at_067(self):
        table = case_table(self.rows("a", "with", [0.67]) + self.rows("b", "with", [0.66]))
        line_a = next(l for l in table.splitlines() if l.startswith("| a |"))
        line_b = next(l for l in table.splitlines() if l.startswith("| b |"))
        self.assertIn("| yes |", line_a)
        self.assertIn("| no |", line_b)

    def test_two_of_three_passes(self):
        table = case_table(self.rows("a", "with", [1, 1, 0]))
        self.assertIn("| yes |", next(l for l in table.splitlines() if l.startswith("| a |")))

    def test_case_table_shows_with_without_gap(self):
        table = case_table(self.rows("a", "with", [1, 1, 0.5]) + self.rows("a", "without", [0.5, 0.5, 0.5]))
        line = next(l for l in table.splitlines() if l.startswith("| a |"))
        self.assertIn("+0.33", line)

    def test_case_table_without_arm_missing(self):
        table = case_table(self.rows("a", "with", [1]))
        line = next(l for l in table.splitlines() if l.startswith("| a |"))
        self.assertIn("| n/a |", line)


if __name__ == "__main__":
    unittest.main()
