#!/bin/bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
exec "$REPO/evals/scaffold/spec.sh" "$REPO" ACME-12
