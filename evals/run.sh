#!/bin/bash
# Runs the QA evals: the model runs and soft grading through claude plugin eval, then the hard checks in check.py.
# Usage: evals/run.sh [--tag T]... [--case GLOB] [--model M] [--runs N] [-j N] [--max-cost-usd X] [--save LABEL] [--keep]
# Never publishes the report (--no-publish). See evals/README.md.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export QA_EVALS_REPO="$REPO"

EVAL_ARGS=()
CHECK_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --save) CHECK_ARGS+=(--save "$2"); shift 2 ;;
    --keep) CHECK_ARGS+=(--keep); shift ;;
    --tag|--case|--model|--runs|--max-cost-usd|-j|--concurrency) EVAL_ARGS+=("$1" "$2"); shift 2 ;;
    *) echo "run.sh: unknown option $1" >&2; exit 2 ;;
  esac
done

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT_DIR="$REPO/evals/results/$STAMP"
mkdir -p "$OUT_DIR"

# Threshold 0 here: the pass mark (0.67) is applied by check.py to the combined score.
set +e
claude plugin eval "$REPO" --no-publish --keep-temp --scaffold --trust-plugin \
  --threshold 0 --output-dir "$OUT_DIR" --json "$OUT_DIR/result.json" \
  --allow-tools Bash Write Edit ${EVAL_ARGS[@]+"${EVAL_ARGS[@]}"}
EVAL_EXIT=$?
set -e
if [ ! -f "$OUT_DIR/result.json" ]; then
  echo "run.sh: the eval run wrote no result (exit $EVAL_EXIT)" >&2
  exit "$EVAL_EXIT"
fi
python3 "$REPO/evals/check.py" "$OUT_DIR/result.json" ${CHECK_ARGS[@]+"${CHECK_ARGS[@]}"}
