"""Evidence index for a QA round: what evidence each scenario needs, what the round folder has, and what's missing.

Each scenario declares what shows it passed (in its Playwright spec, `evidence`): a screenshot for a state (a value
list, a message, a layout), a video where the behaviour matters (a rule firing, a record created end to end), query
output where nothing runs as a user, or a mix. This reads the round's results.json and the files on disk, writes
evidence-index.csv into the round folder, and exits non-zero if any scenario is missing evidence it declared, or
declares none. publish.sh runs it before copying a round to Drive.

  python3 evidence_index.py "evidence/<epic>/<QA sub-task>/<date> <org> <round>"

The QA sub-task folder's name starts with its ticket key and a space ("PROJ-21 Case Origin values"). Files are
named by ticket and scenario:

  screenshots/PROJ-21-S1.png, PROJ-21-S2a.png   one per scenario, or lettered when a scenario covers several records
  videos/PROJ-21-S1.webm, PROJ-21-F1.webm       one per scenario, or one per flow (several steps in one user session)
  queries/PROJ-21-S4.json                       query output

results.json holds {"results": [{"id": "S1", "title": "...", "flow": "F1" or absent, "passed": true, false or
absent when not run, "evidence": ["screenshot", "video"]}, ...]}.
"""
import csv, json, re, sys
from pathlib import Path

KINDS = {"screenshot": ("screenshots", r"[a-z]?\.png"), "video": ("videos", r"\.webm"), "query": ("queries", r"[a-z]?\.json")}


def index(round_dir: Path):
    ticket = round_dir.parent.name.split(" ")[0]
    store = json.loads((round_dir / "results.json").read_text())
    rows, problems = [], []
    for r in store["results"]:
        has = {}
        # A step in a flow is covered by the flow's video (<ticket>-<flow>.webm) as well as any of its own.
        names = [r["id"]] + ([r["flow"]] if r.get("flow") else [])
        for kind, (folder, suffix) in KINDS.items():
            ids = names if kind == "video" else [r["id"]]
            pattern = re.compile(rf"^{re.escape(ticket)}-({'|'.join(re.escape(i) for i in ids)}){suffix}$")
            d = round_dir / folder
            has[kind] = sorted(f.name for f in d.iterdir() if pattern.match(f.name)) if d.is_dir() else []
        declared = r.get("evidence") or []
        missing = [k for k in declared if not has[k]]
        if not declared:
            problems.append(f"{r['id']}: declares no evidence")
        if missing:
            problems.append(f"{r['id']}: missing {', '.join(missing)}")
        rows.append({
            "scenario": r["id"], "title": r["title"], "flow": r.get("flow") or "",
            "result": "not run" if r.get("passed") is None else "pass" if r["passed"] else "fail",
            # The test users signed in while the step ran: blank for a query or the admin.
            "ran_as": "; ".join(r.get("ranAs") or []),
            "needs": " + ".join(declared),
            "screenshots": "; ".join(has["screenshot"]), "video": "; ".join(has["video"]), "query_output": "; ".join(has["query"]),
            "missing": " + ".join(missing),
        })
    with open(round_dir / "evidence-index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["scenario"])
        w.writeheader()
        w.writerows(rows)
    return rows, problems


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 2)
    rows, problems = index(Path(sys.argv[1]))
    for r in rows:
        have = [k for k, v in (("screenshot", r["screenshots"]), ("video", r["video"]), ("query output", r["query_output"])) if v]
        print(f"{r['scenario']} {r['result']}: needs {r['needs'] or 'nothing declared'}; has {', '.join(have) or 'nothing'}")
    if problems:
        print("Not ready to publish:\n  " + "\n  ".join(problems))
        sys.exit(1)
