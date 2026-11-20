"""Measures a block of Claude Code QA work from its session log, and adds it to the ledger's sessions.csv.

Every model call is logged with its time and token use. This counts each call once, adds the session's
subagents that ran in the same window, and prices the tokens at the Claude API list price.

    python3 ledger/session_cost.py --session <id> --start 2026-01-05T10:00 --end 2026-01-05T10:30 \\
        --kind run --qa PROJ-21 --runs PROJ-21-R3-A1 --append

--session takes a session ID or "latest" (the most recently written log for this project). Times are in the time
zone set in TZ below (UTC by default, set QA_TZ to your team's zone; the columns end in _local). Without --append it only prints the
figures. After a change to PRICES, `python3 ledger/session_cost.py --reprice` measures every recorded row again and
rewrites its cost.

Where the logs are: Claude Code keeps one folder per project under ~/.claude/projects/, named after the folder you
started Claude Code in, with every character that isn't a letter or a digit replaced by "-". So
"/Users/you/projects/acme-qa" becomes "-Users-you-projects-acme-qa". This
script works that out from --project (default: CLAUDE_PROJECT_DIR if set, else the git repository this file is in,
else the current folder). If the folder isn't found, list ~/.claude/projects/ and pass the right one with --log-dir.

Agent minutes are working time on the clock: from each prompt to the last model call, the session's or a
subagent's, before the next prompt, so time spent waiting on a person doesn't count. Subagents' tokens and cost
are included, and their time counts once even when they run alongside the session or each other.

Count only the work QA needs on any project (scripting, running, fixing, build checks, reviewing evidence,
publishing, the Jira update), so the figures carry over to other projects. Leave out a project's own extras, such as
pushing to GitHub: set the window around them, and split a block in two if one falls in the middle.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import qa_ledger as L

# ---- Project settings -------------------------------------------------------------------------------------------
TZ = ZoneInfo(os.environ.get("QA_TZ", "UTC"))  # the zone --start and --end are given in

# Dollars per million tokens, Claude API list price. A cache write costs 1.25 times input when it lives five
# minutes and twice input when it lives an hour; the log says which (usage.cache_creation).
# These are the API list prices as of 2026-10. Check them against the current Anthropic pricing page before you
# quote a figure, and add a row for every model your sessions use (subagents often run on a different model):
# the script stops on a model it has no price for rather than guess. Model IDs match by prefix.
# The cost is a list-price equivalent for scoping, not what your team pays.
PRICES = {
    "claude-opus-5-5": {"input": 4.0, "cache_write_5m": 5.0, "cache_write_1h": 8.0, "cache_read": 0.20, "output": 20.0},
}
TOKEN_KINDS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
# -----------------------------------------------------------------------------------------------------------------


def split(u: dict) -> dict[str, int]:
    """A call's tokens by kind. A write the log doesn't break down by lifetime is priced at the one-hour rate,
    the higher of the two, so a missing breakdown never lowers the cost."""
    writes = u.get("cache_creation_input_tokens", 0) or 0
    by_ttl = u.get("cache_creation") or {}
    w5 = by_ttl.get("ephemeral_5m_input_tokens", 0) or 0
    return {
        "input": u.get("input_tokens", 0) or 0,
        "cache_write_5m": w5,
        "cache_write_1h": writes - w5,
        "cache_read": u.get("cache_read_input_tokens", 0) or 0,
        "output": u.get("output_tokens", 0) or 0,
    }


def project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    try:
        top = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if top:
            return Path(top)
    except (OSError, subprocess.CalledProcessError):
        pass
    return Path.cwd()


def log_dir_for(project: Path) -> Path:
    """Claude Code's log folder for a project: the absolute path with each non-alphanumeric character as "-"."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(project.resolve()))


def local(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TZ)


