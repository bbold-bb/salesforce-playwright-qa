"""The QA ledger: where its files live, their columns, and how rows are added.

An optional add-on to the QA harness: copy this folder to <qa folder>/ledger/ and run the Playwright specs with
QA_LEDGER=1 (see README.md). Four CSV files in evidence/qa-ledger/ (gitignore it, and keep it on this machine: it holds
your team's cost figures, and the Drive evidence folder may be shared with the client):

- scenarios.csv       one row per scenario defined, per QA sub-task
- scenario-runs.csv   one row per scenario, each time it runs
- sessions.csv        one row per block of QA work: tokens, cost and agent minutes
- jira-items.csv      a read-only snapshot of the Jira items involved: type, parent, epic, sprint

Every value is text, written and read exactly as is (data_hygiene.read_csv_polars), so a run ID like "0012" or a
result like "None" is never turned into a number or a blank.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

QA_DIR = Path(__file__).resolve().parent.parent
# The same evidence folder the Playwright harness writes to (QA_EVIDENCE_DIR overrides it there and here).
EVIDENCE = Path(os.environ["QA_EVIDENCE_DIR"]) if os.environ.get("QA_EVIDENCE_DIR") else QA_DIR / "evidence"
LEDGER = EVIDENCE / "qa-ledger"
sys.path.insert(0, str(QA_DIR))  # so the ledger scripts can import data_hygiene from the qa folder

COLUMNS = {
    "scenarios.csv": ["qa_subtask", "scenario", "title", "expected", "evidence", "source"],
    "scenario-runs.csv": [
        "run_id", "started_local", "qa_subtask", "scenario", "round", "attempt", "reason", "note", "method", "org",
        "sprint", "result", "seconds", "run_folder",
    ],
    "sessions.csv": [
        "entry_id", "session_id", "started_local", "ended_local", "kind", "method", "qa_subtasks", "run_ids", "model",
        "calls", "agent_minutes", "new_tokens", "cache_read_tokens", "cost_usd", "note",
    ],
    "jira-items.csv": [
        "key", "type", "title", "status", "parent", "epic", "epic_title", "sprint", "sprints", "updated",
        "snapshot_local",
    ],
}

# Why a run happened. A new round means something under test changed; a new attempt within a round
# means it didn't (the script was fixed, the approved Test Steps changed, or a step was flaky). Keep these lists the
# same as ROUND_REASONS and ATTEMPT_REASONS in playwright/lib/evidence.ts.
ROUND_REASONS = {
    "first-run": "The first round for this QA sub-task in this org",
    "retest-after-fix": "A failure reopened the build sub-task and the build was fixed",
    "story-changed": "The story, its acceptance criteria or its Test Steps changed",
    "regression-after-deployment": "A deployment touched what the story built",
}
ATTEMPT_REASONS = {
    "script-fix": "The test script was fixed; nothing under test changed",
    "steps-changed": "The approved Test Steps changed and the script followed them; the build didn't change",
    "flaky": "A step failed for a reason outside the build (timing, session); nothing changed",
    "tooling-check": "A check that the QA tooling still works after it changed; nothing under test changed",
}
# A practice run of a script before its recorded run: round R0, no video, its own folder under evidence/rehearsal/.
OTHER_REASONS = {
    "rehearsal": "A practice run of a script before its recorded run: round R0, no video, its own folder",
}
# Runs kept in the ledger and the evidence but left out of the report's figures, since they tested the QA
# tooling or practised a script rather than testing the build. Without this, every change to the runner and every
# rehearsal inflates the cost per scenario.
LEFT_OUT_REASONS = {"tooling-check", "rehearsal"}
METHODS = {"playwright", "browser-tool", "by-hand"}
KINDS = {
    "setup": "One-time tooling setup, not tied to a story",
    "scripting": "Writing a story's scenarios as a script",
    "run": "Running scenarios and reading the result",
    "fix": "Fixing a failed script or scenario, and rerunning",
    "review": "Reviewing evidence and drafting the Testing Feedback",
    "build-check": "Running and reviewing a build check",
    "reporting": "Write-ups and figures about the QA",
}


def path(name: str) -> Path:
    return LEDGER / name


def ensure(name: str) -> Path:
    """Creates the ledger file with its header if it doesn't exist yet."""
    p = path(name)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUMNS[name])
    return p


def read_rows(name: str) -> list[dict[str, str]]:
    p = path(name)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append(name: str, rows: list[dict[str, str]]) -> None:
    p = ensure(name)
    cols = COLUMNS[name]
    for r in rows:
        extra = set(r) - set(cols)
        if extra:
            raise ValueError(f"{name}: unknown columns {sorted(extra)}")
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def write_all(name: str, rows: list[dict[str, str]]) -> None:
    """Replaces the file. Used for the Jira snapshot, which is a copy of Jira, and by session_cost.py --reprice,
    which measures recorded rows again after a price change."""
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    cols = COLUMNS[name]
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
