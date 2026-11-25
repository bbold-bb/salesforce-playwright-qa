#!/bin/bash
# The org tier: for each story, Claude writes the spec from the approved Test Steps, rehearses it (round R0) against a
# throwaway scratch org and fixes it until it passes or the stop rule fires. check.py then grades each run from the
# rehearsal's own results.json. Runs outside claude plugin eval, whose sealed runs have no network or sf CLI.
#
# Usage: QA_EVALS_DEVHUB=<dev hub alias> evals/org/run.sh [--stories "ACME-11 ACME-12"] [--runs 3] [--model M]
#          [--budget-usd 10] [--keep-org] [--keep] [--save LABEL]
#   --budget-usd  the most one run may spend (claude --max-budget-usd); a run that hits it scores 0
#   --keep-org    leave the scratch org up afterwards (it expires in a day either way)
#   --keep        leave the runs' working folders (in the system temp folder) for reading; each run's spec and
#                 rehearsal results are copied to the results folder either way
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
STORIES="ACME-11 ACME-12"; RUNS=3; MODEL="${QA_EVALS_MODEL:-opus}"; BUDGET=10; KEEP_ORG=0; KEEP_WS=0; CHECK_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --stories) STORIES="$2"; shift 2 ;;
    --runs) RUNS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --budget-usd) BUDGET="$2"; shift 2 ;;
    --keep-org) KEEP_ORG=1; shift ;;
    --keep) KEEP_WS=1; shift ;;
    --save) CHECK_ARGS+=(--save "$2"); shift 2 ;;
    *) echo "org/run.sh: unknown option $1" >&2; exit 2 ;;
  esac
done

OUT="$REPO/evals/results/$(date -u +%Y-%m-%dT%H-%M-%SZ)-org"
mkdir -p "$OUT"
# The runs work outside the repo: Claude Code won't let a headless run write into a folder inside another project.
# No link to it from the results folder: a link left dangling there breaks claude plugin eval for every case.
WSROOT="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/qa-evals-org.XXXXXX")" && pwd -P)"
cleanup() {
  [ "$KEEP_ORG" = 1 ] || "$REPO/evals/org/org-down.sh" "$OUT"
  if [ "$KEEP_WS" = 1 ]; then echo "org/run.sh: working folders kept in $WSROOT"; else rm -rf "$WSROOT"; fi
}
trap cleanup EXIT
# Ctrl-C or a kill stops the whole loop, not just the run in progress, so no further run starts and spends money.
trap 'echo "org/run.sh: stopped"; exit 130' INT TERM

set +e
"$REPO/evals/org/org-up.sh" "$OUT"
UP=$?
set -e
if [ "$UP" -ne 0 ]; then
  echo "org/run.sh: setup failed (exit $UP), not scored. See $OUT/org-*.json" >&2
  exit "$UP"
fi
ALIAS="$(cat "$OUT/org-alias")"
REAL_SF="$(command -v sf)"

# Tools a run may use. Bash is limited to running the harness, reading files, and the sf queries and describes the
# harness itself uses. Every sf call goes through the guard in evals/org/guard, which keeps it on the scratch org.
TOOLS=(Read Glob Grep Write Edit Skill "Bash(npm run qa:*)" "Bash(npx playwright test:*)"
       "Bash(sf data query:*)" "Bash(sf sobject describe:*)"
       "Bash(grep:*)" "Bash(ls:*)" "Bash(cat:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(wc:*)"
       "Bash(cut:*)" "Bash(echo:*)" "Bash(printenv:*)")
# Never allowed: writing the rehearsal's evidence (which is what grades the run), and reading the evals' own answer
# keys, approved steps and design (the run gets its approved steps in its own folder).
DENY=("Write(./evidence/**)" "Edit(./evidence/**)"
      "Read(/$REPO/evals/**)" "Read(/$REPO/docs/superpowers/**)"
      "Grep(/$REPO/evals/**)" "Grep(/$REPO/docs/superpowers/**)"
      "Glob(/$REPO/evals/**)" "Glob(/$REPO/docs/superpowers/**)")

for T in $STORIES; do
  for n in $(seq 1 "$RUNS"); do
    WS="$WSROOT/$T/run-$n"
    mkdir -p "$WS"
    (cd "$WS" && "$REPO/evals/scaffold/spec.sh" "$REPO" "$T")
    cp "$OUT/test-users.local.json" "$WS/"
    PROMPT="The Test Steps for $T on the Acme Support project are approved (test-steps/$T.md). Write the Playwright \
spec for it in tests/, then rehearse it against the QA org until every step passes, following the kit's rehearse-then-\
record rules. Rehearse with: npm run qa -- $T  (QA_ROUND=R0 and QA_REASON=rehearsal are already set, and the harness \
already points at the QA org; sf queries and describes go to the QA org without naming it). Run each rehearsal in \
the foreground and wait for it: it can take up to 30 minutes, so give the Bash call a 1800000 ms timeout. This is a \
one-shot session: it ends as soon as you stop, so nothing left running in the background is ever picked up. Run \
commands one at a time, not chained with cd, pipes or semicolons. Don't record a real round. Stop when every step \
passes, or when the stop rule says to stop."
    echo "org/run.sh: $T run $n of $RUNS"
    (cd "$WS" && env PATH="$REPO/evals/org/guard:$PATH" QA_EVALS_REAL_SF="$REAL_SF" QA_EVALS_ORG_ALIAS="$ALIAS" \
        SF_ORG="$ALIAS" SF_TARGET_ORG="$ALIAS" QA_PRIMARY_ORG="$ALIAS" QA_ROUND=R0 QA_REASON=rehearsal \
        QA_EVIDENCE_DIR="$WS/evidence" \
        BASH_DEFAULT_TIMEOUT_MS=1800000 BASH_MAX_TIMEOUT_MS=1800000 \
        claude -p "$PROMPT" --model "$MODEL" --plugin-dir "$REPO" --setting-sources "" --strict-mcp-config \
        --no-session-persistence --permission-mode acceptEdits --max-budget-usd "$BUDGET" --output-format json \
        --disallowedTools "${DENY[@]}" --allowedTools "${TOOLS[@]}" < /dev/null > claude.json 2> claude.err) \
      || echo "org/run.sh: $T run $n ended with an error (see claude.err)"
  done
done

python3 "$REPO/evals/org/write_result.py" "$OUT" "$MODEL" "$WSROOT"
# check.py exits 1 when a case scores under the pass mark; that is this script's exit status too.
python3 "$REPO/evals/check.py" "$OUT/result.json" --keep ${CHECK_ARGS[@]+"${CHECK_ARGS[@]}"}
