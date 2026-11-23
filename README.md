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
cp .env.example .env
# .env に SUPABASE_URL / SUPABASE_ANON_KEY を設定（Project Settings → API）
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
| `SUPABASE_URL` | Supabase Project URL（`frontend/.env` でも可） | なし（未設定時はフロント起動エラー） |
| `SUPABASE_ANON_KEY` | Supabase anon public キー（`frontend/.env` でも可） | なし |
| `FLUTTER_DEVICE` | `flutter run -d` のデバイス | `web-server` |

ローカルだけに閉じたい場合は `BACKEND_BIND_HOST=127.0.0.1` などにしてください。

### フロントエンド認証（Supabase Auth）

- 起動時に Supabase でログイン。セッションは SDK が Web では `localStorage` に保持する。
- ログアウトは明細・グラフ画面の AppBar メニュー「ログアウト」。
- 手動起動例（`frontend/.env` 未使用時）:

```bash
cd frontend
flutter run -d web-server \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000 \
  --dart-define=SUPABASE_URL=https://your-project.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=your-anon-key
```

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

### LINE通知（明細メール）

明細案内メールが届いたら、未取込のカードだけグループへ取込手順を送ります。CSV の取込が成功したときも、同じグループへ完了を1通送ります。アプリは受信箱を見にいきません。Gmail 側の Apps Script が API を呼びます。

雛形は `scripts/apps_script/statement_mail.js` です。秘密は入れていません。動かす正本は、明細メールを受信する Gmail アカウントの Apps Script にコピーしたものです。公式アカウント、トークン、グループ ID、Apps Script、自分宛メールでの到達確認は [docs/notifications/line_setup.md](docs/notifications/line_setup.md) にまとめています。

#### 環境変数

値は Git に入れません。名前だけを置き、実値は Render とスクリプトプロパティに入れます。`backend/.env.example` にも同じ名前があります。

| 名前 | 置く場所 | 用途 |
|------|----------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Render | Messaging API のチャネルアクセストークン |
| `LINE_GROUP_ID` | Render | 送信先グループ ID |
| `APP_UPLOAD_URL` | Render | アップロード画面の基点。クエリ無しの `https://` だけ有効。形の例は `https://example.com/upload` |
| `REMIND_CRON_SECRET` | Render と Apps Script のスクリプトプロパティ | `POST /notify/statement-mail` の秘密鍵。ユーザー JWT とは別 |
| `NOTIFY_API_BASE_URL` | Apps Script のスクリプトプロパティ | API の基点。パスは付けない。形の例は `https://api.example.com` |

トークンかグループ ID が無いときは LINE を送らず、明細の取込 API は成功のままです。

#### 公式アカウントとグループ ID

1. [LINE Developers](https://developers.line.biz/) でプロバイダーと Messaging API チャネルを作る。
2. チャネルアクセストークン（長期）を発行し、Render の `LINE_CHANNEL_ACCESS_TOKEN` に入れる。
3. 公式アカウントを、夫婦とボットだけのグループへ招待する。
4. グループ ID は、ボット参加時の Webhook イベント `source.groupId` です。このアプリは Webhook を受けないので、Developers コンソールで Webhook を一時的に有効にし、届いたイベントから ID を控えます。控えた値は Render の `LINE_GROUP_ID` に入れ、Webhook URL は外してかまいません。
5. 通数はコミュニケーションプラン（月200通）を想定しています。

#### Apps Script

1. 受信する Gmail で Apps Script を新規作成し、`scripts/apps_script/statement_mail.js` の中身を貼る。
2. プロジェクトの設定でスクリプトプロパティ `REMIND_CRON_SECRET` と `NOTIFY_API_BASE_URL` を入れる。ソースには書かない。
3. `checkStatementMails` を1回実行し、Gmail と外部リクエストの権限を許可する。
4. `installQuarterHourTrigger` を1回実行する。これで `checkStatementMails` が15分ごとに動く。エディタのトリガー画面で「時間主導型・15分おき」を `checkStatementMails` に付けても同じです。
5. 処理済みラベルは `detail-management/notified`。API が 200 を返したスレッドだけに付く。400、401、5xx のときは付けないので、次の実行でやり直す。
6. `UrlFetchApp` の待ち時間は 90 秒。無料枠の Render がスリープから起きる時間を見込んでいる。

検索は差出人と件名の両方です。

| カード | 差出人 | 件名に含む文字列 |
|--------|--------|------------------|
| 楽天 | `info@mail.rakuten-card.co.jp` | `【楽天カード】カードご請求金額のご案内` |
| Amex | `AmericanExpress@welcome.americanexpress.com` | `ご請求金額確定のご案内` |

雛形が渡す年月は Asia/Tokyo の今日です。請求月と CSV の利用月をずらすときは、Gmail 側のコピーで年月の組み立てだけを直します。API はメール本文を読みません。

到達確認用の差出人・件名はソースに書きません。スクリプトプロパティ `TEST_STATEMENT_FROM`、`TEST_STATEMENT_SUBJECT`、`TEST_CARD_ISSUER_CODE` が揃ったときだけ、その条件も検索します。年月を指定するときは `TEST_YEAR` と `TEST_MONTH` を両方入れます。確認後はこれらのプロパティを消します。

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

`sample/` 配下には実明細などの個人情報を置く想定です。`.gitignore` で除外しているため、**追加・コミットしないでください**（ローカル検証専用）。

コミットメッセージは **日本語** で書く（詳細は `.cursor/rules/git-commits.mdc`）。
