#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/iHateTheWorld555.github.io"
cd "$REPO_ROOT"

if [[ -f ".env.paper-review" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.paper-review"
  set +a
fi

args=()
if [[ "${1:-}" != "" ]]; then
  args+=(--date "$1")
fi

if [[ "${PAPER_REVIEW_MAX:-}" != "" ]]; then
  args+=(--max "$PAPER_REVIEW_MAX")
fi

if [[ "${CLAUDE_REVIEW_MODEL:-}" != "" ]]; then
  args+=(--model "$CLAUDE_REVIEW_MODEL")
fi

python scripts/claude_review_papers_direct.py "${args[@]}" --scrape --push
