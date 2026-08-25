#!/bin/bash
# Surviving news pipeline entrypoint. Publication requires explicit --publish.
set -euo pipefail

PROFILE="${1:-}"
MODE="${2:---dry-run}"
case "$PROFILE" in
  morning) FETCHER="fetch_morning_news.py"; CATEGORY="news"; TAG="morning-news"; MIN_CHARS=800 ;;
  it) FETCHER="fetch_it_tech.py"; CATEGORY="it"; TAG="it-tech"; MIN_CHARS=800 ;;
  trend) FETCHER="fetch_trends.py"; CATEGORY="trend"; TAG="trend"; MIN_CHARS=200 ;;
  *) printf 'usage: %s {morning|it|trend} [--dry-run|--publish]\n' "$0" >&2; exit 2 ;;
esac
[[ "$MODE" == "--dry-run" || "$MODE" == "--publish" ]] || { printf 'invalid mode: %s\n' "$MODE" >&2; exit 2; }

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LOG_DIR="${CHUMJI_NEWS_LOG_DIR:-$HOME/.cache/cron-chumji-news}"
RECEIPT_DIR="${CHUMJI_NEWS_RECEIPT_DIR:-$HOME/.local/state/chumji-news/publication-receipts}"
SUPABASE_ENV="${CHUMJI_NEWS_SUPABASE_ENV:-$HOME/.config/supabase/chumji-news.env}"
TELEGRAM_TOKEN_FILE="${CHUMJI_NEWS_TELEGRAM_TOKEN_FILE:-$HOME/.openclaw/secrets/telegram-macmini-bot-token}"
TELEGRAM_CHAT_ID="${CHUMJI_NEWS_TELEGRAM_CHAT_ID:--5290748342}"
WEB_BASE="${CHUMJI_NEWS_WEB_BASE:-https://chumji-news.vercel.app}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$TAG.log"
RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/chumji-news-$TAG.XXXXXX")
trap 'rm -rf "$RUN_DIR"' EXIT

if [[ "$PROFILE" == trend ]]; then
  python3 "$ROOT/$FETCHER" --audit-dir "$LOG_DIR/trend-audit" >"$RUN_DIR/source.json" 2>>"$LOG_FILE"
else
  python3 "$ROOT/$FETCHER" >"$RUN_DIR/source.json" 2>>"$LOG_FILE"
fi

TODAY=$(TZ=Asia/Seoul date +%Y-%m-%d)
DATE_KOR=$(TZ=Asia/Seoul date '+%Y.%m.%d (%a)' | sed \
  -e 's/Mon/월/' -e 's/Tue/화/' -e 's/Wed/수/' -e 's/Thu/목/' \
  -e 's/Fri/금/' -e 's/Sat/토/' -e 's/Sun/일/')
python3 "$ROOT/build_prompt.py" --profile "$PROFILE" --date-kor "$DATE_KOR" \
  --input "$RUN_DIR/source.json" --output "$RUN_DIR/prompt.txt"
"$ROOT/adapters/openclaw_gpt_summarize.sh" "$RUN_DIR/prompt.txt" "$LOG_FILE" "$TAG" >"$RUN_DIR/briefing.md"

BRIEFING_CHARS=$(python3 -c 'from pathlib import Path; import sys; print(len(Path(sys.argv[1]).read_text()))' "$RUN_DIR/briefing.md")
(( BRIEFING_CHARS >= MIN_CHARS )) || { printf 'briefing too short: %s\n' "$BRIEFING_CHARS" >&2; exit 1; }
if grep -Eq '데이터 품질 문제|브리핑 생성 불가|정상 생성이 불가능|공식 브리핑 출력 불가' "$RUN_DIR/briefing.md"; then
  printf 'briefing contains a failure page\n' >&2
  exit 1
fi

if [[ "$MODE" == "--dry-run" ]]; then
  python3 - "$PROFILE" "$CATEGORY" "$TODAY" "$RUN_DIR/briefing.md" <<'PY'
from pathlib import Path
import json, re, sys
text = Path(sys.argv[4]).read_text()
print(json.dumps({"profile": sys.argv[1], "category": sys.argv[2], "date": sys.argv[3],
                  "chars": len(text), "first_line": text.splitlines()[0],
                  "links": len(re.findall(r"\[[^]]+\]\(https?://", text))}, ensure_ascii=False))
PY
  exit 0
fi

[[ -r "$SUPABASE_ENV" ]] || { printf 'missing Supabase env file\n' >&2; exit 1; }
[[ -r "$TELEGRAM_TOKEN_FILE" ]] || { printf 'missing Telegram token file\n' >&2; exit 1; }
set -a
# shellcheck disable=SC1090
. "$SUPABASE_ENV"
set +a
: "${NEXT_PUBLIC_SUPABASE_URL:?missing NEXT_PUBLIC_SUPABASE_URL}"
: "${SUPABASE_SERVICE_ROLE_KEY:?missing SUPABASE_SERVICE_ROLE_KEY}"
umask 077
printf '%s' "$SUPABASE_SERVICE_ROLE_KEY" >"$RUN_DIR/supabase.key"
printf '%s' "$TELEGRAM_CHAT_ID" >"$RUN_DIR/telegram-chat-id"
python3 "$ROOT/adapters/publish.py" --date "$TODAY" --category "$CATEGORY" \
  --briefing-file "$RUN_DIR/briefing.md" --supabase-url "$NEXT_PUBLIC_SUPABASE_URL" \
  --supabase-key-file "$RUN_DIR/supabase.key" --telegram-token-file "$TELEGRAM_TOKEN_FILE" \
  --telegram-chat-id-file "$RUN_DIR/telegram-chat-id" --receipt-dir "$RECEIPT_DIR" --web-base "$WEB_BASE"
