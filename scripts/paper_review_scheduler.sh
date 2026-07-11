#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/iHateTheWorld555.github.io"
LOG_DIR="$REPO_ROOT/logs"
PID_FILE="$LOG_DIR/paper-review-scheduler.pid"
HOUR_UTC="${PAPER_REVIEW_HOUR_UTC:-5}"
MINUTE_UTC="${PAPER_REVIEW_MINUTE_UTC:-30}"

mkdir -p "$LOG_DIR"
exec 8>"$LOG_DIR/paper-review-scheduler.lock"
if ! flock -n 8; then
  echo "Another paper scheduler already owns the lock" >&2
  exit 0
fi

echo "$$" > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT INT TERM

while true; do
  now="$(date -u +%s)"
  next="$(date -u -d "today ${HOUR_UTC}:${MINUTE_UTC}:00" +%s)"
  if (( next <= now )); then
    next="$(date -u -d "tomorrow ${HOUR_UTC}:${MINUTE_UTC}:00" +%s)"
  fi
  delay=$((next - now))
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') next run: $(date -u -d "@$next" +'%Y-%m-%dT%H:%M:%SZ')"
  sleep "$delay"
  "$REPO_ROOT/scripts/run_paper_review_workflow.sh" >> "$LOG_DIR/paper-review-workflow.log" 2>&1 || \
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') workflow failed; see paper-review-workflow.log" >&2
done
