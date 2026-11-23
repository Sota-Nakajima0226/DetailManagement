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

ブラウザ向けのエントリは `frontend/web/` にあります。本番の配信手順は下の「本番デプロイ」です。構成の詳細は `requirements_and_design.md` の §13 を参照してください。

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
| `SUPABASE_URL` | Supabase の Project URL。JWT Signing Keys の検証に使う | なし |
| `SUPABASE_JWT_SECRET` | Legacy HS256 のときだけ。Signing Keys（ES256 など）では不要 | なし |
| `SUPABASE_JWT_AUDIENCE` | JWT の audience クレーム | `authenticated` |

#### 環境構築の流れ

開発用と本番用は別の Supabase プロジェクトにします。本番の順番は「本番デプロイ」にまとめています。

1. Supabase で **dev 用プロジェクト**と**本番用プロジェクト**を別々に作成する。
2. API には各プロジェクトの `SUPABASE_URL` を入れる。Legacy HS256 のプロジェクトだけ `SUPABASE_JWT_SECRET` を足す（`backend/.env` は dev 用、Render の環境変数は本番用）。
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

1. [LINE Official Account Manager](https://manager.line.biz/) で公式アカウントを作り、「設定」→「Messaging API」→「Messaging APIを利用する」でチャネルを作る。Developers コンソールからチャネルは直接作れない。ボタンの順は [docs/notifications/line_setup.md](docs/notifications/line_setup.md) の手順1。
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

## 本番デプロイ

公開 URL は Render の `*.onrender.com` です。API は Web Service、フロントは Static Site です。定義はリポジトリ直下の `render.yaml` です。秘密の値はリポジトリに置かず、Render の環境変数と Supabase のダッシュボードに入れます。

1. 開発用とは別に、本番用の Supabase プロジェクトを作る。
2. 認証の Site URL を、静的サイトの `https://….onrender.com` にする。URL は手順 4 のあとで分かるので、分かった時点で設定する。自己登録は使わない。
3. Supabase のダッシュボードで夫と妻を追加し、メール確認済みにする。表示された UUID を控える。
4. Render でこの GitHub リポジトリの Blueprint（`render.yaml`）を適用する。サービスは `detail-management-api` と `detail-management-web` です。`render.yaml` が `origin` の `main` に入ってから適用します。
5. API の環境変数を Render に入れる。`sync: false` の項目は作成時にダッシュボードで聞かれます。
   - `DATABASE_URL`: Supabase の Session pooler（IPv4）の接続文字列。アプリが `postgresql://` を `postgresql+psycopg://` に読み替えます。
   - `SUPABASE_URL`: 本番プロジェクトの Project URL。
   - `OPENAI_API_KEY`: 任意。空ならルールだけで取り込み、AI 分類はスキップします。
   - `LINE_CHANNEL_ACCESS_TOKEN`、`LINE_GROUP_ID`、`APP_UPLOAD_URL`、`REMIND_CRON_SECRET`: 明細メール通知の4つ。`APP_UPLOAD_URL` の値は手順 8 で決めます。
   - `LOG_FILE_ENABLED`: `false`。Blueprint にこの値が入っています。ログは stdout を Render の画面で見ます。
6. フロントのビルドに、次の3つを dart-define として入れる。名前は `frontend/lib/core/config/app_config.dart` と同じです。
   - `API_BASE_URL`: API の `https://….onrender.com`（パス無し）。
   - `SUPABASE_URL`: 本番プロジェクトの Project URL。
   - `SUPABASE_ANON_KEY`: 本番の anon key。ビルド成果物に含まれる公開鍵です。service role と JWT secret は入れません。
7. 初回だけ、本番の `DATABASE_URL` を環境に入れた状態で `backend` から次を実行する。デプロイコマンドにはシードを入れません。無料枠では pre-deploy が動かないため、API のビルドでも `python -m alembic upgrade head` が走ります。

   ```bash
   cd backend
   python -m alembic upgrade head
   python scripts/seed_master_data.py --skip-users
   ```

   `--skip-users` はカテゴリ、分類ルール、固定費、issuer、取込プロファイルを入れ、`users.json` は読みません。続けて、手順 3 の UUID を `users` に入れます。

   ```sql
   INSERT INTO users (id, email, role) VALUES
     ('<夫のUUID>', 'husband@example.com', 'owner'),
     ('<妻のUUID>', 'wife@example.com', 'member');
   ```

8. Render に表示された URL で、次を更新する。
   - API の `APP_UPLOAD_URL`: 静的サイトの `https://….onrender.com/upload`（クエリ無し）。
   - Apps Script の `NOTIFY_API_BASE_URL`: API のオリジン（パス無し）。
9. 以降の反映は、`main` を `origin` へ push してから Render がビルドします。push 前のローカルだけの変更は本番に出ません。
10. 無料枠の API は、無通信が約15分続くとスリープします。次のリクエストで起動し、応答が数十秒遅くなることがあります。フロントの Static Site はスリープしません。
11. 確認は次の順です。未ログインで開くとログイン画面になる。ログイン後に明細が見える。`/upload?year=&month=` でアップロード画面が開く。CSV を取り込める。一覧にその明細が出る。API の `/health` は 200 です。

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