def load(path: Path, start: datetime, end: datetime):
    """Assistant calls (deduplicated by message ID) and prompts in the window.

    A call is logged on several lines, one per content block, up to a couple of minutes apart. Each call is timed
    by its first line, so a call whose lines straddle the boundary between two blocks counts in one block only."""
    first: dict[str, tuple[datetime, dict, str]] = {}
    prompts: list[datetime] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = d.get("timestamp")
            if not ts:
                continue
            t = local(ts)
            if d.get("type") == "assistant":
                m = d.get("message") or {}
                # Keying by message ID counts a call once; keeping its earliest line times it by where it started.
                if m.get("id") and m.get("usage") and (m["id"] not in first or t < first[m["id"]][0]):
                    first[m["id"]] = (t, m["usage"], m.get("model", ""))
                continue
            if not (start <= t <= end):
                continue
            if d.get("type") == "user":
                # A prompt is text from the person. Tool results are also logged as "user" lines; they aren't prompts.
                c = (d.get("message") or {}).get("content")
                is_prompt = isinstance(c, str) or (
                    isinstance(c, list) and any(x.get("type") == "text" for x in c)
                    and not any(x.get("type") == "tool_result" for x in c)
                )
                if is_prompt:
                    prompts.append(t)
    calls = {k: v for k, v in first.items() if start <= v[0] < end}
    return calls, sorted(prompts)


def price(model: str) -> dict[str, float]:
    for name, p in PRICES.items():
        if model.startswith(name):
            return p
    raise SystemExit(f"No list price for model {model!r}. Add it to PRICES in {Path(__file__).name}.")


def measure(logs: Path, session: str, start: datetime, end: datetime) -> dict:
    main = logs / f"{session}.jsonl"
    if not main.exists():
        raise SystemExit(f"No session log at {main}")
    calls, prompts = load(main, start, end)
    sub_calls: dict[str, tuple[datetime, dict, str]] = {}
    for sub in sorted((logs / session / "subagents").glob("*.jsonl")):
        c, _ = load(sub, start, end)
        sub_calls.update(c)
    everything = {**calls, **sub_calls}
    if not everything:
        raise SystemExit("No model calls in that window")

    tokens = dict.fromkeys(TOKEN_KINDS, 0)
    cost = 0.0
    models = set()
    for _, u, model in everything.values():
        p = price(model)
        models.add(model)
        for k, v in split(u).items():
            tokens[k] += v
            cost += v * p[k] / 1_000_000

    # Working time: each prompt to the last call, the session's or a subagent's, before the next prompt. Calls
    # before the first prompt in the window count from the window's start. It's clock time, so a subagent working
    # while the session waits counts once, and two working at once don't count twice.
    times = sorted(t for t, _, _ in everything.values())
    marks = [start] + [p for p in prompts if p > start] + [end]
    seconds = 0.0
    for a, b in zip(marks, marks[1:]):
        inside = [t for t in times if a <= t < b]
        if inside:
            seconds += (max(inside) - a).total_seconds()

    return {
        "calls": len(everything),
        "subagent_calls": len(sub_calls),
        "models": sorted(models),
        "tokens": tokens,
        "new_tokens": tokens["input"] + tokens["cache_write_5m"] + tokens["cache_write_1h"] + tokens["output"],
        "cost": cost,
        "agent_minutes": seconds / 60,
        "first": times[0],
        "last": times[-1],
    }


