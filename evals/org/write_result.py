#!/usr/bin/env python3
"""Turns the org loop's runs (<out>/ws/<ticket>/run-<n>/claude.json) into a result.json in the shape claude plugin
eval writes, so check.py grades both the same way. A run scores 1 when Claude finished without an error; the hard
checks in check.py (the rehearsal's own results.json) decide the rest.

Usage: python3 evals/org/write_result.py <out dir> <model> [<working folders root>]   (default <out dir>/ws)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path


def build_result(out: Path, model: str, ws_root: Path | None = None) -> dict:
    cases = []
    total = 0.0
    for tdir in sorted((ws_root or out / "ws").iterdir()):
        arm = []
        for rdir in sorted(tdir.glob("run-*"), key=lambda p: int(p.name.split("-")[1])):
            cj = rdir / "claude.json"
            if cj.is_file():
                c = json.loads(cj.read_text() or "{}")
                cost = float(c.get("total_cost_usd") or 0)
                err = (c.get("subtype") or "error") if c.get("is_error") else None
            else:
                cost, err = 0.0, "no claude.json: the run didn't finish"
            total += cost
            arm.append({"score": 0 if err else 1, "error": err, "costUsd": cost, "workspacePath": str(rdir)})
        cases.append({"name": f"org-{tdir.name}", "arms": {"with": arm}})
    return {"startedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "claudeVersion": "", "costUsd": round(total, 4),
            "suite": {"modelOverride": model, "runner": "evals/org/run.sh"}, "cases": cases}


if __name__ == "__main__":
    out = Path(sys.argv[1])
    root = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    (out / "result.json").write_text(json.dumps(build_result(out, sys.argv[2], root), indent=1))
