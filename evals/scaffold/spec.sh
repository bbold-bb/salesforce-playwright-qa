#!/bin/bash
# Stage 2 workspace: a copy of the kit's harness (node_modules linked, not copied), the project, the story, the kit's
# docs, and the approved Test Steps at test-steps/<ticket>.md. Never the answer keys or docs/superpowers.
# Usage (from a case's scaffold.sh, in the run's folder): spec.sh <repo> <ticket>
set -euo pipefail
REPO="$1"; T="$2"
FIX="$REPO/evals/fixtures/acme-support"
H="$REPO/templates/qa/playwright"
for f in "$H"/* "$H"/.gitignore; do
  case "$(basename "$f")" in node_modules|test-results) continue ;; esac
  cp -R "$f" .
done
ln -s "$H/node_modules" node_modules
# The kit's example spec runs against the kit's demo org setup, not Acme Support; leave it out so a rehearsal of the
# story runs only the story's spec.
rm -f tests/example.spec.ts
mkdir -p stories test-steps docs
cp "$FIX/project.md" .
cp "$FIX/stories/$T.md" stories/
cp "$FIX/approved/$T.md" "test-steps/$T.md"
cp "$REPO"/docs/*.md docs/
