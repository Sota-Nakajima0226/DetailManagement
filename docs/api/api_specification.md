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
4. [分類ロジック仕様](#4-分類ロジック仕様)
5. [通知系API（予定）](#5-通知系api予定)

## 1. 基本情報

- ベースURL（開発）: `http://localhost:8000`
- ベースURL（本番）: `https://xxx.onrender.com`
- 認証方式: `Authorization: Bearer <JWT>`（Supabase Auth）
- データ形式: `application/json`（アップロードは `multipart/form-data`）

## 2. 共通仕様

### 2.1 認証

- `/health` を除く全エンドポイントは `Authorization: Bearer <JWT>` を必須とする。
- JWT は Supabase Auth の access token（HS256 署名）を想定する。
- サーバーは Supabase API を呼ばずに `SUPABASE_JWT_SECRET` でローカル署名検証する。
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
| POST | `/statements/upload` | CSV/PDFをアップロードし、パース・分類・保存を行う |
| GET | `/statements` | 明細一覧を取得（フィルタ対応） |
| PATCH | `/statements/items/{id}` | 明細行のカテゴリを手動更新 |
| GET | `/statements/summary` | 月次カテゴリ集計を取得 |
| GET | `/statements/summary/by-holder` | 対象月の名義人別合計を取得 |
| GET | `/statements/summary/monthly-trend` | 期間の月次推移（カテゴリ別）を取得 |

### POST `/statements/upload`

- 概要: 明細ファイルを保存し、行データを抽出・分類する。
- リクエスト: `multipart/form-data`
  - `file`: CSVまたはPDF
  - `year`: 対象年
  - `month`: 対象月
- 主な処理:
  1. Supabase Storageへ原本保存（未実装の場合あり）
  2. CSV パース（PDF は別途）
  3. ルール分類 → ルール未ヒット分を OpenAI で分類（`OPENAI_API_KEY` 設定時のみ）
  4. `statement_items` に保存
  5. 妻へ通知送信（未実装の場合あり）
- レスポンス例:

```json
{
  "statement_id": 12,
  "inserted_count": 245,
  "unclassified_count": 18,
  "error_count": 2
}
```

### GET `/statements`

- クエリパラメータ（任意）:
  - `year`
  - `month`
  - `category`
  - `card_holder`
  - `is_unclassified`（`true` のとき `category_id IS NULL`）
- レスポンス: 明細行リスト
  - `ai_confidence`: AI 採用時の信頼度（0.0〜1.0、AI分類でない場合は `null`）
  - `needs_ai_review`: `classified_by = "ai"` かつ `ai_confidence <= AI_CONFIDENCE_REVIEW_THRESHOLD` の場合 `true`

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

## 5. 通知系API（予定）

定期リマインド向けに以下を想定:

| メソッド | パス | 用途 |
|----------|------|------|
| POST | `/notify/remind` | 毎月の明細確定リマインド送信 |

※ 実行は `cron-job.org` または GitHub Actions `schedule` を想定。
