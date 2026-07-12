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

REVIEW_PROVIDER="${CLAUDE_REVIEW_PROVIDER:-glm52}"

python3 scripts/scrape_papers.py

if [[ -n "${1:-}" ]]; then
  target_dates=("$1")
else
  lookback_days="${PAPER_SCRAPE_LOOKBACK_DAYS:-7}"
  cutoff="$(date -u -d "$lookback_days days ago" +%Y-%m-%d)"
  mapfile -t target_dates < <(
    find _papers -maxdepth 1 -type f -name '????-??-??.md' -printf '%f\n' \
      | sed 's/\.md$//' | awk -v cutoff="$cutoff" '$0 >= cutoff' | sort -r
  )
fi
if [[ "${#target_dates[@]}" -eq 0 ]]; then
  echo "Error: no daily paper file was produced" >&2
  exit 1
fi

for target_date in "${target_dates[@]}"; do
  echo "Processing paper date $target_date"
  args=(--date "$target_date" --no-scrape --push --provider "$REVIEW_PROVIDER")
  [[ -n "${PAPER_REVIEW_MAX:-}" ]] && args+=(--max "$PAPER_REVIEW_MAX")
  [[ -n "${CLAUDE_REVIEW_MODEL:-}" ]] && args+=(--model "$CLAUDE_REVIEW_MODEL")

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
done

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') paper workflow completed for ${target_dates[*]}"
