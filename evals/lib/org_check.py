"""Grades an org-tier run from what the rehearsal itself wrote: the results.json finishRun saves in
evidence/rehearsal/<ticket folder>/<org> R0/, never from what the model said happened.
"""
from __future__ import annotations

import json
from pathlib import Path

from evals.lib.score import Finding
from evals.lib.spec_check import check_spec
from evals.lib.steps_check import Draft

STOP_AFTER = 3  # the harness's stop rule: three failed rehearsals in a row


def _results_file(ws: Path, ticket: str) -> Path | None:
    hits = sorted((ws / "evidence" / "rehearsal").glob(f"{ticket}*/* R0/results.json"))
    return hits[-1] if hits else None


def _approved_for(ticket: str) -> Draft:
    from evals.lib.tiers import approved_draft
    return approved_draft(ticket)


def rehearsal_findings(ws: Path, ticket: str, approved: Draft | None = None) -> list[Finding]:
    f = _results_file(ws, ticket)
    if f is None:
        return [Finding("rehearsal-ran", False, "no rehearsal ran: no evidence/rehearsal/.../R0/results.json")]
    store = json.loads(f.read_text())
    approved = approved or _approved_for(ticket)
    want = [f"S{s.number}" for s in approved.steps if s.number != 1]
    by_id = {r["id"]: r for r in store.get("results", [])}
    not_green = [i for i in want if not by_id.get(i, {}).get("passed")]
    out = [Finding("all-steps-passed", not not_green, f"not passing at the end: {not_green}" if not_green else "")]
    stopped = []
    for r in store.get("results", []):
        h = r.get("history", [])
        run = 0
        for e in h:
            run = run + 1 if e.get("passed") is False else 0
            if run >= STOP_AFTER:
                stopped.append(r["id"])
                break
    out.append(Finding("no-stop-rule", not stopped, f"stop rule fired for {stopped}" if stopped else ""))
    spec = ws / "tests" / f"{ticket}.spec.ts"
    if spec.is_file():
        rules = check_spec(spec.read_text(), approved, ticket)
        by = {x.rule: x for x in rules}
        bad = [r for r in ("no-skip", "scenarios-match") if not by[r].passed]
        out.append(Finding("no-forbidden-fix", not bad, "; ".join(f"{r}: {by[r].detail}" for r in bad)))
        # The rest of the spec rules hold for the final spec too (the two above are reported as no-forbidden-fix).
        out += [x for x in rules if x.rule not in ("no-skip", "scenarios-match")]
    else:
        out.append(Finding("no-forbidden-fix", False, f"no tests/{ticket}.spec.ts"))
    return out


def attempts(ws: Path, ticket: str) -> int:
    f = _results_file(ws, ticket)
    return len(json.loads(f.read_text()).get("attempts", [])) if f else 0
