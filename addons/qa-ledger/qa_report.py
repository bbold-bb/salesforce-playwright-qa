"""QA ledger report: scenarios, rounds, attempts, time and cost, rolled up by sprint, epic, story or Task, and QA
sub-task.

    python3 ledger/qa_report.py                       everything
    python3 ledger/qa_report.py --sprint "Sprint 1"   one sprint (matches the start of the name)
    python3 ledger/qa_report.py --epic E1             one epic: its key (PROJ-5) or the first word of its title
                                                      (E1 matches "E1 Case foundation", not "E10 ...")
    python3 ledger/qa_report.py --qa PROJ-21          one QA sub-task, down to each scenario run

How cost reaches a scenario: a work session's cost is split evenly across the QA sub-tasks it covered, then each
QA sub-task's share is split evenly across the scenario runs that session produced for it. A share with no
scenario run (writing a script, a review, a write-up) stays with the QA sub-task, so it counts in the "all work"
figures but not in "running". Setup that isn't for one QA sub-task counts only in the totals.

Sprint: a scenario run counts in the sprint it was stamped with when it ran; cost counts in the QA sub-task's
sprint in the latest Jira snapshot.

Runs whose reason is in LEFT_OUT_REASONS (tooling-check: checks of the QA tooling itself; rehearsal: practice runs
of a script before its recorded run) are left out of every figure and listed at the end.

Every file is read as text and audited (data_hygiene.py, in the qa folder) before anything is counted, and the
script stops on anything unexplained. A figure going into a write-up, ticket or message also gets an independent
recompute first.
"""
from __future__ import annotations

import argparse
import sys

import polars as pl

import qa_ledger as L
from data_hygiene import audit, read_csv_polars, require_clean

NONE = "(none)"


def load(name: str) -> pl.DataFrame:
    p = L.path(name)
    if not p.exists():
        return pl.DataFrame({c: [] for c in L.COLUMNS[name]}, schema={c: pl.Utf8 for c in L.COLUMNS[name]})
    df = read_csv_polars(p)
    missing = set(L.COLUMNS[name]) - set(df.columns)
    if missing:
        raise SystemExit(f"{name} is missing columns {sorted(missing)}")
    return df


def check(runs: pl.DataFrame, sessions: pl.DataFrame, catalog: pl.DataFrame, jira: pl.DataFrame) -> None:
    issues = []
    for df, cols, label in [
        (runs, ["run_id", "qa_subtask", "scenario", "round", "attempt", "reason", "method", "org", "sprint", "result"], "scenario-runs"),
        (sessions, ["entry_id", "kind", "method", "qa_subtasks", "run_ids"], "sessions"),
        (catalog, ["qa_subtask", "scenario"], "scenarios"),
        (jira, ["key", "type", "parent", "epic", "sprint"], "jira-items"),
    ]:
        for c in cols:
            issues += audit(df[c].to_list(), f"{label}.{c}")
    require_clean(issues)

    problems = []
    reasons = set(L.ROUND_REASONS) | set(L.ATTEMPT_REASONS) | set(L.OTHER_REASONS)
    problems += [f"unknown reason {r!r}" for r in set(runs["reason"].drop_nulls()) - reasons]
    problems += [f"unknown method {m!r}" for m in (set(runs["method"].drop_nulls()) | set(sessions["method"].drop_nulls())) - L.METHODS]
    problems += [f"unknown kind {k!r}" for k in set(sessions["kind"].drop_nulls()) - set(L.KINDS)]
    problems += [f"unknown result {r!r}" for r in set(runs["result"].drop_nulls()) - {"pass", "fail", "not-run"}]
    known_runs = set(runs["run_id"])
    for ids in sessions["run_ids"].drop_nulls():
        problems += [f"sessions.csv names run {r} that isn't in scenario-runs.csv" for r in ids.split(";") if r not in known_runs]
    keys = set(jira["key"])
    qa = set(runs["qa_subtask"]) | set(catalog["qa_subtask"])
    for ids in sessions["qa_subtasks"].drop_nulls():
        qa |= set(ids.split(";"))
    problems += [f"{k} isn't in the Jira snapshot; refresh it (ledger/jira_snapshot.py)" for k in sorted(qa - keys)]
    dupes = runs.group_by(["run_id", "scenario"]).len().filter(pl.col("len") > 1)
    problems += [f"run {r['run_id']} lists {r['scenario']} twice" for r in dupes.iter_rows(named=True)]
    if problems:
        raise SystemExit("Ledger problems:\n  " + "\n  ".join(problems))


