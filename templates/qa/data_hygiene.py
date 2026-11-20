"""Data hygiene for every count you publish: read data as it really is, and flag values that won't match.

Three failure modes keep producing wrong numbers on migration and QA work:

1. Source values with stray characters, compared exactly. A legacy system stores "Pending Review " with a trailing
   space, "Awaiting  Reply" with a double space, or "On Hold\u2013Customer" with an en dash. An exact match
   against the clean name finds nothing, so a value that is used reads as unused.
2. Readers that change values on the way in. pandas turns the strings "None", "N/A", "NA", "NULL" and "nan" into
   missing values by default, so a real picklist value "None" counts as 0. Polars infers types
   from the first rows unless told not to.
3. Helpers that treat a real value as blank (a check like `str(v) in ("", "nan", "None")`).

Use this module for any script that loads values from a source system, Salesforce, a workbook or a CSV and counts,
matches or publishes them:

- read with `read_csv_polars` or `read_csv_pandas`, which keep every value as text, exactly as written;
- compare with `canon()` as the matching key, and keep the original value for display and for building;
- run `audit()` on each list of values a script loads, and `match()` when comparing two lists (source against
  target, a legacy list against a story's list). `require_clean()` stops the script on anything not explained in
  `allow`. Keep the explained values in value_quirks.py, next to this file, each with its reason.

Two more traps the audit can't see for you:

- SOQL compares text case-insensitively (WHERE Name = 'phone' finds "Phone"); Python doesn't. A count that agrees
  in the org and disagrees in a script is often this. Match on `canon()` in Python, or say which you used.
- Salesforce IDs come in 15 and 18 characters. The 15-character form is case-sensitive, so mixing the two in a join
  silently drops or mismatches rows. Convert every ID to 18 characters before you join or compare.

Command line:  python3 data_hygiene.py audit FILE.csv --column value [--group list]
               python3 data_hygiene.py selftest
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Strings pandas reads as missing by default. Several are real values in Salesforce picklists and source systems.
NA_LIKE = {"", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>",
           "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"}
# Hyphen, non-breaking hyphen, figure dash, en dash, the long dash, horizontal bar, minus sign. Written as escapes
# so the file itself holds none of them.
DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
# Curly single and double quotes, and their plain forms.
QUOTES = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
# Non-breaking space, figure space, narrow non-breaking space, zero-width space, byte order mark.
ODD_SPACES = "\u00a0\u2007\u202f\u200b\ufeff"


def canon(value: object) -> str:
    """The matching key: Unicode-normalized, dashes and quotes made plain, spaces trimmed and collapsed, case folded.
    Use it only to decide whether two values are the same. Display and build with the original."""
    s = unicodedata.normalize("NFKC", "" if value is None else str(value))
    for ch in DASHES:
        s = s.replace(ch, "-")
    for k, v in QUOTES.items():
        s = s.replace(k, v)
    for ch in ODD_SPACES:
        s = s.replace(ch, " ")
    return re.sub(r"\s+", " ", s).strip().casefold()


@dataclass
class Issue:
    kind: str
    value: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.kind}: {self.value!r}" + (f" ({self.detail})" if self.detail else "")


def audit(values: Iterable[object], label: str = "") -> list[Issue]:
    """Flag every value that would break an exact match or a naive reader. Nulls are skipped."""
    issues: list[Issue] = []
    groups: dict[str, set[str]] = defaultdict(set)
    for v in dict.fromkeys(str(x) for x in values if x is not None):  # each distinct value once, in order
        if v != v.strip():
            issues.append(Issue("leading or trailing space", v))
        if "  " in v.strip():
            issues.append(Issue("double space", v))
        if any(ch in v for ch in DASHES):
            issues.append(Issue("non-standard dash", v))
        if any(ch in v for ch in QUOTES):
            issues.append(Issue("curly quote", v))
        if any(ch in v for ch in ODD_SPACES) or "\t" in v or "\n" in v:
            issues.append(Issue("hidden or odd whitespace", v))
        if v.strip() in NA_LIKE and v.strip():
            issues.append(Issue("value a reader may take for missing", v, "keep it as text"))
        groups[canon(v)].add(v)
    for key, members in groups.items():
        if len(members) > 1:
            issues.append(Issue("values that differ only in spacing, dashes, quotes or case", " | ".join(sorted(members))))
    if label:
        for i in issues:
            i.detail = f"{label}; {i.detail}" if i.detail else label
    return issues


@dataclass
class MatchReport:
    exact: list[str] = field(default_factory=list)
    by_alias: list[tuple[str, str]] = field(default_factory=list)
    canonical_only: list[tuple[str, str]] = field(default_factory=list)
    source_unmatched: list[str] = field(default_factory=list)
    target_unmatched: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"exact {len(self.exact)}, by alias {len(self.by_alias)}, after cleanup only {len(self.canonical_only)}, "
               f"source unmatched {len(self.source_unmatched)}, target unmatched {len(self.target_unmatched)}"]
        out += [f"  after cleanup only: {s!r} -> {t!r}" for s, t in self.canonical_only]
        out += [f"  source unmatched: {s!r}" for s in self.source_unmatched]
        out += [f"  target unmatched: {t!r}" for t in self.target_unmatched]
        return out


def match(source: Iterable[object], target: Iterable[object], aliases: dict[str, str] | None = None) -> MatchReport:
    """Compare source values (a legacy system, a data file) with target values (a story's list, Salesforce).
    `aliases` maps a source value to its target value for known spelling variants, each one deliberate.
    A pair that matches only after cleanup is reported, so the script owner decides rather than the code."""
    aliases = aliases or {}
    src = sorted({str(v) for v in source if v is not None})
    tgt = sorted({str(v) for v in target if v is not None})
    tgt_exact, tgt_canon = set(tgt), {canon(t): t for t in tgt}
    rep, hit = MatchReport(), set()
    for s in src:
        if s in tgt_exact:
            rep.exact.append(s); hit.add(s)
        elif s in aliases and aliases[s] in tgt_exact:
            rep.by_alias.append((s, aliases[s])); hit.add(aliases[s])
        elif canon(s) in tgt_canon:
            rep.canonical_only.append((s, tgt_canon[canon(s)])); hit.add(tgt_canon[canon(s)])
        else:
            rep.source_unmatched.append(s)
    rep.target_unmatched = [t for t in tgt if t not in hit]
    return rep


class HygieneError(RuntimeError):
    pass


def require_clean(issues: list[Issue], allow: dict[str, str] | None = None) -> list[Issue]:
    """Stop on any issue whose value isn't in `allow` (value -> the reason it's acceptable). Returns what was allowed,
    so the script can print it. Every entry in `allow` should name the source and why it's fine. Keep the project's
    entries in value_quirks.py (VALUE_ALLOW) and pass that in."""
    allow = allow or {}
    bad = [i for i in issues if i.value not in allow]  # exact values only, so allowing "None" can't cover more
    if bad:
        raise HygieneError("Unexplained data issues:\n  " + "\n  ".join(map(str, bad)))
    return [i for i in issues if i not in bad]


def read_csv_polars(path: str | Path, **kw):
    """Every column as text, exactly as written: no type guessing, and only truly empty fields are null."""
    import polars as pl
    return pl.read_csv(path, infer_schema_length=0, null_values=None, **kw)


def read_csv_pandas(path: str | Path, **kw):
    """Every column as text, exactly as written: "None", "N/A" and "NULL" stay strings. Use it only when a library
    needs a pandas DataFrame; Polars is the default."""
    import pandas as pd
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, **kw)


def _selftest() -> None:
    assert canon("Pending Review ") == canon("Pending Review")
    assert canon("Awaiting  Reply") == canon("Awaiting Reply")
    assert canon("On Hold\u2013Customer") == canon("On Hold-Customer")
    kinds = {i.kind for i in audit(["Blue ", "Blue", "None", "Zone \u2013 A"])}
    assert {"leading or trailing space", "values that differ only in spacing, dashes, quotes or case",
            "value a reader may take for missing", "non-standard dash"} <= kinds, kinds
    r = match(["Recieved/Logged", "Pending Review ", "Other", "Retired"],
              ["Received/Logged", "Pending Review", "Other", "Never used"],
              aliases={"Recieved/Logged": "Received/Logged"})
    assert r.exact == ["Other"] and r.by_alias and r.canonical_only == [("Pending Review ", "Pending Review")]
    assert r.source_unmatched == ["Retired"] and r.target_unmatched == ["Never used"]
    try:
        require_clean(audit(["Blue "]))
        raise AssertionError("require_clean should have stopped")
    except HygieneError:
        pass
    assert require_clean(audit(["Blue "]), {"Blue ": "Trailing space in the source; built as Blue"})
    print("selftest ok")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="audit one column of a CSV, optionally per group")
    a.add_argument("file")
    a.add_argument("--column", required=True)
    a.add_argument("--group")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "selftest":
        _selftest()
        return 0
    import csv
    # The csv module reads every value as text, exactly as written, so nothing here is type-guessed.
    rows = list(csv.DictReader(open(args.file, newline="", encoding="utf-8")))
    groups: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        groups[r.get(args.group, "") if args.group else ""].append(r[args.column])
    total = 0
    for g, vals in sorted(groups.items()):
        for i in audit(vals, g):
            print(i)
            total += 1
    print(f"{total} issue(s) in {len(rows)} rows")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
