"""Each tier's hard check, registered with check.py by case-name prefix.

Answer keys and approved Test Steps are always read from the repo's fixtures, never from the run's folder,
so nothing the model writes there can change how it's graded.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from evals.lib.runs import RunRef
from evals.lib.score import Finding
from evals.lib.spec_check import check_spec, compile_check
from evals.lib.steps_check import check_steps, parse_steps

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "acme-support"


def ticket_of(case: str) -> str:
    """'steps-ACME-11' -> 'ACME-11'."""
    return case.split("-", 1)[1]


def load_key(ticket: str) -> dict:
    return json.loads((FIX / "keys" / f"{ticket}.json").read_text())


def check_steps_run(run: RunRef, ws: Path) -> list[Finding]:
    ticket = ticket_of(run.case)
    draft_file = ws / "qa-steps" / f"{ticket}.md"
    if not draft_file.is_file():
        return [Finding("output-file", False, f"no qa-steps/{ticket}.md")]
    text = draft_file.read_text()
    return check_steps(parse_steps(text), load_key(ticket), text)


def approved_draft(ticket: str):
    return parse_steps((FIX / "approved" / f"{ticket}.md").read_text())


def check_spec_run(run: RunRef, ws: Path) -> list[Finding]:
    """The spec rules, then tsc and playwright test --list, in the run's copy of the harness."""
    ticket = ticket_of(run.case)
    spec = ws / "tests" / f"{ticket}.spec.ts"
    if not spec.is_file():
        return [Finding("output-file", False, f"no tests/{ticket}.spec.ts")]
    approved = approved_draft(ticket)
    return check_spec(spec.read_text(), approved, ticket) + compile_check(ws, ticket, approved)


def check_org_run(run: RunRef, ws: Path) -> list[Finding]:
    from evals.lib.org_check import rehearsal_findings
    return rehearsal_findings(ws, ticket_of(run.case))


def org_note(run: RunRef, ws: Path) -> str:
    from evals.lib.org_check import attempts
    n = attempts(ws, ticket_of(run.case))
    return f"{n} rehearsal attempt{'' if n == 1 else 's'}"


def outputs(run: RunRef, ws: Path) -> list[Path]:
    """The files a run produced that a person may want to read: the draft, the spec, a rehearsal's results, and in
    the org tier Claude's own final message."""
    t = ticket_of(run.case)
    found = [p for p in (ws / "qa-steps" / f"{t}.md", ws / "tests" / f"{t}.spec.ts") if p.is_file()]
    found += sorted((ws / "evidence" / "rehearsal").glob(f"{t}*/* R0/results.json"))
    found += [p for p in (ws / "claude.json",) if p.is_file()]  # the org loop's final message, cost and turns
    return found


def register(checks: dict[str, Callable], notes: dict[str, Callable]) -> None:
    checks["steps-"] = check_steps_run
    checks["spec-"] = check_spec_run
    checks["org-"] = check_org_run
    notes["org-"] = org_note
