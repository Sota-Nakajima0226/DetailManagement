#!/usr/bin/env bash
# 開発用: FastAPI バックエンドと Flutter Web フロントを起動する。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11

BACKEND_PORT="${BACKEND_PORT:-8000}"
# 同一 LAN からアクセスするには 0.0.0.0。ローカルのみにしたいときは 127.0.0.1
BACKEND_BIND_HOST="${BACKEND_BIND_HOST:-0.0.0.0}"

WEB_PORT="${WEB_PORT:-8080}"
WEB_BIND_HOST="${WEB_BIND_HOST:-0.0.0.0}"
# スマホ確認は web-server（既定）。従来どおり PC の Chrome だけなら FLUTTER_DEVICE=chrome
FLUTTER_DEVICE="${FLUTTER_DEVICE:-web-server}"

detect_lan_host() {
  local os
  os="$(uname -s)"
  if [[ "$os" == "Darwin" ]]; then
    ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
  elif [[ "$os" == "Linux" ]]; then
    hostname -I 2>/dev/null | awk '{print $1; exit}' || true
  fi
}

LAN_HOST="${LAN_HOST:-$(detect_lan_host)}"
if [[ -z "$LAN_HOST" ]]; then
  LAN_HOST="127.0.0.1"
  echo "警告: LAN の IP を自動検出できませんでした。スマホから繋ぐ場合は LAN_HOST=（PC の IP）を指定してください。" >&2
fi

# スマホのブラウザから API を呼ぶには、ループバックではなく PC の LAN IP が必要
API_BASE_URL="${API_BASE_URL:-http://$LAN_HOST:$BACKEND_PORT}"

