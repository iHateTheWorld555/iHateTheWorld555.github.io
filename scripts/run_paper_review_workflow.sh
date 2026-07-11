#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/iHateTheWorld555.github.io"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

# A manual catch-up run and the daily cron invocation must not edit/commit the
# same paper files concurrently.
exec 9>"$LOG_DIR/paper-review-workflow.lock"
if ! flock -n 9; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') another paper workflow is already running; skip"
  exit 0
fi

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') paper workflow started"

if [[ -f ".env.paper-review" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.paper-review"
  set +a
fi

# score_papers.py talks to the same inference endpoint as the CC launcher. Keep
# the key in its existing owner file instead of copying it into another secret.
CCC_CMD="${CLAUDE_REVIEW_CMD:-/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/ccc}"
if [[ -z "${INF_API_KEY:-}" && -f "$CCC_CMD" ]]; then
  INF_API_KEY="$(sed -n 's/^export INF_API_KEY="\([^"]*\)".*/\1/p' "$CCC_CMD" | head -1)"
  export INF_API_KEY
fi
if [[ -z "${INF_API_KEY:-}" ]]; then
  echo "Error: INF_API_KEY is unavailable" >&2
  exit 1
fi

python3 scripts/scrape_papers.py

target_date="${1:-}"
if [[ -z "$target_date" ]]; then
  target_date="$(find _papers -maxdepth 1 -type f -name '????-??-??.md' -printf '%f\n' \
    | sed 's/\.md$//' | sort | tail -1)"
fi
if [[ -z "$target_date" ]]; then
  echo "Error: no daily paper file was produced" >&2
  exit 1
fi

score_ok=0
for attempt in 1 2 3; do
  if python3 scripts/score_papers.py "$target_date"; then
    score_ok=1
    break
  fi
  echo "Score pass $attempt/3 failed for $target_date" >&2
  [[ "$attempt" -lt 3 ]] && sleep 60
done
if [[ "$score_ok" -ne 1 ]]; then
  echo "Error: scoring did not complete after 3 passes" >&2
  exit 1
fi

args=(--date "$target_date" --no-scrape --push)
[[ -n "${PAPER_REVIEW_MAX:-}" ]] && args+=(--max "$PAPER_REVIEW_MAX")
if [[ "${CLAUDE_REVIEW_MODEL:-}" != "" ]]; then
  args+=(--model "$CLAUDE_REVIEW_MODEL")
fi

review_ok=0
for attempt in 1 2 3; do
  if python3 scripts/claude_review_papers_direct.py "${args[@]}"; then
    review_ok=1
    break
  fi
  echo "Review pass $attempt/3 failed for $target_date" >&2
  [[ "$attempt" -lt 3 ]] && sleep 60
done
if [[ "$review_ok" -ne 1 ]]; then
  echo "Error: review did not complete after 3 passes" >&2
  exit 1
fi

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') paper workflow completed for $target_date"
