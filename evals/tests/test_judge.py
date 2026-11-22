import unittest

from evals.lib import judge


def fake(answers):
    calls = []

    def ask(prompt, model):
        calls.append(prompt)
        v, r = answers[len(calls) - 1]
        return v, r, 0.01
    ask.calls = calls
    return ask


class Judge(unittest.TestCase):
    def test_majority_of_three_passes(self):
        v = judge.judge("rubric", "file", votes=3, ask=fake([("PASS", "ok"), ("FAIL", "step 2"), ("PASS", "ok")]))
        self.assertTrue(v.passed)
        self.assertEqual(v.votes, ["PASS", "FAIL", "PASS"])
        self.assertEqual(v.reasons, ["ok", "step 2", "ok"])
        self.assertAlmostEqual(v.cost, 0.03)

    def test_majority_of_three_fails(self):
        v = judge.judge("rubric", "file", votes=3, ask=fake([("FAIL", "a"), ("FAIL", "b"), ("PASS", "c")]))
        self.assertFalse(v.passed)

    def test_prompt_carries_rubric_and_file(self):
        ask = fake([("PASS", "ok")])
        judge.judge("RUBRIC TEXT", "FILE TEXT", votes=1, ask=ask)
        self.assertIn("RUBRIC TEXT", ask.calls[0])
        self.assertIn("FILE TEXT", ask.calls[0])

    def test_a_failed_call_is_not_a_vote(self):
        answers = iter([RuntimeError("claude not found"), ("PASS", "ok"), ("FAIL", "step 2")])
        def ask(prompt, model):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a[0], a[1], 0.01
        v = judge.judge("r", "f", votes=3, ask=ask)
        self.assertEqual(v.votes, ["PASS", "FAIL"])
        self.assertEqual(v.failed_calls, ["claude not found"])
        self.assertFalse(v.passed)  # 1 of 2 valid votes is not a majority

    def test_no_valid_votes_means_unavailable(self):
        def ask(prompt, model):
            raise RuntimeError("claude not found")
        v = judge.judge("r", "f", votes=3, ask=ask)
        self.assertIsNone(v.passed)
        self.assertEqual(v.votes, [])

    def test_combined_score_counts_the_judge_as_one_soft_check(self):
        # two runner checks both passed (runner score 1.0) and the judge failed: 2 of 3
        self.assertAlmostEqual(judge.combined(1.0, 2, False), 2 / 3)
        self.assertAlmostEqual(judge.combined(0.5, 2, True), 2 / 3)
        self.assertAlmostEqual(judge.combined(1.0, 0, True), 1.0)


if __name__ == "__main__":
    unittest.main()
