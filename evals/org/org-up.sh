#!/bin/bash
# Creates the org tier's throwaway scratch org: the Acme Support fixture metadata, the test users, a first sign-in to
# warm it up, then a setup check. Writes the org's alias to <out>/org-alias.
# Usage: org-up.sh <out dir>        Needs QA_EVALS_DEVHUB (your Dev Hub's sf alias).
# Exit 3 when the setup check fails: the run is reported as "setup failed", not scored.
set -euo pipefail
: "${QA_EVALS_DEVHUB:?set QA_EVALS_DEVHUB to your Dev Hub alias}"
OUT="$(cd "$1" && pwd)"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PROJ="$REPO/evals/fixtures/acme-support/sfdx"
ALIAS="qa-evals-$(date +%Y%m%d-%H%M%S)"
export SF_DISABLE_COLORS=true FORCE_COLOR=0
cd "$PROJ"

echo "org-up: creating scratch org $ALIAS from $QA_EVALS_DEVHUB"
# Named before it exists, so org-down.sh deletes it even when creation times out or is interrupted.
echo "$ALIAS" > "$OUT/org-alias"
sf org create scratch --definition-file config/project-scratch-def.json --target-dev-hub "$QA_EVALS_DEVHUB" \
  --alias "$ALIAS" --duration-days 1 --wait 20 --json > "$OUT/org-create.json"

echo "org-up: deploying the fixture metadata"
sf project deploy start --source-dir force-app --target-org "$ALIAS" --wait 30 --json > "$OUT/org-deploy.json"

echo "org-up: creating the test users"
# The kit's own script, as a tester would run it. The settings it writes are copied into each run's folder (run.sh).
USERS=(python3 "$REPO/templates/qa/test_users.py" --org "$ALIAS" --tester "Eval A" --persona SupportAgent
       --personas "$REPO/evals/fixtures/acme-support/personas.json" --settings "$OUT/test-users.local.json")
"${USERS[@]}" --apply
"${USERS[@]}" --check || exit 3

echo "org-up: first sign-in (a new org's first Lightning load is slow)"
NODE_PATH="$REPO/templates/qa/playwright/node_modules" node "$REPO/evals/org/warm.cjs" "$ALIAS"

echo "org-up: setup check"
python3 - "$ALIAS" <<'PY' || exit 3
import json, subprocess, sys
alias = sys.argv[1]
def sf(*args):
    out = subprocess.run(["sf", *args, "--target-org", alias, "--json"], capture_output=True, text=True)
    return json.loads(out.stdout)["result"]
fields = {f["name"] for f in sf("sobject", "describe", "--sobject", "Case")["fields"]}
problems = [f for f in ("Contact_Channel__c", "Resolution_Summary__c") if f not in fields]
vr = sf("data", "query", "--use-tooling-api", "--query",
        "SELECT Active FROM ValidationRule WHERE ValidationName = 'Resolution_Summary_Required'")["records"]
if not vr or not vr[0]["Active"]:
    problems.append("validation rule Resolution_Summary_Required")
if not sf("data", "query", "--query", "SELECT Id FROM Report WHERE DeveloperName = 'Cases_by_Contact_Channel'")["records"]:
    problems.append("report Cases_by_Contact_Channel")
if problems:
    print("org-up: setup check failed:", ", ".join(problems))
    sys.exit(1)
print("org-up: setup check passed")
PY
echo "org-up: ready, $ALIAS"