# Flutter 用 Supabase（frontend/.env または環境変数）
if [[ -f "$FRONTEND_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$FRONTEND_DIR/.env"
  set +a
fi

load_flutter_env() {
  if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_ANON_KEY:-}" ]]; then
    echo "エラー: SUPABASE_URL と SUPABASE_ANON_KEY が未設定です。" >&2
    echo "  frontend/.env.example を frontend/.env にコピーして設定するか、環境変数で export してください。" >&2
    exit 1
  fi
}

flutter_dart_defines() {
  echo "--dart-define=API_BASE_URL=${API_BASE_URL}"
  echo "--dart-define=SUPABASE_URL=${SUPABASE_URL}"
  echo "--dart-define=SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}"
}

activate_venv() {
  local v
  for v in "$BACKEND_DIR/.venv" "$BACKEND_DIR/venv" "$REPO_ROOT/.venv"; do
    if [[ -f "$v/bin/activate" ]]; then
      # shellcheck source=/dev/null
      source "$v/bin/activate"
      return 0
    fi
  done
  return 1
}

ensure_python_version() {
  python - <<PY
import sys

required = ($REQUIRED_PYTHON_MAJOR, $REQUIRED_PYTHON_MINOR)
actual = sys.version_info[:2]
if actual != required:
    raise SystemExit(
        f"Python {required[0]}.{required[1]} is required, "
        f"but current interpreter is {sys.version.split()[0]} ({sys.executable}). "
        "Recreate backend/.venv with: cd backend && python3.11 -m venv .venv"
    )
PY
}

# $1 = yes のときだけフロントの URL を表示（backend 単体起動では誤解を避ける）
print_dev_urls() {
  local with_flutter="${1:-no}"
  echo "" >&2
  echo "---- 同一 WiFi 内の端末 ----" >&2
  echo "  API（確認）: http://${LAN_HOST}:${BACKEND_PORT}/health" >&2
  if [[ "$with_flutter" == "yes" ]]; then
    if [[ "$FLUTTER_DEVICE" == "web-server" ]]; then
      echo "  フロント（スマホ等）: http://${LAN_HOST}:${WEB_PORT}" >&2
      echo "  フロント（この PC）: http://127.0.0.1:${WEB_PORT}" >&2
    else
      echo "  フロント: デバイス「${FLUTTER_DEVICE}」（例: Chrome が自動で開く）" >&2
    fi
  fi
  echo "  API ベース（フロントに埋め込み）: ${API_BASE_URL}" >&2
  echo "" >&2
}

wait_for_backend() {
  local i pid="$1"
  for i in $(seq 1 50); do
    if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null; then
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "バックエンドが起動に失敗しました（プロセスが終了しています）。" >&2
      return 1
    fi
    sleep 0.1
  done
  echo "バックエンドの起動待ちがタイムアウトしました。" >&2
  return 1
}

run_backend() {
  cd "$BACKEND_DIR"
  activate_venv || true
  ensure_python_version
  print_dev_urls no
  exec python -m uvicorn main:app --reload --host "$BACKEND_BIND_HOST" --port "$BACKEND_PORT"
}

run_frontend() {
  cd "$FRONTEND_DIR"
  load_flutter_env
  print_dev_urls yes
  # shellcheck disable=SC2046
  if [[ "$FLUTTER_DEVICE" == "web-server" ]]; then
    exec flutter run -d web-server \
      --web-hostname="$WEB_BIND_HOST" \
      --web-port="$WEB_PORT" \
      $(flutter_dart_defines)
  else
    exec flutter run -d "$FLUTTER_DEVICE" $(flutter_dart_defines)
  fi
}

run_all() {
  local backend_pid

  cd "$BACKEND_DIR"
  activate_venv || true
  ensure_python_version
  python -m uvicorn main:app --reload --host "$BACKEND_BIND_HOST" --port "$BACKEND_PORT" &
  backend_pid=$!

  cleanup() {
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  wait_for_backend "$backend_pid"
  print_dev_urls yes

  cd "$FRONTEND_DIR"
  load_flutter_env
  # shellcheck disable=SC2046
  if [[ "$FLUTTER_DEVICE" == "web-server" ]]; then
    flutter run -d web-server \
      --web-hostname="$WEB_BIND_HOST" \
      --web-port="$WEB_PORT" \
      $(flutter_dart_defines)
  else
    flutter run -d "$FLUTTER_DEVICE" $(flutter_dart_defines)
  fi
}

usage() {
  cat <<EOF
使い方: $(basename "$0") [backend|frontend|all]

  backend   FastAPI（uvicorn）を ${BACKEND_BIND_HOST}:${BACKEND_PORT} で待受（LAN からは http://${LAN_HOST}:${BACKEND_PORT}）
  frontend  Flutter Web を起動（既定: web-server → 同一 WiFi から http://${LAN_HOST}:${WEB_PORT}）
  all       バックエンドをバックグラウンドで起動してからフロントを起動

環境変数:
  BACKEND_PORT       バックエンドのポート（既定: 8000）
  BACKEND_BIND_HOST  uvicorn の待受アドレス（既定: 0.0.0.0 = LAN から到達可）
  WEB_PORT           Flutter web-server のポート（既定: 8080）
  WEB_BIND_HOST      Flutter web-server の待受（既定: 0.0.0.0）
  LAN_HOST           PC の LAN IP（未指定時は macOS/Linux で自動検出。API_BASE_URL の既定に使う）
  API_BASE_URL       フロントに埋め込む API のベース URL（既定: http://\$LAN_HOST:\$BACKEND_PORT）
  SUPABASE_URL       Supabase Project URL（frontend/.env でも可）
  SUPABASE_ANON_KEY  Supabase anon public キー（frontend/.env でも可）
  FLUTTER_DEVICE     flutter run -d のデバイス（既定: web-server。PC の Chrome だけなら chrome）

前提:
  - バックエンドは backend/.env に DATABASE_URL 等が必要な場合があります
  - バックエンドの Python は 3.11 固定です（backend/.venv は python3.11 で作成してください）
  - Python 仮想環境は backend/.venv / backend/venv / リポジトリ直下 .venv を自動で有効化します
  - フロント起動時は frontend/.env に SUPABASE_URL / SUPABASE_ANON_KEY が必要です（.env.example 参照）

Flutter（frontend / all）:
  - Dart を編集したあと、ブラウザの再読み込みだけでは不十分なことがあります。flutter run 中のターミナルで r（ホットリロード）か R（ホットリスタート）を押してください。
  - エディタの「保存時にホットリロード」設定にすると、ブラウザ操作なしで反映できます。
EOF
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    backend) run_backend ;;
    frontend) run_frontend ;;
    all) run_all ;;
    -h | --help | help | "")
      usage
      exit 0
      ;;
    *)
      echo "不明な引数: $cmd" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
