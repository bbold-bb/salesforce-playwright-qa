#!/bin/bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
exec "$REPO/evals/scaffold/steps.sh" "$REPO" ACME-12
