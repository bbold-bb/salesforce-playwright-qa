#!/bin/bash
# Publishes a reviewed QA round to the team's shared QA Evidence folder in Google Drive, through Google Drive for
# desktop: copy the files into the synced folder and Drive uploads them.
#
#   ./publish.sh "evidence/<epic>/PROJ-21 Case Origin values/2026-01-05 my-partial-sandbox R2"
#   ./publish.sh --build-check-only "evidence/<epic>/PROJ-61 Business hours"
#
# --build-check-only is for a QA sub-task whose steps are all checked by query: it copies only the newest build check
# into the QA sub-task's folder, and only once its Verified line says the figures were independently recomputed.
#
# Publish a round once it's complete, never part way. It first checks every scenario has the evidence it declares
# (evidence_index.py, which writes evidence-index.csv into the round), then copies the round's final evidence (run
# summary, evidence index, screenshots, videos, query output) to the same place under QA Evidence, and the QA
# sub-task's newest build check into its folder. Earlier attempts and the run manifests stay on this machine: the
# manifests can list names from the org's Setup Audit Trail. results.json stays here too, and the shared run summary
# leaves out the attempts and the test tooling (shared_summary.py): the shared folder shows what was tested and what
# it showed. A rehearsal (evidence/rehearsal/) is never published. The QA ledger, if you use the add-on, stays on this
# machine too: it holds your team's cost figures, and the Drive folder may be shared with the client. It adds and
# updates files and never deletes anything in Drive. Watch the run's videos first, to confirm each scenario shows what
# it should and shows only test records.
#
# Run it from a real terminal (Terminal, iTerm, or your editor's terminal panel). A sandboxed agent shell may be
# unable to write to ~/Library/CloudStorage, where Google Drive for desktop keeps its folders, so the copy fails.
# Don't grant the agent Full Disk Access to get around it; run this yourself.
#
# One-time setup: put the local path of the QA Evidence folder in .drive-dir (gitignore it), for example
#   echo "$HOME/Library/CloudStorage/<your Google Drive for desktop folder>/Shared drives/<drive>/<folder>/QA Evidence" > .drive-dir
# or set QA_DRIVE_DIR for one run.
set -euo pipefail
cd "$(dirname "$0")"

# Where to record each publish, if your project keeps a log of what was pushed where. Change or blank it.
SYNC_LOG="${QA_SYNC_LOG:-}"

DRIVE="${QA_DRIVE_DIR:-$(cat .drive-dir 2>/dev/null || true)}"
if [ -z "$DRIVE" ]; then
  echo "Set the Drive folder once: put the local path of the QA Evidence folder in $(pwd)/.drive-dir"
  exit 1
fi
if [ ! -d "$DRIVE" ]; then
  if [ -d "$(dirname "$DRIVE")" ]; then
    mkdir "$DRIVE"
  else
    echo "Not found: $(dirname "$DRIVE"). Is Google Drive for desktop running, and is the path right?"
    exit 1
  fi
fi

if [ "${1:-}" = "--build-check-only" ]; then
  TICKET_REL="${2:?Give the QA sub-task folder, for example evidence/<epic>/<QA sub-task>}"
  TICKET_REL="${TICKET_REL%/}"
  case "$TICKET_REL" in evidence/*/*) ;; *) echo "Expected evidence/<epic>/<QA sub-task>, got: $TICKET_REL"; exit 1 ;; esac
  TICKET_DIR="${TICKET_REL#evidence/}"
  TICKET="$(basename "$TICKET_DIR" | cut -d' ' -f1)"
  check="$(ls "$TICKET"-build-check-*.md 2>/dev/null | sort | tail -1 || true)"
  [ -n "$check" ] || { echo "No build check for $TICKET in $(pwd)"; exit 1; }
  grep -q "^- \*\*Verified:\*\* figures verified" "$check" || { echo "$check isn't verified yet (its Verified line). Not published."; exit 1; }
  mkdir -p "$TICKET_REL" "$DRIVE/$TICKET_DIR"
  # The shared copy says nothing about how its figures were checked; the Verified line stays in the local copy.
  grep -v "^- \*\*Verified:\*\*" "$check" > "$DRIVE/$TICKET_DIR/$check"
  echo "Copied $check to $TICKET_DIR"
  echo "Drive for desktop uploads in the background."; [ -n "$SYNC_LOG" ] && echo "Record this publish in $SYNC_LOG."
  exit 0
fi

RUN="${1:?Give the run folder, for example evidence/<epic>/<QA sub-task>/<date> <org> <round>}"
RUN="${RUN%/}"
case "$RUN" in evidence/rehearsal/*) echo "A rehearsal is never published: $RUN"; exit 1 ;; esac
case "$RUN" in evidence/*/*/*) ;; *) echo "Expected evidence/<epic>/<QA sub-task>/<run>, got: $RUN"; exit 1 ;; esac
[ -f "$RUN/run-summary.md" ] || { echo "No run-summary.md in $RUN"; exit 1; }
python3 evidence_index.py "$RUN" || { echo "Not published."; exit 1; }
if [ "${2:-}" != "--reviewed" ]; then
  read -r -p "Have you watched every video in this run and seen only test records? [y/N] " ok
  [ "$ok" = "y" ] || [ "$ok" = "Y" ] || { echo "Not published."; exit 1; }
fi
REL="${RUN#evidence/}"
TICKET_DIR="$(dirname "$REL")"
TICKET="$(basename "$TICKET_DIR" | cut -d' ' -f1)"
mkdir -p "$DRIVE/$REL"
# No --delete: Drive keeps whatever is already there. Attempts, run manifests and results.json stay local, and the
# run summary goes as its shared copy.
rsync -a --exclude 'attempts/' --exclude 'run-manifest-*.json' --exclude 'results.json' --exclude 'run-summary.md' \
  "$RUN/" "$DRIVE/$REL/"
python3 shared_summary.py "$RUN/run-summary.md" > "$DRIVE/$REL/run-summary.md"
echo "Copied $REL"
# Only the newest build check: an older one is superseded and stays here.
check="$(ls "$TICKET"-build-check-*.md 2>/dev/null | sort | tail -1 || true)"
if [ -n "$check" ]; then
  # The shared copy says nothing about how its figures were checked; the Verified line stays in the local copy.
  grep -v "^- \*\*Verified:\*\*" "$check" > "$DRIVE/$TICKET_DIR/$check"
  echo "Copied $check"
fi
echo "Drive for desktop uploads in the background."; [ -n "$SYNC_LOG" ] && echo "Record this publish in $SYNC_LOG."
