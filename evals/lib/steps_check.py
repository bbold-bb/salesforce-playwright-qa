"""Reads a QA sub-task's Test Steps, written in the kit's template format (docs/writing-test-steps.md), and checks
them against a fixture's answer key.

Shapes it reads, case-insensitively and with markdown decoration (#, *, -) allowed:
  "<n>. <text> [<Tag>]"           a step; the tag may sit on a following indented line
  "Flow F<n>, as <user>"          starts a flow; a blank line ends it
  "Coverage"                      the heading, then "- Criterion <n>: <text>" bullets
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from evals.lib.score import Finding

TAGS = ["Build check", "Query", "Screenshot", "Video"]
_TAG_RE = re.compile(r"\[(build check|query|screenshot|video)\]", re.I)
_STEP_RE = re.compile(r"^\W{0,4}(\d+)\.\s+(.*)$")
_FLOW_RE = re.compile(r"^\W*flow\s+(F\d+)\b\s*[,:-]?\s*(?:as\s+)?(.*?)[\W]*$", re.I)
_COVERAGE_RE = re.compile(r"^\W*coverage\W*$", re.I)
_CRIT_RE = re.compile(r"\b(?:criterion|criteria|ACs?)\b\s*:?\s*((?:\d+(?:\s*(?:,\s*and|,|and|&|/)\s*)?)+)", re.I)
_BULLET_RE = re.compile(r"^\s*[-*]\s*(?:\*\*)?\s*((?:criterion|criteria|ACs?)\b\s*(?:\d+(?:\s*(?:,\s*and|,|and|&|/)\s*)?)+)"
                        r"\s*(?:\([^)]*\))?\s*(?:\*\*)?\s*[:.)-]\s*(.*)$", re.I)
_TICKET_RE = r"\b{}\b"


@dataclass
class Step:
    number: int
    flow: str | None
    user: str | None
    criteria: list[int]
    tag: str  # the first tag, "" when none
    tags: list[str] = field(default_factory=list)
    text: str = ""


@dataclass
class Draft:
    steps: list[Step]
    coverage: dict[int, str]
    flows: dict[str, str]  # flow id -> the user it runs as


def _canon_tag(t: str) -> str:
    return next(x for x in TAGS if x.lower() == t.lower())


def _criteria(text: str) -> list[int]:
    found: set[int] = set()
    for m in _CRIT_RE.finditer(text):
        found.update(int(n) for n in re.findall(r"\d+", m.group(1)))
    return sorted(found)


def parse_steps(text: str) -> Draft:
    steps: list[Step] = []
    coverage: dict[int, str] = {}
    flows: dict[str, str] = {}
    flow: str | None = None
    in_coverage = False
    cur: list[str] | None = None
    cur_meta: tuple[int, str | None] | None = None

    def close() -> None:
        nonlocal cur, cur_meta
        if cur is not None and cur_meta is not None:
            body = " ".join(cur)
            tags = [_canon_tag(t) for t in _TAG_RE.findall(body)]
            n, fl = cur_meta
            steps.append(Step(number=n, flow=fl, user=flows.get(fl) if fl else None, criteria=_criteria(body),
                              tag=tags[0] if tags else "", tags=tags, text=body))
        cur, cur_meta = None, None

    for raw in text.splitlines():
        line = raw.rstrip()
        if in_coverage:
            m = _BULLET_RE.match(line)
            if m:
                for n in re.findall(r"\d+", m.group(1)):
                    coverage[int(n)] = m.group(2).strip()
            continue
        if _COVERAGE_RE.match(line):
            close()
            in_coverage = True
            continue
        if not line.strip():
            close()
            flow = None
            continue
        fm = _FLOW_RE.match(line)
        if fm and not _STEP_RE.match(line):
            close()
            flow = fm.group(1).upper()
            user = re.sub(r"\s*\([^)]*\)?\s*$", "", fm.group(2).strip())  # "(Standard User)" and the like
            flows[flow] = re.sub(r"^the\s+", "", user, flags=re.I).strip()
            continue
        sm = _STEP_RE.match(line)
        if sm:
            close()
            cur = [sm.group(2)]
            cur_meta = (int(sm.group(1)), flow)
            continue
        if cur is not None:
            cur.append(line.strip())
    close()
    return Draft(steps=steps, coverage=coverage, flows=flows)


def _step_text_after_build_check(draft: Draft) -> str:
    return " ".join(s.text for s in draft.steps if s.number != 1)


def check_steps(draft: Draft, key: dict, text: str) -> list[Finding]:
    out: list[Finding] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        out.append(Finding(rule, ok, detail))

    first = draft.steps[0] if draft.steps else None
    add("build-check-first", bool(first and first.number == 1 and first.tag == "Build check"),
        "" if first else "no steps found")

    untagged = [s.number for s in draft.steps if len(s.tags) != 1]
    add("step-has-tag", not untagged, f"steps without exactly one tag: {untagged}" if untagged else "")

    no_crit = [s.number for s in draft.steps if s.number != 1 and not s.criteria]
    add("step-has-criterion", not no_crit, f"steps naming no criterion: {no_crit}" if no_crit else "")

    key_crit = {int(k): v for k, v in key["criteria"].items()}
    missing = sorted(set(key_crit) - set(draft.coverage))
    extra = sorted(set(draft.coverage) - set(key_crit))
    add("coverage-complete", not missing, f"criteria missing from Coverage: {missing}" if missing else "")
    add("coverage-no-extra", not extra, f"Coverage names criteria the story doesn't have: {extra}" if extra else "")

    tag_problems = []
    other_problems = []
    for c, spec in sorted(key_crit.items()):
        proving = [s for s in draft.steps if c in s.criteria]
        if spec["where"] == "other":
            cov = draft.coverage.get(c, "")
            if not re.search(_TICKET_RE.format(re.escape(spec["other"])), cov, re.I):
                other_problems.append(f"criterion {c}: Coverage doesn't name {spec['other']}")
            if proving:
                other_problems.append(f"criterion {c}: tested here by step(s) {[s.number for s in proving]}")
            continue
        allowed = set(spec["tags"])
        if any(s.number != 1 and s.tag in allowed for s in proving):
            continue
        cov = draft.coverage.get(c, "").lower()
        build_ok = first is not None and first.tag == "Build check"
        if "Build check" in allowed and build_ok and ("build check" in cov or re.search(r"\bstep 1\b", cov)):
            continue
        got = sorted({s.tag or "untagged" for s in proving if s.number != 1})
        tag_problems.append(f"criterion {c}: no step proves it with one of {sorted(allowed)}"
                            + (f" (found {got})" if got else ""))
    add("tag-matches-key", not tag_problems, "; ".join(tag_problems))

    allowed_users = {u.lower() for u in key["users"]}
    bad_users = sorted({u for u in draft.flows.values() if u.lower() not in allowed_users})
    add("allowed-users", not bad_users, f"flows run as users the story doesn't need: {bad_users}" if bad_users else "")

    scope = _step_text_after_build_check(draft) + " " + " ".join(draft.coverage.values())
    hits = [w for w in key.get("forbidden", []) if re.search(r"\b" + re.escape(w) + r"\b", scope, re.I)]
    add("forbidden-absent", not hits, f"found outside the build check: {hits}" if hits else "")

    add("other-ticket-named", not other_problems, "; ".join(other_problems))

    n_flows = len(draft.flows)
    add("max-flows", n_flows <= key["max_flows"],
        f"{n_flows} flows, the story needs at most {key['max_flows']}" if n_flows > key["max_flows"] else "")
    return out
