#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PYTHON="${FRESH_PRICE_PYTHON:-/opt/homebrew/bin/python3}"
NODE="${FRESH_PRICE_NODE:-/opt/homebrew/bin/node}"
VERCEL="${FRESH_PRICE_VERCEL:-$(command -v vercel || true)}"
OUTPUT_ROOT="${FRESH_PRICE_OUTPUT_ROOT:-$HOME/Library/Application Support/chumji-news/price-snapshots}"
DATA_KEY_FILE="${FRESH_PRICE_DATA_KEY_FILE:-$HOME/.config/data-go-kr/api_key}"
GARAK_PASSWORD_FILE="${FRESH_PRICE_GARAK_PASSWORD_FILE:-$HOME/.openclaw/secrets/garak-publicdata-passwd}"
APP_ENV_FILE="${FRESH_PRICE_APP_ENV_FILE:-$HOME/workspace/chumji-news/.env.local}"
VERCEL_PROJECT_FILE="${FRESH_PRICE_VERCEL_PROJECT_FILE:-$HOME/workspace/chumji-news/.vercel/project.json}"
TELEGRAM_TOKEN_FILE="${FRESH_PRICE_TELEGRAM_TOKEN_FILE:-$HOME/.openclaw/secrets/telegram-macmini-bot-token}"
TELEGRAM_CHAT_ID="${FRESH_PRICE_TELEGRAM_CHAT_ID:-7800641846}"
PUBLIC_URL="${FRESH_PRICE_PUBLIC_URL:-https://chumji-news.vercel.app}"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--dry-run]" >&2
  exit 2
fi

for required in "$DATA_KEY_FILE" "$GARAK_PASSWORD_FILE"; do
  [[ -s "$required" ]] || { echo "missing required SecretRef: $required" >&2; exit 1; }
done

run_date="$(TZ=Asia/Seoul date +%F)"
run_root="$OUTPUT_ROOT/$run_date"
mkdir -p "$run_root"

"$PYTHON" -B "$ROOT/operations/jobs/fresh-food/run_shadow.py" \
  --output-root "$OUTPUT_ROOT" \
  --data-key-file "$DATA_KEY_FILE" \
  --garak-password-file "$GARAK_PASSWORD_FILE"

status_file="$run_root/shadow-status.json"
report_file="$run_root/report.json"
snapshot_file="$($PYTHON - "$status_file" <<'PY'
import json, pathlib, sys
status = json.loads(pathlib.Path(sys.argv[1]).read_text())
missing = status.get("missing_items") or []
if status.get("collector_exit_code") != 0 or status.get("error_count") != 0 or missing:
    raise SystemExit(f"price snapshot validation failed: errors={status.get('error_count')} missing={missing}")
print(status["snapshot_path"])
PY
)"
snapshot_date="$($PYTHON - "$report_file" <<'PY'
import json, pathlib, re, sys
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
match = re.match(r"(\d{4}-\d{2}-\d{2})", str(report.get("generatedAt", "")))
if not match:
    raise SystemExit("report has no valid generatedAt date")
print(match.group(1))
PY
)"

stage="$(mktemp -d /tmp/chumji-news-price-deploy.XXXXXX)"
cleanup() { rm -rf "$stage"; }
trap cleanup EXIT
if [[ -e "$ROOT/.git" ]]; then
  # Checkouts use committed bytes only; broken Git metadata must fail closed.
  git -C "$ROOT" archive HEAD | tar -x -C "$stage"
else
  # Immutable releases are git archives themselves and have no .git metadata.
  tar -C "$ROOT" --exclude='.git' --exclude='.env*' --exclude='.vercel' \
    --exclude='node_modules' --exclude='.next' --exclude='__pycache__' \
    --exclude='*.pyc' -cf - . | tar -x -C "$stage"
fi
mkdir -p "$stage/public/fresh-food/$snapshot_date"
cp "$snapshot_file" "$stage/public/fresh-food/index.html"
cp "$snapshot_file" "$stage/public/fresh-food/$snapshot_date/index.html"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "validated price snapshot: $snapshot_date"
  echo "dry-run: publication disabled"
  exit 0
fi

[[ -n "$VERCEL" && -x "$VERCEL" ]] || { echo "missing Vercel CLI" >&2; exit 1; }
[[ -s "$VERCEL_PROJECT_FILE" ]] || { echo "missing Vercel project reference: $VERCEL_PROJECT_FILE" >&2; exit 1; }
mkdir -p "$stage/.vercel"
cp "$VERCEL_PROJECT_FILE" "$stage/.vercel/project.json"
(
  cd "$stage"
  "$VERCEL" deploy --prod --yes
)
curl -fsS --max-time 30 "$PUBLIC_URL/prices/$snapshot_date" >/dev/null

[[ -s "$APP_ENV_FILE" ]] || { echo "missing application SecretRef: $APP_ENV_FILE" >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "$APP_ENV_FILE"
set +a
"$NODE" "$ROOT/scripts/save-price-snapshot.js" "$report_file"

[[ -s "$TELEGRAM_TOKEN_FILE" ]] || { echo "missing Telegram SecretRef: $TELEGRAM_TOKEN_FILE" >&2; exit 1; }
# Read the token inside the HTTP client, never into shell expansion or argv.
"$PYTHON" - "$TELEGRAM_TOKEN_FILE" "$TELEGRAM_CHAT_ID" "$snapshot_date" "$PUBLIC_URL" <<'PY_SEND'
import json
import pathlib
import sys
import urllib.parse
import urllib.request

token_file, chat_id, date, public_url = sys.argv[1:]
message = f"신선식품 가격 - {date}\n가락시장 최신 도매 + KAMIS 소매 조사\n그래프 보기: {public_url}/prices/{date}"
try:
    token = pathlib.Path(token_file).read_text().strip()
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise ValueError("Telegram rejected publication")
except Exception:
    raise SystemExit("Telegram publication failed; response details suppressed") from None
print(f"price snapshot publication complete: message_id={result['result']['message_id']}")
PY_SEND
