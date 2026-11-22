#!/usr/bin/env python3
"""The hard checks: reads a claude plugin eval result, opens each run's folder, checks the files it wrote in code,
and writes one score table.

Usage: python3 evals/check.py <result.json> [--save LABEL] [--keep] [--no-judge]
  --save LABEL  also copy the scores to evals/baselines/<date>-<model>-<LABEL>.{json,md}
  --keep        leave the runs' kept folders in place (they're deleted by default)
  --no-judge    skip the judge (lib/judge.py); runs keep the runner's score alone

The judge reads the run's draft or spec against the case's rubric.md, 3 times, and the majority decides. It counts
as one soft check beside the runner's own; it is skipped for a run that already failed a hard check (that run scores
0 either way). Every vote's reason is saved in hard-checks.json and next to the run's output as judge.md.
Exit 1 when any case scores under 0.67 with the skill loaded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.lib import judge as judge_lib  # noqa: E402
from evals.lib import runs  # noqa: E402
from evals.lib.score import PASS_MARK, Finding, Row, case_table, run_score  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# Case-name prefix -> check(run, workspace) -> findings. Filled in by each tier's module.
HARD_CHECKS: dict[str, Callable[[runs.RunRef, Path], list[Finding]]] = {}
# Case-name prefix -> note(run, workspace) -> text reported in the table, not scored.
NOTES: dict[str, Callable[[runs.RunRef, Path], str]] = {}
# The judge, replaceable in tests.
JUDGE = judge_lib.judge


def _register() -> None:
    # No fallback: if the checks can't load, the report must stop, or every run would keep its runner score unchecked.
    import importlib
    importlib.import_module("evals.lib.tiers").register(HARD_CHECKS, NOTES)


def save_outputs(run: runs.RunRef, ws: Path | None, out_dir: Path) -> None:
    """Copies the run's draft, spec and rehearsal results to <results>/outputs/<case>/<arm>-<n>/ before cleanup."""
    if ws is None:
        return
    from evals.lib.tiers import outputs
    dest = out_dir / "outputs" / run.case / f"{run.arm}-{run.index + 1}"
    for p in outputs(run, ws):
        target = dest / p.relative_to(ws)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, target)


def check_run(run: runs.RunRef) -> tuple[list[Finding], str]:
    prefix = next((p for p in HARD_CHECKS if run.case.startswith(p)), None)
    note_fn = next((fn for p, fn in NOTES.items() if run.case.startswith(p)), None)
    if prefix is None:
        return [], ""
    ws = runs.workspace(run)
    if ws is None:
        return [Finding("output", False, f"no output: {run.error or 'the run left no folder'}")], ""
    try:
        findings = HARD_CHECKS[prefix](run, ws)
    except Exception as e:  # a crashed check fails the run, never the whole report
        findings = [Finding("check-crashed", False, f"{type(e).__name__}: {e}")]
    note = note_fn(run, ws) if note_fn else ""
    return findings, note


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--save")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    a = ap.parse_args(argv)
    _register()
    result = Path(a.result)
    meta = json.loads(result.read_text())
    rows: list[Row] = []
    detail = []
    judge_cost = 0.0
    from evals.lib.tiers import judged_file, rubric
    for run in runs.load_runs(result):
        findings, note = check_run(run)
        if run.error and "timed out" in run.error:
            # Shown in the table so a slow run isn't read as the model getting worse.
            note = "; ".join(x for x in (note, "timed out") if x)
        score = run_score(run.runner_score, findings)
        verdict = None
        ws = runs.workspace(run)
        if not a.no_judge and ws is not None and all(f.passed for f in findings):
            rub, target = rubric(run), judged_file(run, ws)
            if rub and target:
                verdict = JUDGE(rub, target.read_text())
                judge_cost += verdict.cost
                if verdict.passed is None:
                    note = "; ".join(x for x in (note, "judge unavailable") if x)
                else:
                    score = judge_lib.combined(run.runner_score, run.runner_checks, verdict.passed)
        rows.append(Row(case=run.case, arm=run.arm, index=run.index, score=score,
                        failed=[f.rule for f in findings if not f.passed], note=note,
                        judged=None if verdict is None else verdict.passed))  # None too when unavailable
        detail.append({"case": run.case, "arm": run.arm, "run": run.index, "runner_score": run.runner_score,
                       "score": score, "error": run.error, "note": note,
                       "findings": [f.__dict__ for f in findings],
                       "judge": None if verdict is None else {"passed": verdict.passed, "votes": verdict.votes,
                                                              "reasons": verdict.reasons,
                                                              "failed_calls": verdict.failed_calls}})
        save_outputs(run, ws, result.parent)
        if verdict is not None:
            jd = result.parent / "outputs" / run.case / f"{run.arm}-{run.index + 1}" / "judge.md"
            jd.parent.mkdir(parents=True, exist_ok=True)
            head = {True: "PASS", False: "FAIL", None: "unavailable"}[verdict.passed]
            jd.write_text(f"# Judge: {head} ({', '.join(verdict.votes) or 'no votes'})\n\n"
                          + "\n".join(f"- **{v}:** {r}" for v, r in zip(verdict.votes, verdict.reasons))
                          + "".join(f"\n- **Call failed:** {e}" for e in verdict.failed_calls) + "\n")
        if not a.keep:
            runs.cleanup(run)
    model = meta.get("suite", {}).get("modelOverride") or "default-model"
    header = (f"# QA eval scores\n\n- Date: {meta.get('startedAt', '')}\n- Model: {model}\n"
              f"- Claude Code: {meta.get('claudeVersion', '')}\n- Cost: ${meta.get('costUsd', 0):.2f}, plus the judge "
              f"${judge_cost:.2f} ({judge_lib.MODEL})\n"
              f"- Pass mark: {PASS_MARK:.2f} (2 of 3 runs) with the skill loaded; the gap to without the skill is reported only\n\n")
    md = header + case_table(rows)
    out_json = result.parent / "hard-checks.json"
    out_md = result.parent / "scores.md"
    out_json.write_text(json.dumps(detail, indent=1))
    out_md.write_text(md)
    if a.save:
        base = REPO / "evals" / "baselines"
        base.mkdir(exist_ok=True)
        stem = f"{dt.date.today().isoformat()}-{model}-{a.save}"
        shutil.copy(out_json, base / f"{stem}.json")
        shutil.copy(out_md, base / f"{stem}.md")
    print(md)
    with_cases = {r.case for r in rows if r.arm == "with"}
    failing = [c for c in with_cases
               if sum(r.score for r in rows if r.case == c and r.arm == "with")
               / max(1, len([r for r in rows if r.case == c and r.arm == "with"])) < PASS_MARK - 1e-9]
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
