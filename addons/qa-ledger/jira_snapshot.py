"""Writes the ledger's Jira snapshot (jira-items.csv) from saved Jira search results.

The snapshot is how the ledger knows each QA sub-task's parent story or Task, its epic and its sprint, so nobody
types that in by hand. Jira is only read. Refresh it before a report, or before a run so the run is stamped with
the right sprint:

1. Search Jira with  project = PROJ ORDER BY key ASC  (your project key, set in JIRA_PROJECT below) and the fields
   summary, issuetype, parent, status, updated and the Sprint field (SPRINT below), every page, saving each
   page as JSON. Through an Atlassian connector a large result is often saved to a file; any of its JSON shapes
   works (a list of issues, {"issues": [...]}, or {"issues": {"nodes": [...]}}).
2. python3 ledger/jira_snapshot.py page1.json page2.json ...

Fetch every page. A sub-task whose parent isn't in the results stops the script, since its story, epic and sprint
would otherwise be blank.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import qa_ledger as L

# ---- Project settings -------------------------------------------------------------------------------------------
JIRA_PROJECT = "PROJ"
# The Sprint field's ID. customfield_10020 is common on Jira Cloud but not universal: check yours (an issue's JSON,
# or the field list in Jira settings) before the first snapshot.
SPRINT = "customfield_10020"
ET = ZoneInfo(os.environ.get("QA_TZ", "UTC"))  # the zone snapshot_local is written in
# -----------------------------------------------------------------------------------------------------------------


def issues(doc) -> list[dict]:
    if isinstance(doc, list):
        return doc
    i = doc.get("issues", doc)
    if isinstance(i, dict):
        i = i.get("nodes", [])
    return i


def sprint_names(fields: dict) -> list[str]:
    # Jira lists every sprint the item has been in, oldest first; the last is the current one.
    return [s.get("name", "") for s in (fields.get(SPRINT) or []) if isinstance(s, dict)]


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        print(f"This project's search:  project = {JIRA_PROJECT} ORDER BY key ASC  with Sprint field {SPRINT}")
        return 1
    items: dict[str, dict] = {}
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for it in issues(json.load(f)):
                items[it["key"]] = it
    if not any("updated" in it.get("fields", {}) for it in items.values()):
        raise SystemExit("The search results have no 'updated' field; include it in the fields list")

    def epic_of(key: str, seen: set[str] | None = None) -> str:
        seen = seen or set()
        it = items.get(key)
        if not it or key in seen:
            return ""
        seen.add(key)
        f = it["fields"]
        if f["issuetype"]["name"] == "Epic":
            return key
        parent = (f.get("parent") or {}).get("key", "")
        return epic_of(parent, seen) if parent else ""

    now = datetime.now(ET).strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for key, it in sorted(items.items(), key=lambda kv: int(kv[0].split("-")[1])):
        f = it["fields"]
        sprints = sprint_names(f)
        epic = epic_of(key)
        rows.append({
            "key": key,
            "type": f["issuetype"]["name"],
            "title": f.get("summary", ""),
            "status": (f.get("status") or {}).get("name", ""),
            "parent": (f.get("parent") or {}).get("key", ""),
            "epic": epic,
            "epic_title": items[epic]["fields"]["summary"] if epic in items else "",
            "sprint": sprints[-1] if sprints else "",
            "sprints": "; ".join(sprints),
            "updated": f.get("updated", ""),
            "snapshot_local": now,
        })
    # A sub-task with no sprint of its own counts in its parent's sprint, as Jira boards show it.
    by_key = {r["key"]: r for r in rows}
    for r in rows:
        if not r["sprint"] and r["parent"] in by_key and by_key[r["parent"]]["type"] != "Epic":
            r["sprint"] = by_key[r["parent"]]["sprint"]
    missing_parents = sorted({r["parent"] for r in rows if r["parent"] and r["parent"] not in items})
    if missing_parents:
        raise SystemExit(f"Parents not in the search results (fetch every page): {missing_parents}")
    L.write_all("jira-items.csv", rows)
    print(f"Wrote {len(rows)} Jira items to {L.path('jira-items.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
