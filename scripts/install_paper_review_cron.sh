#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/iHateTheWorld555.github.io"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

SCHEDULE="${PAPER_REVIEW_CRON:-30 5 * * *}"
CMD="$REPO_ROOT/scripts/run_paper_review_workflow.sh >> $LOG_DIR/paper-review-workflow.log 2>&1"
LINE="$SCHEDULE $CMD"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

crontab -l 2>/dev/null | grep -vF "$CMD" > "$tmp" || true
printf '%s\n' "$LINE" >> "$tmp"
crontab "$tmp"

echo "Installed cron entry:"
echo "$LINE"
