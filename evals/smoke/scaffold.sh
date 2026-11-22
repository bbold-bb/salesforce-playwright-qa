#!/bin/bash
# Copies one kit doc into the run's folder, to prove a scaffold can find the repo. The runner strips custom
# environment variables, so scaffolds find the repo from their own path (evals/<tier>/<case>/scaffold.sh).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cp "$REPO/docs/writing-test-steps.md" .
