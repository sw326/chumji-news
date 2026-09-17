#!/bin/bash
# Text-only summarization adapter preserving the production OpenClaw invocation contract.
# Models are tried in order; a later model runs only when the earlier call fails.
set -euo pipefail

PROMPT_FILE="${1:?prompt file is required}"
LOG_FILE="${2:?log file is required}"
JOB_TAG="${3:-news}"
OPENCLAW_BIN="${OPENCLAW_BIN:-/opt/homebrew/bin/openclaw}"
JQ_BIN="${JQ_BIN:-/opt/homebrew/bin/jq}"
MODEL="${OPENCLAW_MODEL:-openai/gpt-5.6-luna}"
FALLBACK_MODELS="${OPENCLAW_FALLBACK_MODELS-anthropic/claude-haiku-4-5}"

[[ -r "$PROMPT_FILE" ]] || { printf 'prompt file is not readable: %s\n' "$PROMPT_FILE" >>"$LOG_FILE"; exit 1; }
SAFE_TAG=$(printf '%s' "$JOB_TAG" | tr -cd '[:alnum:]_-')
[[ -n "$SAFE_TAG" ]] || SAFE_TAG="news"
RESULT_FILE=$(mktemp)
OUTPUT_FILE=$(mktemp)
trap 'rm -f "$RESULT_FILE" "$OUTPUT_FILE"' EXIT

summarize_with() {
  local model="$1" attempt="$2"
  local session_key="agent:main:cron-${SAFE_TAG}-$(date +%Y%m%dT%H%M%S)-$$-${attempt}"
  : >"$RESULT_FILE"
  "$OPENCLAW_BIN" agent --agent main --session-key "$session_key" --model "$model" \
    --message-file "$PROMPT_FILE" --thinking off --timeout 900 --json \
    >"$RESULT_FILE" 2>>"$LOG_FILE" || return 1
  "$JQ_BIN" -er '
    if .status != "ok" then error("OpenClaw agent status: " + (.status // "unknown"))
    else [.result.payloads[]?.text // empty] | join("\n") | select(length > 0) end
  ' "$RESULT_FILE" >"$OUTPUT_FILE" 2>>"$LOG_FILE" || return 1
}

ATTEMPT=0
set -f  # model ids are split on spaces only, never globbed
for CANDIDATE in "$MODEL" $FALLBACK_MODELS; do
  ATTEMPT=$((ATTEMPT + 1))
  if summarize_with "$CANDIDATE" "$ATTEMPT"; then
    (( ATTEMPT == 1 )) || printf '[%s] summarized with fallback model: %s\n' \
      "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$CANDIDATE" >>"$LOG_FILE"
    cat "$OUTPUT_FILE"
    exit 0
  fi
  printf '[%s] summarize failed with model: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$CANDIDATE" >>"$LOG_FILE"
done
exit 1
