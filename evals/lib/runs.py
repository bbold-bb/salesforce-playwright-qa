"""Finds each eval run in a claude plugin eval result, and the folder of files that run left behind.

The runner keeps each run's folder when given --keep-temp. The result JSON gives each run's trace path,
<kept>/out/trace.jsonl, and the files the model wrote are at <kept>/sealed/home/cwd. The runner seals that
folder (mode 000) and makes the kept folder read-only, so it's opened before reading and removed after.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunRef:
    case: str
    arm: str  # "with" (skill loaded) or "without"
    index: int
    kept: Path | None  # the run's kept folder, None when the run left none
    runner_score: float
    error: str | None
    direct: Path | None = None  # a workspace the org loop made itself: read in place, never deleted


def load_runs(result_json: Path) -> list[RunRef]:
    data = json.loads(Path(result_json).read_text())
    found: list[RunRef] = []
    for case in data.get("cases", []):
        for arm, arm_runs in case.get("arms", {}).items():
            for i, r in enumerate(arm_runs):
                trace = r.get("tracePath")
                kept = Path(trace).parent.parent if trace else None
                direct = Path(r["workspacePath"]) if r.get("workspacePath") else None
                found.append(RunRef(case=case["name"], arm=arm, index=i, kept=kept,
                                    runner_score=float(r.get("score") or 0), error=r.get("error"), direct=direct))
    return found


def workspace(run: RunRef) -> Path | None:
    """The folder the model worked in, opened for reading; None if the run left no folder."""
    if run.direct is not None:
        return run.direct if run.direct.is_dir() else None
    if run.kept is None or not run.kept.exists():
        return None
    sealed = run.kept / "sealed"
    os.chmod(run.kept, 0o700)
    if sealed.exists():
        os.chmod(sealed, 0o700)
    cwd = sealed / "home" / "cwd"
    return cwd if cwd.is_dir() else None


def cleanup(run: RunRef) -> None:
    if run.kept is None or not run.kept.exists():
        return
    for root, dirs, _ in os.walk(run.kept, topdown=True):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o700)
            except OSError:
                pass
    os.chmod(run.kept, 0o700)
    shutil.rmtree(run.kept, ignore_errors=True)
