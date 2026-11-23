#!/usr/bin/env bash
# Render の Static Site 用。Flutter 3.29.2 を入れて frontend をビルドする。
# 必要な環境変数: API_BASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY
set -euo pipefail

FLUTTER_VERSION="3.29.2"

: "${API_BASE_URL:?API_BASE_URL is required}"
: "${SUPABASE_URL:?SUPABASE_URL is required}"
: "${SUPABASE_ANON_KEY:?SUPABASE_ANON_KEY is required}"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
sdk_dir="${HOME}/sdks/flutter-${FLUTTER_VERSION}"

if [[ ! -x "${sdk_dir}/bin/flutter" ]]; then
  mkdir -p "$(dirname "${sdk_dir}")"
  git clone --depth 1 --branch "${FLUTTER_VERSION}" https://github.com/flutter/flutter.git "${sdk_dir}"
fi

export PATH="${sdk_dir}/bin:${PATH}"
git config --global --add safe.directory "${sdk_dir}" || true
flutter config --no-analytics --enable-web >/dev/null
flutter precache --web

cd "${repo_root}/frontend"
flutter build web \
  --dart-define="API_BASE_URL=${API_BASE_URL}" \
  --dart-define="SUPABASE_URL=${SUPABASE_URL}" \
  --dart-define="SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}"
