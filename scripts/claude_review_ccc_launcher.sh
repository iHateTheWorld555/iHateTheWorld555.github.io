#!/usr/bin/env bash
set -euo pipefail

# SDK-compatible ccc launcher.
# The normal ccc script cd's into claude-code-free before launching Claude Code.
# For SDK automation we must preserve the caller cwd so transcripts and project
# memory are scoped to this repository.

CCC_CMD="${CLAUDE_REVIEW_CMD:-/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/ccc}"
CC_DIR="${CLAUDE_REVIEW_CC_DIR:-/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/claude-code-free}"
CC_SETUP_DIR="${CLAUDE_REVIEW_CC_SETUP_DIR:-/inspire/qb-ilm/project/video-generation/chenxie-25019/hyr/cc-setup}"

unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

BUN=""
for candidate in \
  "$CC_SETUP_DIR/bun/bun" \
  "$(command -v bun 2>/dev/null || true)" \
  "$HOME/.bun/bin/bun"; do
  if [[ -x "$candidate" ]]; then
    BUN="$candidate"
    break
  fi
done

if [[ -z "$BUN" ]]; then
  echo "Error: bun not found. Expected at $CC_SETUP_DIR/bun/bun" >&2
  exit 1
fi

ENV_FILE="${CC_ENV_FILE:-${ENV_FILE:-$HOME/.env.local}}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

provider="${1:-glm51ascend}"
case "$provider" in
  glm51ascend)
    shift || true
    INF_BASE_URL="${INF_BASE_URL:-https://9obb5eeg99okcgjmhmh8kp5ekqj5ejeh.openapi-sj.sii.edu.cn}"
    OPENAI_CONTEXT_WINDOW="${OPENAI_CONTEXT_WINDOW:-202752}"
    ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-glm5.1-w4a8}"
    ;;
  glm52|glm-5.2|glm52ascend)
    shift || true
    INF_API_KEY="${INF_API_KEY:-PXD1xpmXaRQthNTPHJZJYv0nMl3YBcf/mDZJ+dg2lU8=}"
    INF_BASE_URL="${INF_BASE_URL:-https://kkdam8deopmhch9cjd8qoghcpjdhh8ch.openapi-sj.sii.edu.cn}"
    OPENAI_CONTEXT_WINDOW="${OPENAI_CONTEXT_WINDOW:-200000}"
    ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-GLM-5.2-w4a8}"
    export CLAUDE_CODE_SUBAGENT_MODEL="${CLAUDE_CODE_SUBAGENT_MODEL:-GLM-5.2-w4a8}"
    ;;
  *)
    echo "Error: claude_review_ccc_launcher.sh only supports glm51ascend/glm52, got '$provider'" >&2
    exit 1
    ;;
esac

if [[ -z "${INF_API_KEY:-}" && -f "$CCC_CMD" ]]; then
  INF_API_KEY="$(sed -n 's/^export INF_API_KEY="\([^"]*\)".*/\1/p' "$CCC_CMD" | head -1)"
fi
if [[ -z "${INF_API_KEY:-}" ]]; then
  echo "Error: INF_API_KEY not set and could not be read from $CCC_CMD" >&2
  exit 1
fi

export OPENAI_API_KEY="$INF_API_KEY"
export OPENAI_BASE_URL="$INF_BASE_URL/v1"
export OPENAI_CONTEXT_WINDOW
export ANTHROPIC_MODEL
export CLAUDE_CODE_SUBAGENT_MODEL="${CLAUDE_CODE_SUBAGENT_MODEL:-$ANTHROPIC_MODEL}"
export API_TIMEOUT_MS="${API_TIMEOUT_MS:-3000000}"
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN

exec "$BUN" run "$CC_DIR/src/dev-entry.ts" -- "$@"
