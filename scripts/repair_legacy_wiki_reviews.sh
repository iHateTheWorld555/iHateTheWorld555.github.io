#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REVIEW_PROVIDER="${CLAUDE_REVIEW_PROVIDER:-glm52}"
MAX_REPAIRS="${PAPER_REVIEW_WIKI_REPAIR_MAX:-0}"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

# These phrases were emitted before the isolated Claude profile registered the
# OMC wiki MCP server. A repaired review must disappear from this query.
STALE_PATTERN='wiki_query.*(不可用|未注册)|OMC.*(不可用|未注册)|wiki MCP.*(不可用|未注册)'

mapfile -t stale_reviews < <(
  rg -l "$STALE_PATTERN" _paper_reviews -g '*.md' 2>/dev/null | sort
)

if [[ "${#stale_reviews[@]}" -eq 0 ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') no legacy wiki reviews need repair"
  exit 0
fi

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') repairing ${#stale_reviews[@]} legacy wiki reviews"
processed=0
failed=0

for review_path in "${stale_reviews[@]}"; do
  if [[ "$MAX_REPAIRS" =~ ^[0-9]+$ ]] && (( MAX_REPAIRS > 0 && processed >= MAX_REPAIRS )); then
    echo "Reached PAPER_REVIEW_WIKI_REPAIR_MAX=$MAX_REPAIRS; remaining reviews stay queued"
    break
  fi

  review_date="$(basename "$(dirname "$review_path")")"
  arxiv_id="$(basename "$review_path" .md)"
  args=(
    --date "$review_date"
    --arxiv-id "$arxiv_id"
    --force
    --no-scrape
    --push
    --provider "$REVIEW_PROVIDER"
  )
  [[ -n "${CLAUDE_REVIEW_MODEL:-}" ]] && args+=(--model "$CLAUDE_REVIEW_MODEL")

  processed=$((processed + 1))
  repaired=0
  for attempt in 1 2; do
    echo "Repairing $arxiv_id ($review_date), attempt $attempt/2"
    if python3 scripts/claude_review_papers_direct.py "${args[@]}" \
      && ! rg -q "$STALE_PATTERN" "$review_path"; then
      repaired=1
      break
    fi
    echo "Repair attempt $attempt/2 failed for $arxiv_id" >&2
    [[ "$attempt" -lt 2 ]] && sleep 60
  done

  if [[ "$repaired" -ne 1 ]]; then
    failed=$((failed + 1))
  fi
done

remaining="$(rg -l "$STALE_PATTERN" _paper_reviews -g '*.md' 2>/dev/null | wc -l)"
echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') legacy wiki repair pass finished: processed=$processed failed=$failed remaining=$remaining"

# A failure is intentionally non-zero so the scheduler log/alert exposes it;
# successful reviews have already been committed, pushed, and remote-verified.
(( failed == 0 ))
