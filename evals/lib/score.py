"""Combines the runner's score with the hard checks, and writes the score table."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

PASS_MARK = 2 / 3  # a case passes when it holds on 2 of its 3 runs


@dataclass
class Finding:
    rule: str
    passed: bool
    detail: str


@dataclass
class Row:
    case: str
    arm: str
    index: int
    score: float
    failed: list[str] = field(default_factory=list)  # hard rules this run failed
    note: str = ""  # reported, not scored (for example, rehearsal attempts)
    judged: bool | None = None  # the judge's verdict, None when it didn't run


def run_score(runner_score: float, findings: list[Finding]) -> float:
    """A run with any failed hard check scores 0; otherwise it keeps the runner's score."""
    return 0.0 if any(not f.passed for f in findings) else runner_score


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def case_table(rows: list[Row]) -> str:
    by = defaultdict(list)
    for r in rows:
        by[(r.case, r.arm)].append(r)
    cases = sorted({r.case for r in rows})
    out = [
        "| Case | Runs | Score with skill | Passed (0.67) | Score without | Gap | Hard rules failed | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in cases:
        w = by.get((c, "with"), [])
        wo = by.get((c, "without"), [])
        ws = _mean([r.score for r in w])
        wos = f"{_mean([r.score for r in wo]):.2f}" if wo else "n/a"
        gap = f"{ws - _mean([r.score for r in wo]):+.2f}" if wo else "n/a"
        failed = sorted({f for r in w for f in r.failed})
        flags = ("timed out", "judge unavailable")
        counts = {f: sum(1 for r in w if f in r.note) for f in flags}

        def rest(n: str) -> str:
            for f in flags:
                n = n.replace(f, "")
            return n.strip("; ").strip()
        notes = "; ".join([rest(r.note) for r in w if rest(r.note)]
                          + [f"{n} {f}" for f, n in counts.items() if n])
        judged = [r.judged for r in w if r.judged is not None]
        if judged:
            notes = "; ".join(x for x in (notes, f"judge passed {sum(judged)} of {len(judged)}") if x)
        out.append(f"| {c} | {len(w)} | {ws:.2f} | {'yes' if ws >= PASS_MARK - 1e-9 else 'no'} | {wos} | {gap} | "
                   f"{', '.join(failed) or 'none'} | {notes} |")
    return "\n".join(out) + "\n"
