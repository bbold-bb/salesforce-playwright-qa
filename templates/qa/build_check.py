"""Build check: what a Jira build ticket specifies, against what an org has, one row per component and property.

Each row names the metadata type and API name, the property, what the ticket specifies and what the org has, so
anyone can find the component in Setup or a retrieve. Results:

  Match     the org has what the ticket specifies
  Mismatch  it doesn't
  Recorded  the ticket states a behaviour rather than a value (a formula, say), so the org's value is recorded for
            the reader; the behaviour itself is shown by the QA scenarios

It reads a metadata-format retrieve of the org (read-only), plus a field describe or a query through the sf CLI
where a check needs one. It reads metadata, never records, so the output is safe to share with the client. Values are
compared exactly as written and every value list is audited with data_hygiene.py (next to this file): a trailing
space or a curly quote in an org value is a Mismatch, even when the value looks right on screen.

  python3 build_check.py PROJ-21 --retrieve <folder that holds package.xml> [--org my-partial-sandbox] [--verified "..."]

The org comes from --org, else the SF_ORG environment variable, else DEFAULT_ORG below. Output goes next to this
file: <ticket>-build-check-<date>.md and the same rows as .json.

What each check retrieves is in CHECKS. The worked example, PROJ-21, needs StandardValueSet:CaseOrigin and
StandardValueSet:CaseStatus, and runs in any org on standard metadata. For example:

  sf project retrieve start --metadata StandardValueSet:CaseOrigin StandardValueSet:CaseStatus \\
      --target-metadata-dir build-check-retrieve --unzip --target-org my-partial-sandbox

Then pass --retrieve the folder inside build-check-retrieve that holds package.xml and standardValueSets/.

Adding a check for a new ticket (see README.md for more):
  1. Read the build sub-task's spec and write down, per component, the properties it fixes and their values.
  2. Write a function check_<ticket>(c, R) that reads the retrieve under R and calls c.row() for single values and
     c.values() for value lists. Put the expected values in a SPEC constant above the function, quoting the ticket's
     wording exactly, and say in the docstring which ticket it checks and the date you read it.
  3. Add the ticket to CHECKS with the spec ticket, a title, the function and a one-line description of the source.
  4. Retrieve what it needs, run it, and read every Mismatch before believing it: some are the check, not the build.
"""
import argparse, datetime, json, os, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from data_hygiene import audit  # noqa: E402

# ---- Project settings: change these for your project --------------------------------------------------------------
DEFAULT_ORG = "my-partial-sandbox"   # sf CLI alias of the org QA runs in; --org or SF_ORG overrides it
# -------------------------------------------------------------------------------------------------------------------

NS = {"m": "http://soap.sforce.com/2006/04/metadata"}


def t(el, tag):
    """The text of a child element, or None. Values come back exactly as the org wrote them, spaces included."""
    x = el.find(f"m:{tag}", NS)
    return x.text if x is not None and x.text is not None else None


