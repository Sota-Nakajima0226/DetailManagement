# DetailManagement

家族向け家計管理アプリのモノレポです。フロントは Flutter Web（PWA）、API は FastAPI、データストアは PostgreSQL（例: Supabase）を想定しています。

詳細な要件・設計はリポジトリ直下の  `docs/` を参照してください。

## 前提環境

- **Python** 3.11（バックエンド。`.python-version` / `runtime.txt` で固定）
- **Flutter** SDK（フロント; Web ビルド用）
- **PostgreSQL**（API が DB に接続する機能を使う場合）
- **bash**（起動スクリプト用）

## 初回セットアップ

### バックエンド

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate   # Windows は .venv\Scripts\activate
python --version             # Python 3.11.x であることを確認
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

### AI分類設定

| 変数 | 説明 | 既定値 |
|------|------|--------|
| `AI_CONFIDENCE_REVIEW_THRESHOLD` | AI分類済み明細を「要確認」として表示する信頼度しきい値 | `0.8` |

### 認証設定（Supabase Auth）

`/health` を除く全エンドポイントは `Authorization: Bearer <JWT>` を必須にしています。
dev / prod ともに Supabase Auth を使い、認証コードパスを完全に1本化しています（dev 専用バイパスは設けない方針）。

| 変数 | 説明 | 既定値 |
|------|------|--------|
| `SUPABASE_JWT_SECRET` | Supabase の JWT 秘密鍵（HS256 検証用、必須） | なし |
| `SUPABASE_JWT_AUDIENCE` | JWT の audience クレーム | `authenticated` |
| `SUPABASE_JWT_ALGORITHM` | 署名アルゴリズム | `HS256` |

#### 環境構築の流れ

1. Supabase で **dev 用プロジェクト**と**本番用プロジェクト**を別々に作成する。
2. 各プロジェクトの管理画面 *Project Settings → API → JWT Settings → JWT Secret* を `SUPABASE_JWT_SECRET` に設定する（`backend/.env` の値は dev 用、Render の環境変数に本番用）。
3. 夫・妻の 2 アカウントを各 Supabase プロジェクトで作成し、UUID を控える。
4. `users` テーブルに以下のような SQL でレコードを投入する（`role` は `owner` か `member`）。

   ```sql
   INSERT INTO users (id, email, role) VALUES
     ('<夫のUUID>', 'husband@example.com', 'owner'),
     ('<妻のUUID>', 'wife@example.com',    'member');
   ```

5. フロントは Supabase SDK でログインし、取得した JWT を `Authorization` ヘッダに載せて API を叩く。

`users` に未登録の UUID で来たリクエストは 403 になります。ユニットテストでは `app.dependency_overrides[get_current_user]` で固定ユーザーを注入してください（例: `backend/tests/test_auth.py`）。

### バックエンドログ

バックエンドは stdout と `backend/logs/app.log` に JSON 形式でログを出力します。ログファイルは既定で 10MB x 5世代でローテーションします。API アクセスログは既定で有効で、リクエスト・レスポンス body は出力しません。

| 変数 | 説明 | 既定値 |
|------|------|--------|
| `LOG_LEVEL` | Python ログレベル | `INFO` |
| `LOG_API_ACCESS` | API アクセスログの出力 | `true` |
| `LOG_FILE_ENABLED` | ログファイル出力 | `true` |
| `LOG_FILE_PATH` | ログファイルパス（backend からの相対パス） | `logs/app.log` |
| `LOG_FILE_MAX_BYTES` | ローテーションするファイルサイズ | `10485760` |
| `LOG_FILE_BACKUP_COUNT` | 保持するローテーション世代数 | `5` |
| `LOG_AI_CLASSIFICATION_DETAIL` | AI に渡した店名と分類結果の詳細ログを出力 | `false` |

`LOG_AI_CLASSIFICATION_DETAIL=true` は家計情報を含むログになるため、開発・調査時のみ有効にしてください。
`backend/logs/` 配下のログファイルは Git 管理対象外です。

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
