# 家族家計管理アプリ API仕様書

## 目次

1. [基本情報](#1-基本情報)
2. [共通仕様](#2-共通仕様)
3. [エンドポイント一覧](#3-エンドポイント一覧)
   - [3.1 明細](#31-明細)
   - [3.2 カテゴリ](#32-カテゴリ)
   - [3.3 分類ルール](#33-分類ルール)
   - [3.4 固定費](#34-固定費)
   - [3.5 手動支払い](#35-手動支払い)
   - [3.6 カード発行会社・取込プロファイル](#36-カード発行会社取込プロファイル)
4. [分類ロジック仕様](#4-分類ロジック仕様)
5. [CSV取込（プロファイル駆動）](#5-csv取込プロファイル駆動)
6. [通知系API（予定）](#6-通知系api予定)

## 1. 基本情報

- ベースURL（開発）: `http://localhost:8000`
- ベースURL（本番）: `https://xxx.onrender.com`
- 認証方式: `Authorization: Bearer <JWT>`（Supabase Auth）
- データ形式: `application/json`（アップロードは `multipart/form-data`）

## 2. 共通仕様

### 2.1 認証

- `/health` を除く全エンドポイントは `Authorization: Bearer <JWT>` を必須とする。
- JWT は Supabase Auth の access token（JWT Signing Keys: **ES256** / RS256 等）を想定する。
- サーバーは `SUPABASE_URL` の JWKS（`/auth/v1/.well-known/jwks.json`）で公開鍵検証する（Supabase API は都度呼ばない）。
- Legacy HS256 トークンのみのプロジェクトでは、追加で `SUPABASE_JWT_SECRET` による検証にフォールバック可能。
- 検証後、JWT の `sub`（Supabase Auth の UUID）で `users` テーブルを引き、
  未登録ユーザーは 403 を返す（事前に夫・妻の 2 アカウントを `users` に登録しておく）。
- 開発環境は本番とは別の Supabase プロジェクトを用意し、`SUPABASE_JWT_SECRET` を切り替えるだけで本番と同じ認証コードパスを通す。

| 状態 | 応答 |
|------|------|
| Authorization ヘッダなし | 401 + `WWW-Authenticate: Bearer` |
| JWT 不正・期限切れ | 401 |
| JWT は有効だが `users` に未登録 | 403 |
| サーバーに `SUPABASE_JWT_SECRET` 未設定 | 500（設定エラー） |

### 2.2 ステータスコード方針

| コード | 用途 |
|--------|------|
| 200 | 取得・更新成功 |
| 201 | 作成成功 |
| 400 | リクエスト不正 |
| 401 | 認証エラー |
| 403 | 認可エラー（`users` 未登録など） |
| 404 | 対象データなし |
| 422 | バリデーションエラー |
| 500 | サーバー内部エラー |

### 2.3 エラー応答例

```json
{
  "detail": "Invalid request"
}
```

### 2.4 ログ

- アプリケーションログは stdout とログファイルに JSON 形式で出力する（Render / ローカルターミナル / `backend/logs/app.log` で確認）。
- ログファイルは既定で `logs/app.log`、10MB x 5世代でローテーションする（`LOG_FILE_*` 環境変数で変更可能）。
- API アクセスログは `LOG_API_ACCESS=true`（既定）で出力し、`method` / `path` / `query` / `status_code` / `duration_ms` / `request_id` などのメタ情報を記録する。
- リクエスト・レスポンス body は、明細や API キーなどの機密情報混入を避けるため出力しない。
- AI 分類ログは通常、バッチ件数・採用件数・低確信度件数などのサマリのみ出力する。
- `LOG_AI_CLASSIFICATION_DETAIL=true` のときだけ、AI に渡した店名と分類結果を詳細ログとして出力する（家計情報を含むため開発・調査時のみ推奨）。

## 3. エンドポイント一覧

## 3.1 明細

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/statements/detect-issuer` | CSV ヘッダ等から issuer を推定（確認用） |
| POST | `/statements/upload` | CSV をアップロードし、変換・分類・保存する（複数ファイル可） |
| GET | `/statements` | 明細一覧を取得（フィルタ対応） |
| GET | `/statements/upload-status` | 対象月の issuer ごとの取込済み状況 |
| PATCH | `/statements/items/{id}` | 明細行のカテゴリを手動更新 |
| GET | `/statements/summary` | 月次カテゴリ集計を取得 |
| GET | `/statements/summary/by-holder` | 対象月の名義人別合計を取得 |
| GET | `/statements/summary/monthly-trend` | 期間の月次推移（カテゴリ別）を取得 |

### POST `/statements/detect-issuer`

- 概要: アップロード前の確認用。CSV を受け取り、有効な `csv_import_profiles.header_signature` と照合して issuer 候補を返す。
- リクエスト: `multipart/form-data`（`file`）
- レスポンス例:

```json
{
  "detected_code": "rakuten",
  "detected_display_name": "楽天",
  "confidence": "high",
  "candidates": [
    { "code": "rakuten", "display_name": "楽天" }
  ]
}
```

- 判定不能時は `detected_code = null` と候補一覧（または空）を返し、クライアントで手動選択させる。

### POST `/statements/upload`

- 概要: 明細ファイルを保存し、取込プロファイルで共通モデルへ変換して分類・保存する。複数 CSV 可。
- リクエスト: `multipart/form-data`
  - `files`: CSV（**1件以上**。フィールド名は繰り返し `files`）
  - `year` / `month`: 対象年月（全ファイル共通）
  - `card_issuer_codes`（推奨）: issuer コード（`rakuten` / `amex` 等）の繰り返しフィールド。**`files` と同じ順序・同じ件数**で送る。画面で確認・修正した code の送付を正とする
  - `card_issuer_codes` を省略した場合のみ、サーバが各ファイルについて `detect-issuer` 相当の再判定を行う（曖昧・不能なら当該ファイルはエラー）
  - `files` と `card_issuer_codes` の件数が食い違う場合は **400**
- **互換性（破壊的変更）**: 旧形式の単一フィールド `file`、および単一オブジェクト応答（トップレベルに `statement_id` 等）は **サポートしない**。クライアントは本節の `files` / `card_issuer_codes` / `results[]` に合わせる（フロント追従は P3）
- 変換: DB の `csv_import_profiles` を読む **汎用エンジン** のみ。会社専用パーサは置かない。PDF は対象外（将来）
- 再アップロード: 同一 `year` / `month` / issuer が既にある場合は当該 statement（および items）を **置換**（他 issuer の行は触らない）
- 主な処理（ファイルごと）:
  1. Supabase Storageへ原本保存（未実装の場合あり）
  2. 指定/判定した issuer のプロファイルで共通モデルへ変換
  3. ルール分類 → ルール未ヒット分を OpenAI で分類（`OPENAI_API_KEY` 設定時のみ）
  4. `statement_items` に保存
  5. 全ファイル処理後、妻へ通知送信（未実装の場合あり）
- レスポンス: 常に `results` 配列（ファイル順）。単一ファイルでも配列1件。

```json
{
  "results": [
    {
      "card_issuer_code": "rakuten",
      "statement_id": 12,
      "inserted_count": 245,
      "unclassified_count": 18,
      "error_count": 2
    },
    {
      "card_issuer_code": "amex",
      "statement_id": 13,
      "inserted_count": 88,
      "unclassified_count": 5,
      "error_count": 0
    }
  ]
}
```

### GET `/statements`

- クエリパラメータ（任意）:
  - `year`
  - `month`
  - `category`
  - `card_holder`
  - `card_issuer`（`card_issuers.code`）
  - `is_unclassified`（`true` のとき `category_id IS NULL`）
- レスポンス: 明細行リスト（`statements` / `card_issuers` と JOIN）
  - `card_issuer_code` / `card_issuer_name`
  - `ai_confidence`: AI 採用時の信頼度（0.0〜1.0、AI分類でない場合は `null`）
  - `needs_ai_review`: `classified_by = "ai"` かつ `ai_confidence <= AI_CONFIDENCE_REVIEW_THRESHOLD` の場合 `true`

### GET `/statements/upload-status`

- 概要: 対象月について、`include_in_reminder = true` かつ `is_active` な issuer ごとの取込有無を返す。
- クエリパラメータ:
  - `year`（必須）
  - `month`（必須）
- レスポンス例:

```json
{
  "year": 2026,
  "month": 3,
  "expected_issuers": [
    { "code": "rakuten", "display_name": "楽天" },
    { "code": "amex", "display_name": "Amex" }
  ],
  "uploaded": [
    { "code": "rakuten", "display_name": "楽天", "statement_id": 12, "uploaded_at": "2026-04-06T10:00:00Z" }
  ],
  "missing": [
    { "code": "amex", "display_name": "Amex" }
  ]
}
```

### PATCH `/statements/items/{id}`

- 概要: 明細行のカテゴリを手動で修正する。
- リクエスト例:

```json
{
  "category_id": 3
}
```

### GET `/statements/summary`

- クエリパラメータ:
  - `year`（必須）
  - `month`（必須）
  - `card_issuer`（任意。`card_issuers.code`。未指定時は全 issuer 合算）
- レスポンス例:

```json
{
  "year": 2026,
  "month": 3,
  "totals": [
    { "category_id": 1, "category_name": "食費", "amount": 35600 },
    { "category_id": 3, "category_name": "光熱費", "amount": 14200 }
  ]
}
```

### GET `/statements/summary/by-holder`

- クエリパラメータ:
  - `year`（必須）
  - `month`（必須）
  - `card_issuer`（任意。`card_issuers.code`）
- レスポンス例:

```json
{
  "year": 2026,
  "month": 3,
  "totals": [
    { "card_holder": "夫", "amount": 124000 },
    { "card_holder": "妻", "amount": 98000 },
    { "card_holder": "共通", "amount": 26000 }
  ]
}
```

### GET `/statements/summary/monthly-trend`

- 概要: 指定期間のカテゴリ別月次推移を返す（棒グラフ用）。
- クエリパラメータ:
  - `from_year`（必須）
  - `from_month`（必須）
  - `to_year`（必須）
  - `to_month`（必須）
  - `category_id`（任意、未指定時は全カテゴリ）
- レスポンス例:

```json
{
  "from": { "year": 2026, "month": 1 },
  "to": { "year": 2026, "month": 3 },
  "series": [
    {
      "category_id": 1,
      "category_name": "食費",
      "points": [
        { "year": 2026, "month": 1, "amount": 52300 },
        { "year": 2026, "month": 2, "amount": 48700 },
        { "year": 2026, "month": 3, "amount": 50120 }
      ]
    }
  ]
}
```

## 3.2 カテゴリ

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/categories` | 一覧取得 |
| POST | `/categories` | 新規作成 |
| PUT | `/categories/{id}` | 更新 |
| DELETE | `/categories/{id}` | 削除 |

### POST `/categories`

```json
{
  "name": "教育費",
  "color": "#3F51B5",
  "sort_order": 8
}
```

## 3.3 分類ルール

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/rules` | 一覧取得 |
| POST | `/rules` | 新規作成 |
| PUT | `/rules/{id}` | 更新 |
| DELETE | `/rules/{id}` | 削除 |

### POST `/rules`

```json
{
  "pattern": "イオン",
  "is_regex": false,
  "category_id": 1,
  "priority": 100
}
```

- バリデーション:
  - `priority` は `0` 以上の整数

## 3.4 固定費

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/fixed-expenses` | 一覧取得 |
| POST | `/fixed-expenses` | 新規作成 |
| PUT | `/fixed-expenses/{id}` | 更新 |
| DELETE | `/fixed-expenses/{id}` | 無効化（論理削除） |

### POST `/fixed-expenses`

```json
{
  "name": "Netflix",
  "amount": 1490,
  "category_id": 7,
  "billing_day": 27,
  "card_holder": "共通",
  "valid_from": "2026-03-01"
}
```

## 3.5 手動支払い

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/manual-expenses` | 一覧取得（年月フィルタ） |
| POST | `/manual-expenses` | 新規登録 |
| PUT | `/manual-expenses/{id}` | 更新 |
| DELETE | `/manual-expenses/{id}` | 削除 |

### POST `/manual-expenses`

```json
{
  "used_at": "2026-03-18",
  "shop_name": "地域イベント費",
  "amount": 2000,
  "category_id": 7,
  "card_holder": "妻",
  "year": 2026,
  "month": 3,
  "note": "自治会費"
}
```

## 3.6 カード発行会社・取込プロファイル

管理画面は低優先。当面は本 API または SQL でメンテする。

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/card-issuers` | 発行会社一覧 |
| POST | `/card-issuers` | 発行会社作成 |
| PUT | `/card-issuers/{id}` | 発行会社更新 |
| DELETE | `/card-issuers/{id}` | 無効化（論理削除想定） |
| GET | `/csv-import-profiles` | 取込プロファイル一覧 |
| GET | `/csv-import-profiles/{id}` | 取込プロファイル取得 |
| POST | `/csv-import-profiles` | 取込プロファイル作成 |
| PUT | `/csv-import-profiles/{id}` | 取込プロファイル更新 |
| DELETE | `/csv-import-profiles/{id}` | 削除 |

### POST `/card-issuers`

```json
{
  "code": "smbc",
  "display_name": "三井住友",
  "include_in_reminder": true,
  "remind_day_of_month": 15,
  "sort_order": 3
}
```

### POST `/csv-import-profiles`

```json
{
  "card_issuer_id": 3,
  "encoding": "utf-8",
  "header_signature": ["利用日", "利用店舗", "金額"],
  "column_mapping": {
    "used_at": "利用日",
    "shop_name": "利用店舗",
    "amount": "金額",
    "card_holder": null
  },
  "transforms": {
    "date_format": "%Y/%m/%d",
    "amount_remove_chars": [","],
    "default_card_holder": "夫"
  },
  "skip_rules": [{ "when_column": "利用店舗", "equals": "合計" }],
  "custom_hook": null
}
```

## 4. 分類ロジック仕様

分類優先順位:
1. `classification_rules` を `priority` 降順で評価。
2. 未ヒット時は、環境変数 `OPENAI_API_KEY` が設定されていれば OpenAI（Chat Completions）で店名からカテゴリを推定。未設定のときは AI を呼ばず未分類のまま取り込む。
3. AI 確信度が閾値未満（既定 `AI_CLASSIFICATION_CONFIDENCE_THRESHOLD=0.7`）の場合は `category_id = NULL` のまま保存し、UI 上は「未分類」として表示する（マスタの「その他」とは別物）。閾値未満でも `ai_confidence` / `ai_raw_response` に推定結果を残す場合がある（デバッグ用）。

ルール外の店名は取り込みバッチ内で重複排除し、OpenAI へは最大数十件ずつまとめて送る。

記録ルール:
- ルール一致時: `classified_by = "rule"`
- AI 採用時（確信度 >= 閾値）: `classified_by = "ai"`, `ai_confidence` を保存
- 手動修正時: `classified_by = "manual"`

一覧画面の要確認表示:
- AI 分類採用後も `AI_CONFIDENCE_REVIEW_THRESHOLD`（既定 `0.8`）以下の明細は `needs_ai_review = true` として返し、UI で低信頼度行として強調表示する。
- `category_id = NULL` の明細は UI 上「未分類」として表示し、低信頼度行とは別色で強調表示する。

## 5. CSV取込（プロファイル駆動）

```text
CSVファイル（複数可）
  → header_signature で issuer 候補を判定（detect-issuer）
  → ユーザー確認後、files と同じ順の card_issuer_codes を upload に添付
  → csv_import_profiles を読む汎用エンジン
  → 共通モデル（used_at, shop_name, amount, card_holder, ...）
  → 分類 → statement_items（results[] でファイルごと返す）
```

- 会社専用パーサは追加しない。カード追加時は `card_issuers` + `csv_import_profiles` を追加する。
- `custom_hook` は通常 NULL。設定で表現できない場合の任意・低優先の逃げ道であり、初期実装では未使用でよい。
- detect の照合（当面）: プロファイルの `header_signature` 全要素が CSV ヘッダに含まれる（順序不問）。一意一致なら `detected_code` に採用、複数一致・不一致は `null` と候補。

## 6. 通知系API（予定）

| メソッド | パス | 用途 |
|----------|------|------|
| POST | `/notify/remind` | 明細取込リマインド送信（未取込 issuer がある場合） |
| GET | `/notify/remind.ics` | 毎月リマインド用のカレンダー（`.ics`）配布（任意・認証方針は実装時に決定） |

### POST `/notify/remind`

- 概要: 今日が `remind_day_of_month` に当たる（または再通知日の）issuer のうち、対象年月で未アップロードのものだけ夫へ LINE 通知する。該当がなければ通知せず成功応答。
- issuer ごとのリマインド日は `card_issuers.remind_day_of_month`（変更可）。初期値: `rakuten=23`, `amex=4`。
- 呼び出し元: `cron-job.org` または GitHub Actions `schedule` 等（例: 毎日1回叩いてサーバ側で「今日が remind_day か」を判定）。
- 認証: サービス用シークレット（例: `Authorization: Bearer <REMIND_CRON_SECRET>`）。ユーザー JWT とは別経路。
- リクエスト例（任意ボディ。省略時はサーバが「今日」と対象年月を決定）:

```json
{
  "year": 2026,
  "month": 3,
  "force": false
}
```

- `force=true` のときは未取込有無に関わらず通知する（手動試験用）。
- レスポンス例:

```json
{
  "year": 2026,
  "month": 3,
  "due_issuers": ["amex"],
  "missing": ["amex"],
  "notified": true
}
```

### GET `/notify/remind.ics`

- 概要: 「毎年毎月 N 日」のリマインドイベントを含む `.ics` を返す。端末カレンダーへ一度登録すればサーバ cron なしでも催促できる補助手段。
- `N`（日付）は環境変数またはクエリで指定可能とする想定。
