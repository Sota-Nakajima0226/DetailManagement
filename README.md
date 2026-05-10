# DetailManagement

家族向け家計管理アプリのモノレポです。フロントは Flutter Web（PWA）、API は FastAPI、データストアは PostgreSQL（例: Supabase）を想定しています。

詳細な要件・設計はリポジトリ直下の  `docs/` を参照してください。

## 前提環境

- **Python** 3 系（バックエンド）
- **Flutter** SDK（フロント; Web ビルド用）
- **PostgreSQL**（API が DB に接続する機能を使う場合）
- **bash**（起動スクリプト用）

## 初回セットアップ

### バックエンド

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows は .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env の DATABASE_URL などを環境に合わせて編集
```

DB スキーマを使う場合は `backend` をカレントにしてマイグレーションを適用します。

```bash
cd backend
python -m alembic upgrade head
```

### フロントエンド

```bash
cd frontend
flutter pub get
```

Web 用の `web/` がまだない場合は、`frontend` 内で `flutter create . --platforms=web` などで追加できます。

## 起動方法（開発）

リポジトリ直下から `scripts/dev.sh` を使います。

```bash
# API とフロントの両方（推奨）
./scripts/dev.sh all

# API のみ
./scripts/dev.sh backend

# フロントのみ（別ターミナルで API が既に動いている場合など）
./scripts/dev.sh frontend
```

起動後、ターミナルに **API のヘルスチェック URL** と **フロントの URL** が表示されます。ヘルプは次のとおりです。

```bash
./scripts/dev.sh --help
```

### 動作確認

- API: 表示された URL の `/health`（例: `http://127.0.0.1:8000/health`）
- フロント（既定）: `web-server` モードのため、PC では `http://127.0.0.1:8080` をブラウザで開きます（ポートは環境変数で変更可）。

### 同一 WiFi のスマホから開く

既定で API・Flutter の待受は `0.0.0.0` です。PC の LAN IP が自動検出され、`API_BASE_URL` に埋め込まれます。スマホのブラウザで、ターミナルに出た **フロントの URL**（`http://（開発 PC の LAN IP）:8080` など）を開いてください。

IP が誤る場合（VPN など）は PC の IP を明示します（下記の `REPLACE_WITH_YOUR_PC_LAN_IP` はプレースホルダです。実際のアドレスに置き換えてください）。

```bash
LAN_HOST='REPLACE_WITH_YOUR_PC_LAN_IP' ./scripts/dev.sh all
```

### PC の Chrome だけで開発したい場合

```bash
FLUTTER_DEVICE=chrome ./scripts/dev.sh all
```

この場合、スマホからフロント URL には繋がりません。

### 環境変数（`dev.sh`）

| 変数 | 説明 | 既定値 |
|------|------|--------|
| `BACKEND_PORT` | API ポート | `8000` |
| `BACKEND_BIND_HOST` | uvicorn の待受アドレス | `0.0.0.0` |
| `WEB_PORT` | Flutter web-server のポート | `8080` |
| `WEB_BIND_HOST` | Flutter web-server の待受 | `0.0.0.0` |
| `LAN_HOST` | PC の LAN IP（API をフロントに渡す用途） | OS から自動検出 |
| `API_BASE_URL` | フロントに埋め込む API のベース URL | `http://<LAN_HOST>:<BACKEND_PORT>` |
| `FLUTTER_DEVICE` | `flutter run -d` のデバイス | `web-server` |

ローカルだけに閉じたい場合は `BACKEND_BIND_HOST=127.0.0.1` などにしてください。

## 開発時のメモ

- **バックエンド**: `uvicorn` は `--reload` のため、Python ファイル保存後に自動で再起動します。
- **フロント**: Dart 変更後はブラウザの再読み込みだけでは足りないことがあります。`flutter run` を実行しているターミナルで **`r`（ホットリロード）** または **`R`（ホットリスタート）** を押してください。エディタの「保存時にホットリロード」も利用できます。

## 手動起動（スクリプトを使わない場合）

```bash
# ターミナル 1
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ターミナル 2
cd frontend
flutter run -d web-server --web-hostname 0.0.0.0 --web-port 8080 \
  --dart-define=API_BASE_URL=http://REPLACE_WITH_YOUR_PC_LAN_IP:8000
```

（`REPLACE_WITH_YOUR_PC_LAN_IP` はプレースホルダです。開発 PC の LAN 上の IP に置き換えてください。）

機密値はリポジトリに含めず、`.env`（コミット対象は `.env.example` のみ）で管理してください。
