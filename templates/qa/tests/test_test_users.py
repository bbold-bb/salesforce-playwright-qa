"""Tests for test_users.py that need no org. From the qa folder: python3 -m unittest discover -s tests"""
import copy, json, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import test_users as tu

ORG = "00D000000000001AAA"
BASE = {"defaults": {"TimeZoneSidKey": "America/New_York", "LocaleSidKey": "en_US", "LanguageLocaleKey": "en_US", "EmailEncodingKey": "UTF-8"},
        "personas": {"Specialist": {"profile": "Standard User", "permission_sets": ["Support_Agent"], "queues": ["Tier_2"]},
                     "Supervisor": {"profile": "Standard User"}}}
IDS = {("profile", "Standard User"): "00e1", ("permission_sets", "Support_Agent"): "0PS1", ("queues", "Tier_2"): "00G1"}


def user(ident, **over):
    return {"Id": "0051", "Name": tu.full_name(ident), "FirstName": ident["FirstName"], "LastName": ident["LastName"],
            "Username": ident["Username"], "Email": ident["Email"], "Alias": ident["Alias"], "IsActive": True,
            "Profile": {"Name": "Standard User"}, "UserRole": None, **{f: False for f in tu.USER_FIELDS}, **BASE["defaults"], **over}


def empty():
    return {k: set() for k in tu.ACCESS}


class Validate(unittest.TestCase):
    def bad(self, change, words):
        d = copy.deepcopy(BASE)
        change(d["personas"], d)
        self.assertTrue(any(words in p for p in tu.validate(d)), tu.validate(d))

    def test_shipped_file(self):
        self.assertEqual(tu.validate(json.loads(tu.PERSONAS.read_text())), [])

    def test_base(self):
        self.assertEqual(tu.validate(BASE), [])

    def test_problems(self):
        self.bad(lambda p, d: p.update({"SeniorSpecialist": {"profile": "Standard User"}}), "ends with Specialist")
        self.bad(lambda p, d: p.update({"two words": {"profile": "X"}}), "letters and digits")
        self.bad(lambda p, d: p["Specialist"].update(profile="Standard User "), "spaces around")
        self.bad(lambda p, d: p["Specialist"].update(queues=["A", "A"]), "twice")
        self.bad(lambda p, d: p["Specialist"].update(permsets=[]), "unknown key permsets")
        self.bad(lambda p, d: p["Specialist"].update(queues="A"), "isn't a list")
        self.bad(lambda p, d: d["defaults"].pop("TimeZoneSidKey"), "no TimeZoneSidKey")
        self.bad(lambda p, d: p["Specialist"].update(user={"UserPermissionsKnowledgeUser": "yes"}), "true or false")
        self.bad(lambda p, d: p["Specialist"].update(user={"Password": "x"}), "isn't a user field")
        self.bad(lambda p, d: p.clear(), "no entries")


class Names(unittest.TestCase):
    def test_identity(self):
        i = tu.identity("Specialist", "Ana P", ORG)
        self.assertEqual(tu.full_name(i), "SpecialistTest Ana P")
        self.assertEqual(i["Username"], "specialisttest.anap.00d000000000001aaa@example.com")
        self.assertEqual(i["Email"], "specialisttest.anap@example.com")
        self.assertLessEqual(len(i["Alias"]), 8)

    def test_two_testers_differ(self):
        a, b = (tu.identity("Specialist", t, ORG) for t in ("Ana P", "Raj Q"))
        for f in ("Username", "Email", "LastName"):
            self.assertNotEqual(a[f], b[f])

    def test_bad_testers(self):
        for t in ("", " Ana", "Ana  P", "!!!", "x" * 31, "Ana; P"):
            with self.assertRaises(tu.Stop, msg=t):
                tu.tester_tag(t)

    def test_too_long(self):
        with self.assertRaises(tu.Stop):
            tu.identity("A" * 25, "x" * 30, ORG)

    def test_clashes(self):
        self.assertTrue(tu.name_clashes(["SpecialistTest Ana P"], ["SpecialistTest Ana Parker"]))
        self.assertTrue(tu.name_clashes(["SpecialistTest Ana Parker"], ["specialisttest ana p"]))
        self.assertFalse(tu.name_clashes(["SpecialistTest Ana P"], ["SpecialistTest Raj Q", "SupervisorTest Ana P"]))