def sf(args, org):
    """Runs a read-only sf CLI command and returns its JSON result."""
    out = subprocess.run(["sf", *args, "-o", org, "--json"], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["result"]


class Check:
    def __init__(self, ticket, spec_ticket, org):
        self.ticket, self.spec_ticket, self.org = ticket, spec_ticket, org
        self.rows = []

    def row(self, mtype, api, prop, expected, actual, result=None, note=""):
        """One property. Compared exactly (no trimming, no case folding) unless you pass result="Recorded"."""
        if result is None:
            result = "Match" if expected == actual else "Mismatch"
        self.rows.append(dict(type=mtype, api=api, property=prop, expected=expected, actual=actual, result=result, note=note))

    def values(self, mtype, api, prop, expected, actual, note=""):
        """A value list, compared as a set (the ticket doesn't fix the order); the org's order is shown. Any hygiene
        flag on the org's values makes it a Mismatch and is named in the note."""
        issues = audit(actual, f"{mtype} {api} {prop}")
        if issues:
            note = "; ".join(filter(None, [note, "hygiene flags: " + "; ".join(str(i) for i in issues)]))
        ok = sorted(expected) == sorted(actual) and not issues
        self.rows.append(dict(type=mtype, api=api, property=prop, expected=", ".join(expected),
                              actual=", ".join(actual), result="Match" if ok else "Mismatch", note=note))

    def write(self, path, header):
        compared = [r for r in self.rows if r["result"] != "Recorded"]
        matched = [r for r in compared if r["result"] == "Match"]
        recorded = [r for r in self.rows if r["result"] == "Recorded"]
        cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
        lines = [*header,
                 f"- **Result:** {len(matched)} of {len(compared)} compared properties match. "
                 f"{len(recorded)} recorded, where the ticket states a behaviour rather than a value.", "",
                 "| Metadata type | API name | Property | Expected | Actual | Result | Note |",
                 "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in self.rows:
            lines.append("| " + " | ".join(cell(r[k]) for k in ("type", "api", "property", "expected", "actual", "result", "note")) + " |")
        path.write_text("\n".join(lines) + "\n")
        with open(path.with_suffix(".json"), "w") as f:
            json.dump(self.rows, f, indent=1)
        return len(matched), len(compared), len(recorded)


def active_values(svs):
    """(fullName, isActive) for each value in a StandardValueSet or a picklist's value set definition."""
    return [(t(v, "fullName"), t(v, "isActive")) for v in svs.findall("m:standardValue", NS)]


# ---- The worked example ------------------------------------------------------------------------------------------
# A build sub-task (PROJ-20 here) says: "Case Origin offers Phone, Email and Web. Case Status offers New, Working,
# Escalated and Closed, and only Closed closes a case. The retired value Web Form is no longer offered."
# These are Salesforce's own defaults plus one value that should be absent, so the check runs in a fresh org.
# For a formula or a rule's condition, record the org's text with result="Recorded" (collapse its whitespace with
# re.sub(r"\s+", " ", text) so the table stays readable) and let a QA scenario show the behaviour.

SPEC_PROJ_21 = {
    "origin_values": ["Phone", "Email", "Web"],
    "origin_removed": ["Web Form"],
    "status_values": ["New", "Working", "Escalated", "Closed"],
    "status_closed": ["Closed"],
}


def check_proj_21(c, R):
    """PROJ-20, Case Origin and Status values, as read 2026-01-05. Replace with your own ticket."""
    s = SPEC_PROJ_21

    # Case Origin: the value set's active values, compared as a list.
    origin = active_values(ET.parse(R / "standardValueSets/CaseOrigin.standardValueSet").getroot())
    c.values("StandardValueSet", "CaseOrigin", "Active values", s["origin_values"], [n for n, a in origin if a != "false"])

    # A removed value: check both the value set and the field describe. A value deleted from the set can still be
    # offered by the describe, and records that already hold it keep it either way, so say so in the note.
    describe = [f for f in sf(["sobject", "describe", "-s", "Case"], c.org)["fields"] if f["name"] == "Origin"][0]
    offered = [v["value"] for v in describe["picklistValues"] if v["active"]]
    in_set = dict(origin)
    for old in s["origin_removed"]:
        still = old in offered or (old in in_set and in_set[old] != "false")
        c.row("StandardValueSet", "CaseOrigin", f"{old} offered", "No", "Yes" if still else "No",
              note="Not in the value set or the field describe. Records that already hold it keep it."
              if old not in in_set and old not in offered else "")

    # Case Status: the values, then a property of each value (closed), then a Recorded row.
    status_root = ET.parse(R / "standardValueSets/CaseStatus.standardValueSet").getroot()
    status = status_root.findall("m:standardValue", NS)
    c.values("StandardValueSet", "CaseStatus", "Active values", s["status_values"],
             [t(v, "fullName") for v in status if t(v, "isActive") != "false"])
    c.values("StandardValueSet", "CaseStatus", "Values that close a case", s["status_closed"],
             [t(v, "fullName") for v in status if t(v, "closed") == "true"])
    default = [t(v, "fullName") for v in status if t(v, "default") == "true"]
    c.row("StandardValueSet", "CaseStatus", "Default value", "The ticket doesn't set one; a QA scenario checks a new case starts at it",
          ", ".join(default) or "None", "Recorded", "Shown by QA scenario S1")


CHECKS = {
    # ticket: (spec ticket, title, function, what it reads)
    "PROJ-21": ("PROJ-20", "Case Origin and Status values", check_proj_21,
                "a read-only retrieve of the CaseOrigin and CaseStatus value sets and the Case field describe"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ticket", choices=sorted(CHECKS))
    ap.add_argument("--retrieve", required=True, type=Path, help="The retrieve folder that holds package.xml")
    ap.add_argument("--org", default=os.environ.get("SF_ORG", DEFAULT_ORG), help="sf CLI org alias (default: SF_ORG, else %(default)s)")
    ap.add_argument("--verified", default="not yet independently recomputed; don't quote its figures until it is",
                    help='The numbers-gate line, once an independent recompute matches, e.g. "figures verified 2026-01-05 by independent recompute"')
    a = ap.parse_args()
    if not (a.retrieve / "package.xml").exists():
        raise SystemExit(f"No package.xml in {a.retrieve}. Pass the retrieve folder that holds package.xml and the metadata folders.")
    spec, title, fn, source = CHECKS[a.ticket]
    c = Check(a.ticket, spec, a.org)
    fn(c, a.retrieve)
    org_id = sf(["org", "display"], a.org)["id"]
    today = datetime.date.today().isoformat()
    out = HERE / f"{a.ticket}-build-check-{today}.md"
    header = [f"# {a.ticket} build check: {title}", "",
              f"What {spec} specifies, against what {a.org} has: one row per metadata component and property.", "",
              f"- **Org:** {a.org}, org ID {org_id}",
              f"- **Checked:** {today}, from {source}. Nothing in the org was changed.",
              f"- **Spec:** {spec}, as read {today}.",
              f"- **Verified:** {a.verified}."]
    m, n, r = c.write(out, header)
    print(f"{out.name}: {m} of {n} compared properties match, {r} recorded")
    for row in c.rows:
        if row["result"] == "Mismatch":
            print("  MISMATCH", row["type"], row["api"], row["property"], "| expected", row["expected"], "| actual", row["actual"], "|", row["note"])


if __name__ == "__main__":
    main()