def allocate(runs: pl.DataFrame, sessions: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Splits each session across its QA sub-tasks, then across the scenario runs it produced for each.
    Returns (per-QA-sub-task shares, per-scenario-run shares)."""
    measures = ["cost_usd", "new_tokens", "cache_read_tokens", "agent_minutes"]
    s = sessions.with_columns(
        [pl.col(m).cast(pl.Float64, strict=True).fill_null(0.0) for m in measures]
    ).with_columns(
        pl.col("qa_subtasks").fill_null(NONE).str.split(";").alias("qa"),
        pl.col("run_ids").fill_null("").str.split(";").alias("runs"),
    )
    s = s.with_columns(pl.col("qa").list.len().alias("n_qa")).explode("qa")
    s = s.with_columns([(pl.col(m) / pl.col("n_qa")).alias(m) for m in measures])

    linked = (
        s.select("entry_id", "qa", "runs").explode("runs").filter(pl.col("runs") != "")
        .join(runs.select("run_id", "qa_subtask", "scenario", "started_local"), left_on=["runs", "qa"],
              right_on=["run_id", "qa_subtask"], how="inner")
        .rename({"runs": "run_id", "qa": "qa_subtask"})
    )
    counts = linked.group_by(["entry_id", "qa_subtask"]).len("n_runs")
    shares = s.rename({"qa": "qa_subtask"}).join(counts, on=["entry_id", "qa_subtask"], how="left")
    shares = shares.with_columns(pl.col("n_runs").fill_null(0), (pl.col("n_runs").fill_null(0) > 0).alias("running"))
    per_run = linked.join(shares.select("entry_id", "qa_subtask", "n_runs", *measures), on=["entry_id", "qa_subtask"]).with_columns(
        [(pl.col(m) / pl.col("n_runs")).alias(m) for m in measures]
    )
    return shares.select("entry_id", "qa_subtask", "kind", "method", "running", *measures), per_run


def money(x: float) -> str:
    return f"${x:,.2f}"


def table(df: pl.DataFrame) -> str:
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.iter_rows():
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(lines)


def rollup(runs: pl.DataFrame, shares: pl.DataFrame, catalog: pl.DataFrame, by: str, label: str) -> pl.DataFrame:
    r = runs.group_by(by).agg(
        pl.col("qa_subtask").n_unique().alias("QA sub-tasks"),
        pl.col("parent").filter(pl.col("parent_type") == "Story").n_unique().alias("Stories"),
        pl.col("parent").filter(pl.col("parent_type") == "Task").n_unique().alias("Tasks"),
        pl.concat_str("qa_subtask", "scenario").n_unique().alias("Scenarios run"),
        pl.len().alias("Scenario runs"),
        pl.concat_str("qa_subtask", "org", "round").n_unique().alias("Rounds"),
        pl.col("run_id").n_unique().alias("Attempts"),
        (pl.col("result") == "fail").sum().alias("Failed runs"),
    )
    c = catalog.group_by(by).agg(pl.concat_str("qa_subtask", "scenario").n_unique().alias("Scenarios defined"))
    k = shares.group_by(by).agg(
        pl.col("cost_usd").sum().alias("all_cost"),
        pl.col("cost_usd").filter(pl.col("running")).sum().alias("run_cost"),
        (pl.col("new_tokens") + pl.col("cache_read_tokens")).sum().alias("tokens"),
        pl.col("agent_minutes").sum().alias("agent_min"),
    )
    out = r.join(c, on=by, how="full", coalesce=True).join(k, on=by, how="full", coalesce=True).fill_null(0)
    n = pl.col("Scenario runs")
    out = out.with_columns(
        pl.when(n > 0).then(pl.col("run_cost") / n).alias("run_per"),
        pl.when(n > 0).then(pl.col("all_cost") / n).alias("all_per"),
        pl.when(n > 0).then(pl.col("tokens") / n).alias("tok_per"),
    ).sort(by)
    return out.select(
        pl.col(by).alias(label), "Scenarios defined", "Scenarios run", "Scenario runs", "Failed runs", "Rounds",
        "Attempts", "QA sub-tasks", "Stories", "Tasks",
        pl.col("all_cost").map_elements(money, return_dtype=pl.Utf8).alias("Cost, all work"),
        pl.col("run_cost").map_elements(money, return_dtype=pl.Utf8).alias("Cost, running"),
        pl.col("run_per").map_elements(lambda x: money(x) if x is not None else "-", return_dtype=pl.Utf8).alias("Running cost per scenario run"),
        pl.col("all_per").map_elements(lambda x: money(x) if x is not None else "-", return_dtype=pl.Utf8).alias("All-work cost per scenario run"),
        pl.col("tok_per").map_elements(lambda x: f"{x:,.0f}" if x is not None else "-", return_dtype=pl.Utf8).alias("Tokens per scenario run"),
        pl.col("agent_min").round(1).alias("AI minutes"),
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="QA ledger report", epilog="Refresh the Jira snapshot (ledger/jira_snapshot.py) first.")
    ap.add_argument("--sprint", help="One sprint: matches the start of the sprint name")
    ap.add_argument("--epic", help="One epic: its key, or the first word of its title")
    ap.add_argument("--qa", help="One QA sub-task key, with every scenario run listed")
    a = ap.parse_args(argv)

    runs, sessions = load("scenario-runs.csv"), load("sessions.csv")
    catalog, jira = load("scenarios.csv"), load("jira-items.csv")
    check(runs, sessions, catalog, jira)
    left_out = runs.filter(pl.col("reason").is_in(list(L.LEFT_OUT_REASONS)))
    runs = runs.filter(~pl.col("reason").is_in(list(L.LEFT_OUT_REASONS)))
    shares, per_run = allocate(runs, sessions)

    parents = jira.select(pl.col("key").alias("parent"), pl.col("type").alias("parent_type"), pl.col("title").alias("parent_title"))
    context = (
        jira.select(pl.col("key").alias("qa_subtask"), "parent", "epic", "epic_title", pl.col("sprint").alias("snapshot_sprint"))
        .join(parents, on="parent", how="left")
        .with_columns(pl.col("epic_title").fill_null(NONE).alias("epic_name"), pl.col("snapshot_sprint").fill_null(NONE))
    )
    runs = runs.join(context, on="qa_subtask", how="left").with_columns(
        pl.coalesce("sprint", "snapshot_sprint").fill_null(NONE).alias("sprint"),
        pl.concat_str(pl.col("parent"), pl.lit(" "), pl.col("parent_title").fill_null("")).alias("story"),
        pl.concat_str("qa_subtask", "scenario", separator=" ").alias("qa_scenario"),
    )
    shares = shares.join(context, on="qa_subtask", how="left").with_columns(
        pl.col("snapshot_sprint").fill_null(NONE).alias("sprint"), pl.col("epic_name").fill_null(NONE),
        pl.concat_str(pl.col("parent").fill_null(NONE), pl.lit(" "), pl.col("parent_title").fill_null("")).alias("story"),
    )
    catalog = catalog.join(context, on="qa_subtask", how="left").with_columns(
        pl.col("snapshot_sprint").alias("sprint"),
        pl.concat_str(pl.col("parent"), pl.lit(" "), pl.col("parent_title").fill_null("")).alias("story"),
    )

    left_out = left_out.join(context, on="qa_subtask", how="left").with_columns(pl.coalesce("sprint", "snapshot_sprint").fill_null(NONE).alias("sprint"))
    scope = []
    for name, df in [("runs", runs), ("shares", shares), ("catalog", catalog), ("left_out", left_out)]:
        if a.sprint:
            df = df.filter(pl.col("sprint").str.starts_with(a.sprint))
        if a.epic:
            df = df.filter((pl.col("epic") == a.epic) | pl.col("epic_name").str.starts_with(f"{a.epic} "))
        if a.qa:
            df = df.filter(pl.col("qa_subtask") == a.qa)
        scope.append(df)
    runs, shares, catalog, left_out = scope
    title = ", ".join(f"{k} {v}" for k, v in [("sprint", a.sprint), ("epic", a.epic), ("QA sub-task", a.qa)] if v) or "all"

    print(f"# QA ledger report: {title}\n")
    total = shares.with_columns(pl.lit("All").alias("all"))
    print("## Totals\n")
    print(table(rollup(runs.with_columns(pl.lit("All").alias("all")), total, catalog.with_columns(pl.lit("All").alias("all")), "all", "Scope")))
    for by, label in [("sprint", "Sprint"), ("epic_name", "Epic"), ("story", "Story or Task"), ("qa_subtask", "QA sub-task")]:
        print(f"\n## By {label.lower()}\n")
        print(table(rollup(runs, shares.filter(pl.col("qa_subtask") != NONE), catalog, by, label)))

    print("\n## By kind of work\n")
    kinds = shares.group_by("kind").agg(
        pl.col("cost_usd").sum().map_elements(money, return_dtype=pl.Utf8).alias("Cost"),
        (pl.col("new_tokens") + pl.col("cache_read_tokens")).sum().cast(pl.Int64).alias("Tokens"),
        pl.col("agent_minutes").sum().round(1).alias("AI minutes"),
    ).sort("kind")
    print(table(kinds.rename({"kind": "Kind"})))

    print("\n## By method\n")
    by_method = runs.group_by("method").agg(
        pl.len().alias("Scenario runs"),
        pl.col("seconds").cast(pl.Float64, strict=False).mean().round(0).alias("Average seconds per scenario run"),
    ).join(
        per_run.join(runs.select("run_id", "scenario", "method"), on=["run_id", "scenario"]).group_by("method").agg(
            pl.col("cost_usd").sum().alias("cost")), on="method", how="left",
    ).with_columns(
        (pl.col("cost").fill_null(0) / pl.col("Scenario runs")).map_elements(money, return_dtype=pl.Utf8).alias("Running cost per scenario run"),
        pl.col("cost").fill_null(0).map_elements(money, return_dtype=pl.Utf8).alias("Cost, running"),
    ).drop("cost").sort("method")
    print(table(by_method.rename({"method": "Method"})))

    if a.qa:
        print("\n## Scenario runs\n")
        detail = runs.join(per_run.select("run_id", "scenario", "cost_usd").group_by(["run_id", "scenario"]).agg(pl.col("cost_usd").sum()),
                           on=["run_id", "scenario"], how="left").sort(["started_local", "scenario"])
        print(table(detail.select(
            pl.col("run_id").alias("Run"), pl.col("scenario").alias("Scenario"), pl.col("started_local").alias("Started (local)"),
            pl.col("reason").alias("Reason"), pl.col("method").alias("Method"), pl.col("result").alias("Result"),
            pl.col("seconds").alias("Seconds"), pl.col("cost_usd").fill_null(0).map_elements(money, return_dtype=pl.Utf8).alias("Running cost"),
        )))
    unlinked = shares.filter(pl.col("qa_subtask") == NONE)["cost_usd"].sum()
    print(f"\nSetup not tied to a QA sub-task: {money(unlinked)}, counted in the totals only. "
          "Running cost: sessions that produced scenario runs. All-work cost adds scripting, review, fixes and write-ups.")
    if left_out.height:
        ids = ", ".join(sorted(set(left_out["run_id"])))
        print(f"Left out of every figure: {left_out.height} scenario runs that checked the QA tooling or rehearsed a script ({ids}). "
              "They stay in the ledger and the evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