class Plan(unittest.TestCase):
    def plan(self, existing=None, held=None, tester="Ana P"):
        return tu.make_plan(BASE, ["Specialist"], tester, ORG, IDS, existing or {}, held or {})[0]

    def test_new(self):
        p = self.plan()
        self.assertIsNone(p["id"])
        self.assertTrue(p["uses_license"])
        self.assertEqual(p["add"]["permission_sets"], ["Support_Agent"])
        self.assertEqual(p["add"]["queues"], ["Tier_2"])

    def test_rerun_adds_only_what_is_missing(self):
        i = tu.identity("Specialist", "Ana P", ORG)
        p = self.plan({i["Username"]: user(i)}, {"0051": {**empty(), "permission_sets": {"Support_Agent", "Extra"}}})
        self.assertEqual((p["changes"], p["uses_license"]), ([], False))
        self.assertEqual(p["add"]["permission_sets"], [])
        self.assertEqual(p["add"]["queues"], ["Tier_2"])

    def test_after_rollback(self):
        i = tu.identity("Specialist", "Ana P", ORG)
        p = self.plan({i["Username"]: user(i, IsActive=False)}, {"0051": empty()})
        self.assertIn("inactive, made active", p["changes"])
        self.assertTrue(p["uses_license"])

    def test_someone_elses_username(self):
        i = tu.identity("Specialist", "Ana P", ORG)
        with self.assertRaises(tu.Stop):
            self.plan({i["Username"]: user(i)}, {"0051": empty()}, tester="AnaP")

    def test_real_email_refused(self):
        i = tu.identity("Specialist", "Ana P", ORG)
        with self.assertRaises(tu.Stop):
            self.plan({i["Username"]: user(i, Email="ana@acme.test")}, {"0051": empty()})

    def test_licenses(self):
        rows = [self.plan(), self.plan()]
        rows[0]["add"]["permission_set_licenses"] = ["Psl"]
        self.assertEqual(tu.license_needs(rows, {"Standard User": "Salesforce"}),
                         {("user license", "Salesforce"): 2, ("permission set license", "Psl"): 1})

    def test_check_reports_extra_access(self):
        i = tu.identity("Specialist", "Ana P", ORG)
        rows = tu.compare(BASE, "Specialist", i, user(i), {**empty(), "permission_sets": {"Support_Agent", "Extra"}, "queues": {"Tier_2"}})
        self.assertEqual([r[0] for r in rows if r[1] != r[2]], ["permission sets"])


class Apex(unittest.TestCase):
    def code(self, rehearse=False):
        return tu.build_apex(tu.make_plan(BASE, ["Specialist"], "Ana P", ORG, IDS, {}, {}), IDS, rehearse)

    def test_no_email_no_password(self):
        self.assertIn("triggerUserEmail = false", self.code())
        self.assertNotIn("assword", self.code())

    def test_rehearsal_always_throws_last(self):
        self.assertNotIn("throw", self.code())
        self.assertTrue(self.code(True).strip().splitlines()[-1].startswith("throw"))

    def test_quotes_escaped(self):
        self.assertEqual(tu.apex_value("O'N\\x"), "'O\\'N\\\\x'")

    def test_too_big(self):
        plan = tu.make_plan(BASE, ["Specialist"], "Ana P", ORG, IDS, {}, {})
        with self.assertRaises(tu.Stop):
            tu.build_apex(plan * 200, IDS, False)

    def test_rollback_keeps_to_example_com(self):
        self.assertIn("Email LIKE '%@example.com'", tu.rollback_apex(["0051"]))


class Settings(unittest.TestCase):
    def test_other_orgs_kept(self):
        out = json.loads(tu.merged_settings('{"full": {"Specialist": "A"}}', "partial", {"Specialist": "B"}))
        self.assertEqual(out, {"full": {"Specialist": "A"}, "partial": {"Specialist": "B"}})

    def test_part_of_a_set_merges(self):
        out = json.loads(tu.merged_settings('{"p": {"Specialist": "A"}}', "p", {"Supervisor": "B"}))
        self.assertEqual(out["p"], {"Specialist": "A", "Supervisor": "B"})

    def test_bad_file_is_not_overwritten(self):
        with self.assertRaises(tu.Stop):
            tu.merged_settings("{", "p", {})


if __name__ == "__main__":
    unittest.main()
