#!/usr/bin/env bash
# 開発用: FastAPI バックエンドと Flutter Web フロントを起動する。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:$BACKEND_PORT}"

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
  exec python3 -m uvicorn main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT"
}

run_frontend() {
  cd "$FRONTEND_DIR"
  exec flutter run -d chrome --dart-define="API_BASE_URL=$API_BASE_URL"
}

run_all() {
  local backend_pid

  cd "$BACKEND_DIR"
  activate_venv || true
  python3 -m uvicorn main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" &
  backend_pid=$!

  cleanup() {
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  wait_for_backend "$backend_pid"

  cd "$FRONTEND_DIR"
  flutter run -d chrome --dart-define="API_BASE_URL=$API_BASE_URL"
}

usage() {
  cat <<EOF
使い方: $(basename "$0") [backend|frontend|all]

  backend   FastAPI（uvicorn）を http://127.0.0.1:${BACKEND_PORT} で起動
  frontend  Flutter Web（Chrome）を起動（API: ${API_BASE_URL}）
  all       バックエンドをバックグラウンドで起動してからフロントを起動

環境変数:
  BACKEND_PORT   バックエンドのポート（既定: 8000）
  API_BASE_URL   フロントが使う API のベース URL（既定: http://127.0.0.1:\$BACKEND_PORT）

前提:
  - バックエンドは backend/.env に DATABASE_URL 等が必要な場合があります
  - Python 仮想環境は backend/.venv / backend/venv / リポジトリ直下 .venv を自動で有効化します

Flutter（frontend / all）:
  - Dart を編集したあと、Chrome の再読み込みだけでは新しい JS に置き換わりません。flutter run 中のターミナルで r（ホットリロード）か R（ホットリスタート）を押してください。
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
