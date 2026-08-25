#!/bin/bash
# Text-only GPT adapter preserving the production OpenClaw invocation contract.
set -euo pipefail

PROMPT_FILE="${1:?prompt file is required}"
LOG_FILE="${2:?log file is required}"
JOB_TAG="${3:-news}"
OPENCLAW_BIN="${OPENCLAW_BIN:-/opt/homebrew/bin/openclaw}"
JQ_BIN="${JQ_BIN:-/opt/homebrew/bin/jq}"
MODEL="${OPENCLAW_MODEL:-openai/gpt-5.5}"

[[ -r "$PROMPT_FILE" ]] || { printf 'prompt file is not readable: %s\n' "$PROMPT_FILE" >>"$LOG_FILE"; exit 1; }
SAFE_TAG=$(printf '%s' "$JOB_TAG" | tr -cd '[:alnum:]_-')
[[ -n "$SAFE_TAG" ]] || SAFE_TAG="news"
RESULT_FILE=$(mktemp)
trap 'rm -f "$RESULT_FILE"' EXIT

SESSION_KEY="agent:main:cron-${SAFE_TAG}-$(date +%Y%m%dT%H%M%S)-$$"
"$OPENCLAW_BIN" agent --agent main --session-key "$SESSION_KEY" --model "$MODEL" \
  --message-file "$PROMPT_FILE" --thinking off --timeout 900 --json \
  >"$RESULT_FILE" 2>>"$LOG_FILE"

"$JQ_BIN" -er '
  if .status != "ok" then error("OpenClaw agent status: " + (.status // "unknown"))
  else [.result.payloads[]?.text // empty] | join("\n") | select(length > 0) end
' "$RESULT_FILE" 2>>"$LOG_FILE"
