#!/bin/bash
# Stage 1 workspace: the project, one story and its build sub-task, and the kit's docs. Never the answer keys,
# the approved steps, or docs/superpowers (the evals' own design, which describes the traps).
# Usage (from a case's scaffold.sh, in the run's folder): steps.sh <repo> <ticket>
set -euo pipefail
REPO="$1"; T="$2"
FIX="$REPO/evals/fixtures/acme-support"
mkdir -p stories builds docs qa-steps
cp "$FIX/project.md" .
cp "$FIX/stories/$T.md" stories/
cp "$FIX/builds/$T-build.md" builds/
cp "$REPO"/docs/*.md docs/
