import unittest
from pathlib import Path

from evals.lib.steps_check import parse_steps, check_steps

GOOD = (Path(__file__).parent / "data" / "steps-good.md").read_text()

KEY = {
    "ticket": "ACME-11",
    "criteria": {
        "1": {"tags": ["Video"], "where": "step"},
        "2": {"tags": ["Build check"], "where": "step"},
        "3": {"tags": ["Video"], "where": "step"},
        "4": {"tags": ["Query", "Build check"], "where": "step"},
    },
    "users": ["Support Agent Test User"],
    "forbidden": [],
    "max_flows": 1,
}


def failed(text, key=KEY):
    return sorted(f.rule for f in check_steps(parse_steps(text), key, text) if not f.passed)


class Parse(unittest.TestCase):
    def test_parse_good_draft(self):
        d = parse_steps(GOOD)
        self.assertEqual([s.number for s in d.steps], [1, 2, 3, 4, 5])
        self.assertEqual(d.flows, {"F1": "Support Agent Test User"})
        self.assertEqual([s.flow for s in d.steps], [None, "F1", "F1", None, None])
        self.assertEqual([s.tag for s in d.steps], ["Build check", "Video", "Video", "Query", "Query"])
        self.assertEqual(sorted(d.coverage), [1, 2, 3, 4])

    def test_parse_criterion_variants(self):
        d = parse_steps(GOOD)
        self.assertEqual(d.steps[1].criteria, [1])     # "Criterion 1"
        self.assertEqual(d.steps[2].criteria, [3])     # "AC 3"
        self.assertEqual(d.steps[3].criteria, [2, 4])  # "Criteria 4 and 2"
        self.assertEqual(d.steps[4].criteria, [1])     # lower case

    def test_parse_more_criterion_variants(self):
        d = parse_steps("1. Build check [Build check]\n2. A. Criteria 1, 2, and 3. [Video]\n3. B. ACs 2 and 4. [Video]\n"
                        "4. C. Criteria: 2. [Query]\n")
        self.assertEqual([s.criteria for s in d.steps[1:]], [[1, 2, 3], [2, 4], [2]])

    def test_parse_coverage_bullet_variants(self):
        d = parse_steps("1. Build check [Build check]\n\nCoverage\n- Criterion 1 (Email): step 2.\n"
                        "- Criteria 2 and 3: step 1.\n- **AC 4**: step 3.\n")
        self.assertEqual(sorted(d.coverage), [1, 2, 3, 4])

    def test_parse_flow_user_variants(self):
        d = parse_steps("Flow F1, as the Support Agent Test User (Standard User)\n2. x. Criterion 1. [Video]\n")
        self.assertEqual(d.flows, {"F1": "Support Agent Test User"})

    def test_parse_tag_on_continuation_line(self):
        d = parse_steps("1. Build check\n   Compare the org. [Build check]\n\nCoverage\n- Criterion 1: step 1.\n")
        self.assertEqual(d.steps[0].tag, "Build check")

    def test_parse_two_tags_keeps_both_for_the_rule(self):
        d = parse_steps("1. Build check [Build check] [Query]\n")
        self.assertEqual(d.steps[0].tags, ["Build check", "Query"])


class Rules(unittest.TestCase):
    def test_good_draft_passes_every_rule(self):
        self.assertEqual(failed(GOOD), [])

    def test_build_check_first(self):
        self.assertEqual(failed(GOOD.replace("1. Build check [Build check]", "1. Build check [Query]")),
                         ["build-check-first", "tag-matches-key"])

    def test_step_has_tag(self):
        self.assertEqual(failed(GOOD.replace("criterion 1. [Query]", "criterion 1.")), ["step-has-tag"])

    def test_step_has_criterion(self):
        self.assertEqual(failed(GOOD.replace("one case with Email. criterion 1.", "one case with Email.")),
                         ["step-has-criterion"])

    def test_coverage_complete(self):
        self.assertEqual(failed(GOOD.replace("- Criterion 4: step 4.\n", "")), ["coverage-complete"])

    def test_coverage_no_extra(self):
        self.assertEqual(failed(GOOD + "- Criterion 9: not tested.\n"), ["coverage-no-extra"])

    def test_tag_matches_key(self):
        self.assertEqual(failed(GOOD.replace("Criterion 1. [Video]", "Criterion 1. [Screenshot]")),
                         ["tag-matches-key"])

    def test_tag_matches_key_needs_a_step(self):
        text = GOOD.replace("Criteria 4 and 2. [Query]", "Criterion 2. [Query]")
        self.assertEqual(failed(text), ["tag-matches-key"])  # no step proves 4 now; 2 has a Query step

    def test_build_criterion_proven_through_coverage(self):
        # criterion 2 has no step of its own: Coverage points at the build check, which is enough.
        text = GOOD.replace("Criteria 4 and 2. [Query]", "Criterion 4. [Query]")
        self.assertEqual(failed(text), [])

    def test_allowed_users(self):
        self.assertEqual(failed(GOOD.replace("Flow F1, as Support Agent Test User",
                                             "Flow F1, as Support Supervisor Test User")), ["allowed-users"])

    def test_forbidden_absent(self):
        key = dict(KEY, forbidden=["Account Access"])
        self.assertEqual(failed(GOOD.replace("pick Email", "pick Account Access"), key), ["forbidden-absent"])

    def test_forbidden_ignores_the_build_check(self):
        key = dict(KEY, forbidden=["Account Access"])
        text = GOOD.replace("its values,", "its values (the build lists Account Access),")
        self.assertEqual(failed(text, key), [])

    def test_other_ticket_named(self):
        key = dict(KEY)
        key["criteria"] = dict(KEY["criteria"], **{"5": {"tags": [], "where": "other", "other": "ACME-17"}})
        self.assertEqual(failed(GOOD + "- Criterion 5: tested in the routing story.\n", key),
                         ["other-ticket-named"])
        self.assertEqual(failed(GOOD + "- Criterion 5: tested in ACME-17.\n", key), [])

    def test_max_flows(self):
        text = GOOD.replace("4. Query", "Flow F2, as Support Agent Test User\n4. Query")
        self.assertEqual(failed(text), ["max-flows"])


if __name__ == "__main__":
    unittest.main()
