#!/bin/bash
# Deletes the org tier's scratch org named in <out>/org-alias. Safe to run twice. Refuses any alias that isn't one
# org-up.sh made (qa-evals-*), so it can never delete another org.
set -uo pipefail
OUT="$1"
[ -f "$OUT/org-alias" ] || exit 0
ALIAS="$(cat "$OUT/org-alias")"
case "$ALIAS" in qa-evals-2*) ;; *) echo "org-down: refusing to delete '$ALIAS' (not a qa-evals scratch org)" >&2; exit 2 ;; esac
sf org delete scratch --target-org "$ALIAS" --no-prompt --json > "$OUT/org-delete.json" 2>&1 && echo "org-down: deleted $ALIAS"
rm -f "$OUT/org-alias"
