#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/iHateTheWorld555.github.io"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

SCHEDULE="${PAPER_REVIEW_CRON:-30 5 * * *}"
CMD="$REPO_ROOT/scripts/run_paper_review_workflow.sh >> $LOG_DIR/paper-review-workflow.log 2>&1"
LINE="$SCHEDULE $CMD # daily-paper-review"

if command -v crontab >/dev/null 2>&1; then
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT

  crontab -l 2>/dev/null | grep -vF "# daily-paper-review" > "$tmp" || true
  printf '%s\n' "$LINE" >> "$tmp"
  crontab "$tmp"

  echo "Installed cron entry:"
  echo "$LINE"
  exit 0
fi

SCHEDULER="$REPO_ROOT/scripts/paper_review_scheduler.sh"
PID_FILE="$LOG_DIR/paper-review-scheduler.pid"
if [[ -s "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Persistent scheduler already running with PID $(cat "$PID_FILE")"
  exit 0
fi

rm -f "$PID_FILE"
setsid -f "$SCHEDULER" >> "$LOG_DIR/paper-review-scheduler.log" 2>&1
for _ in 1 2 3 4 5; do
  [[ -s "$PID_FILE" ]] && break
  sleep 1
done
if [[ ! -s "$PID_FILE" ]] || ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Error: persistent scheduler did not start" >&2
  exit 1
fi
echo "Installed persistent UTC scheduler with PID $(cat "$PID_FILE") (daily at ${PAPER_REVIEW_HOUR_UTC:-5}:${PAPER_REVIEW_MINUTE_UTC:-30})"