def latest_session(logs: Path) -> str:
    found = sorted(logs.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not found:
        raise SystemExit(f"No session logs in {logs}")
    return found[-1].stem


def reprice(logs: Path) -> int:
    """Measures every row in sessions.csv again from its session log and rewrites its cost, so a price change
    reaches the rows already recorded. Tokens, calls and minutes are rewritten too, from the same measure."""
    rows = L.read_rows("sessions.csv")
    before = after = 0.0
    for r in rows:
        start = datetime.fromisoformat(r["started_local"]).replace(tzinfo=TZ)
        end = datetime.fromisoformat(r["ended_local"]).replace(tzinfo=TZ) + timedelta(seconds=1)
        m = measure(logs, r["session_id"], start, end)
        before += float(r["cost_usd"])
        after += round(m["cost"], 2)
        print(f"{r['entry_id']}: ${r['cost_usd']} to ${m['cost']:.2f}")
        r.update({
            "calls": str(m["calls"]),
            "agent_minutes": f"{m['agent_minutes']:.2f}",
            "new_tokens": str(m["new_tokens"]),
            "cache_read_tokens": str(m["tokens"]["cache_read"]),
            "cost_usd": f"{m['cost']:.2f}",
        })
    L.write_all("sessions.csv", rows)
    print(f"{len(rows)} rows repriced: ${before:.2f} to ${after:.2f}")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--reprice":
        rp = argparse.ArgumentParser(description="Measure every recorded block again at the current PRICES")
        rp.add_argument("--reprice", action="store_true")
        rp.add_argument("--project", type=Path)
        rp.add_argument("--log-dir", type=Path)
        r = rp.parse_args(argv)
        return reprice(r.log_dir or log_dir_for(r.project or project_dir()))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--session", required=True, help='A session ID (the log file name without .jsonl), or "latest"')
    ap.add_argument("--start", required=True, help="YYYY-MM-DDTHH:MM[:SS], in TZ")
    ap.add_argument("--end", required=True, help="YYYY-MM-DDTHH:MM[:SS], in TZ, inclusive")
    ap.add_argument("--project", type=Path, help="The folder Claude Code was started in (default: see above)")
    ap.add_argument("--log-dir", type=Path, help="The session-log folder under ~/.claude/projects/, if not worked out from --project")
    ap.add_argument("--kind", choices=sorted(L.KINDS))
    ap.add_argument("--method", choices=sorted(L.METHODS), default="playwright")
    ap.add_argument("--qa", default="", help="QA sub-task keys the work covered, comma-separated")
    ap.add_argument("--runs", default="", help="Run IDs the work produced, comma-separated")
    ap.add_argument("--note", default="")
    ap.add_argument("--append", action="store_true", help="Add the row to sessions.csv")
    a = ap.parse_args(argv)

    logs = a.log_dir or log_dir_for(a.project or project_dir())
    if not logs.is_dir():
        raise SystemExit(f"No Claude Code log folder at {logs}. List ~/.claude/projects/ and pass --log-dir.")
    session = latest_session(logs) if a.session == "latest" else a.session
    start = datetime.fromisoformat(a.start).replace(tzinfo=TZ)
    # The end is inclusive to the second: calls are logged with fractions of a second.
    end = datetime.fromisoformat(a.end).replace(tzinfo=TZ) + timedelta(seconds=1)
    m = measure(logs, session, start, end)
    print(f"Session {session}, {m['first']:%Y-%m-%d %H:%M:%S} to {m['last']:%H:%M:%S} {TZ.key}")
    print(f"Model calls {m['calls']} ({m['subagent_calls']} by subagents), models {', '.join(m['models'])}")
    print(f"Tokens {m['tokens']}, new {m['new_tokens']:,}")
    print(f"AI minutes {m['agent_minutes']:.2f}, cost ${m['cost']:.2f} at list price")

    if a.append:
        if not a.kind:
            raise SystemExit("--kind is required with --append")
        qa = [k.strip() for k in a.qa.split(",") if k.strip()]
        runs = [r.strip() for r in a.runs.split(",") if r.strip()]
        known = {r["run_id"] for r in L.read_rows("scenario-runs.csv")}
        missing = [r for r in runs if r not in known]
        if missing:
            raise SystemExit(f"Run IDs not in scenario-runs.csv: {missing}")
        n = max((int(r["entry_id"][1:]) for r in L.read_rows("sessions.csv")), default=0) + 1
        L.append("sessions.csv", [{
            "entry_id": f"W{n:04d}",
            "session_id": session,
            "started_local": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "ended_local": (end - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S"),
            "kind": a.kind,
            "method": a.method,
            "qa_subtasks": ";".join(qa),
            "run_ids": ";".join(runs),
            "model": ";".join(m["models"]),
            "calls": str(m["calls"]),
            "agent_minutes": f"{m['agent_minutes']:.2f}",
            "new_tokens": str(m["new_tokens"]),
            "cache_read_tokens": str(m["tokens"]["cache_read"]),
            "cost_usd": f"{m['cost']:.2f}",
            "note": a.note,
        }])
        print(f"Added W{n:04d} to {L.path('sessions.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
