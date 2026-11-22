"""The judge: a model reads one file a run wrote against the case's rubric (rubric.md beside its case.yaml) and says
PASS or FAIL with a reason. It runs in check.py rather than in claude plugin eval, so every vote's reason is kept with
the scores. Each run is judged several times (3 by default) and the majority decides.

Headless Claude, with your own settings, CLAUDE.md and MCP servers left out, no tools, and a fixed answer shape.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable

MODEL = os.environ.get("QA_EVALS_JUDGE", "sonnet")
VOTES = int(os.environ.get("QA_EVALS_JUDGE_VOTES", "3"))
_SCHEMA = json.dumps({"type": "object", "required": ["verdict", "reason"], "properties": {
    "verdict": {"type": "string", "enum": ["PASS", "FAIL"]}, "reason": {"type": "string"}}})


@dataclass
class Verdict:
    passed: bool | None  # None: no call returned a verdict, so the judge is unavailable for this run
    votes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    cost: float = 0.0
    failed_calls: list[str] = field(default_factory=list)


def prompt_for(rubric: str, content: str) -> str:
    return (f"You are grading one file against a rubric. Read the whole file before deciding.\n\n"
            f"Rubric:\n{rubric.strip()}\n\nFile:\n<<<FILE\n{content}\nFILE>>>\n\n"
            "Give PASS or FAIL, and the reason in two or three sentences, naming the step or line it turns on.")


def ask_claude(prompt: str, model: str) -> tuple[str, str, float]:
    out = subprocess.run(
        [shutil.which("claude") or "claude", "-p", prompt, "--model", model, "--setting-sources", "", "--strict-mcp-config", "--tools", "",
         "--no-session-persistence", "--output-format", "json", "--json-schema", _SCHEMA],
        capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    d = json.loads(out.stdout)
    s = d.get("structured_output") or {}
    if d.get("is_error") or s.get("verdict") not in ("PASS", "FAIL"):
        raise RuntimeError(f"no verdict: {str(d.get('result'))[:200]}")
    return s["verdict"], s.get("reason", ""), float(d.get("total_cost_usd") or 0)


def judge(rubric: str, content: str, votes: int = VOTES,
          ask: Callable[[str, str], tuple[str, str, float]] = ask_claude, model: str = MODEL) -> Verdict:
    v = Verdict(passed=None)
    prompt = prompt_for(rubric, content)
    for _ in range(votes):
        try:
            verdict, reason, cost = ask(prompt, model)
        except Exception as e:
            # A call that fails (the CLI updating itself, a network blip) is not a vote: an outside hiccup must never
            # be scored as the model's work being wrong.
            v.failed_calls.append(str(e))
            continue
        v.votes.append(verdict)
        v.reasons.append(reason)
        v.cost += cost
    if v.votes:
        v.passed = v.votes.count("PASS") * 2 > len(v.votes)
    return v


def combined(runner_score: float, runner_checks: int, judge_passed: bool) -> float:
    """The judge counts as one more soft check beside the runner's own scored checks."""
    return (runner_score * runner_checks + (1.0 if judge_passed else 0.0)) / (runner_checks + 1)
