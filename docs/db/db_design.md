# 家族家計管理アプリ DB設計書

## 目次

1. [文書概要](#1-文書概要)
2. [設計方針](#2-設計方針)
3. [テーブル一覧](#3-テーブル一覧)
4. [テーブル詳細](#4-テーブル詳細)
5. [主要制約とインデックス方針](#5-主要制約とインデックス方針)
6. [スキーマ移行（issuer 導入時）](#6-スキーマ移行issuer-導入時)
7. [月次集計ビュー](#7-月次集計ビュー)
8. [初期DDL](#8-初期ddl)
9. [初期データ](#9-初期データ)

## 1. 文書概要

- 本書は家族家計管理アプリのDB設計を定義する。
- 対象DBは Supabase 上の PostgreSQL を前提とする。
- 参照元は `requirements_and_design.md` の「データベース設計」節とする。

## 2. 設計方針

- 明細原本（CSV）と明細行データを分離し、再集計を容易にする。
- **issuer（カード発行会社）** をマスタ化し、同月に複数 issuer の明細ファイルを共存させる。
- CSV → 共通明細行への変換は、会社専用パーサではなく **DB 上の取込プロファイル** と汎用エンジンで行う。
- 自動分類（ルール/AI）と手動修正の履歴を保持し、運用改善に活かす。
- 固定費はマスタ管理し、適用期間で履歴を表現する。
- 手動支払いを別テーブルで管理し、月次集計で統合する。

## 3. テーブル一覧

| テーブル名 | 用途 |
|------------|------|
| users | ユーザー情報（認証主体は Supabase Auth） |
| categories | カテゴリマスター |
| classification_rules | 店名パターンによる分類ルール |
| card_issuers | カード発行会社マスタ（issuer） |
| csv_import_profiles | CSV→共通モデルの列マッピング等 |
| statements | 月次明細ファイル情報 |
| statement_items | 明細行データ（共通モデルの永続化） |
| fixed_expenses | 固定費マスター |
| manual_expenses | 手動登録支払い |

## 4. テーブル詳細

### users（ユーザー）

Supabase Auth が主に管理し、アプリではロール参照を行う。

| カラム | 型 | 説明 |
|--------|----|------|
| id | UUID PK | Supabase Auth が生成 |
| email | TEXT | メールアドレス |
| role | TEXT | `owner`（夫）/ `member`（妻） |

### categories（カテゴリマスター）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | カテゴリID |
| name | TEXT | カテゴリ名 |
| color | TEXT | 表示色（例: `#4CAF50`） |
| sort_order | INT | 表示順 |
| created_at | TIMESTAMPTZ | 作成日時 |

### classification_rules（分類ルール）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | ルールID |
| pattern | TEXT | マッチパターン（文字列/正規表現） |
| is_regex | BOOLEAN | 正規表現フラグ |
| category_id | INT FK | `categories.id` |
| priority | INT | 優先度（0以上。大きいほど先評価） |
| created_at | TIMESTAMPTZ | 作成日時 |

### card_issuers（カード発行会社マスタ）

issuer の定義。API・画面では `code` を識別子、`display_name` を表示名として使う。

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | 発行会社ID |
| code | TEXT UNIQUE | 内部コード（例: `rakuten`, `amex`） |
| display_name | TEXT | 表示名（例: `楽天`, `Amex`） |
| is_active | BOOLEAN | 有効フラグ |
| include_in_reminder | BOOLEAN | 取込リマインド／未完了バッジの対象に含めるか |
| remind_day_of_month | INT | 毎月のリマインド日（1〜28推奨）。設定変更可能。初期値: 楽天 `23`、Amex `4` |
| sort_order | INT | 表示順 |
| created_at | TIMESTAMPTZ | 作成日時 |

### csv_import_profiles（CSV取込プロファイル）

issuer ごとの CSV → 共通モデル変換設定。カード追加時は本テーブル（と `card_issuers`）に行を足す。

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | プロファイルID |
| card_issuer_id | INT UNIQUE FK | `card_issuers.id`（1 issuer につき有効プロファイル1件） |
| encoding | TEXT | 文字コード（例: `utf-8`, `cp932`） |
| header_signature | JSONB | 自動判定用。期待するヘッダ列名の配列など |
| column_mapping | JSONB | 共通項目への列対応（`used_at` / `shop_name` / `amount` / `card_holder`） |
| transforms | JSONB | 日付フォーマット、金額正規化、名義人の値変換など |
| skip_rules | JSONB | 合計行・空行・確定前行などのスキップ条件 |
| custom_hook | TEXT NULL | 任意・低優先。設定だけでは表現できない特殊処理の名前。通常は NULL |
| updated_at | TIMESTAMPTZ | 更新日時 |
| created_at | TIMESTAMPTZ | 作成日時 |

`column_mapping` の例:

```json
{
  "used_at": "利用日",
  "shop_name": "利用店名・商品名",
  "amount": "利用金額",
  "card_holder": "利用者"
}
```

`transforms` の例:

```json
{
  "date_format": "%Y/%m/%d",
  "amount_remove_chars": [",", "¥"],
  "card_holder_map": { "本人": "夫", "家族": "妻" }
}
```

### statements（明細ファイル）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | 明細ファイルID |
| year | INT | 対象年 |
| month | INT | 対象月 |
| card_issuer_id | INT FK | `card_issuers.id` |
| file_url | TEXT | Supabase Storage URL |
| uploaded_at | TIMESTAMPTZ | アップロード日時 |

### statement_items（明細行データ＝共通モデルの永続化）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | 明細行ID |
| statement_id | INT FK | `statements.id` |
| used_at | DATE | 利用日 |
| shop_name | TEXT | 店名/商品名 |
| amount | INT | 利用金額（円） |
| card_holder | TEXT | `夫` / `妻` |
| category_id | INT FK | `categories.id` |
| classified_by | TEXT | `rule` / `ai` / `manual` |
| ai_confidence | FLOAT | AI確信度（0.0〜1.0）。SQLAlchemy は `Float` を使用 |
| ai_raw_response | TEXT | AI生レスポンス（デバッグ） |
| source | TEXT | `csv` / `manual` / `fixed`（PDF取込は将来。現状は csv 想定） |
| created_at | TIMESTAMPTZ | 作成日時 |

補足:

- issuer は `statements.card_issuer_id` 経由で参照し、一覧・フィルタでは `card_issuers.code` / `display_name` を JOIN して露出する。
- 一意制約は **`UNIQUE(year, month, card_issuer_id)`**（旧来の `UNIQUE(year, month)` ではない）。同月に楽天・Amex など複数 issuer を共存できる。

### fixed_expenses（固定費マスター）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | 固定費ID |
| name | TEXT | 固定費名 |
| amount | INT | 金額（円） |
| category_id | INT FK | `categories.id` |
| billing_day | INT | 引き落とし日 |
| card_holder | TEXT | `夫` / `妻` / `共通` |
| is_active | BOOLEAN | 有効フラグ |
| valid_from | DATE | 適用開始日 |
| valid_until | DATE | 適用終了日（NULLは継続中） |
| created_at | TIMESTAMPTZ | 作成日時 |

### manual_expenses（手動登録支払い）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | 手動支払いID |
| used_at | DATE | 利用日 |
| shop_name | TEXT | 支払い先 |
| amount | INT | 金額（円） |
| category_id | INT FK | `categories.id` |
| card_holder | TEXT | `夫` / `妻` / `共通` |
| year | INT | 集計対象年 |
| month | INT | 集計対象月 |
| note | TEXT | メモ |
| created_by | TEXT | 登録者 |
| created_at | TIMESTAMPTZ | 作成日時 |

## 5. 主要制約とインデックス方針

- `card_issuers.code` は UNIQUE。
- `csv_import_profiles.card_issuer_id` は UNIQUE（issuer あたりプロファイル1件）。
- `statements` は **`UNIQUE(year, month, card_issuer_id)`** で、同年月かつ同一 issuer の重複登録を防止する。
- `statement_items.statement_id` は `ON DELETE CASCADE` を設定し、明細削除時に関連行を連動削除する。
- 同一 `year` / `month` / issuer の再アップロードは、対象 `statements` 行（および CASCADE で items）を置換する。
- 分類ルールは `priority` 降順で評価し、高優先ルールを先に適用する。
- 固定費履歴は `valid_from` / `valid_until` の期間管理で整合性を担保する。

## 6. スキーマ移行（issuer 導入時）

`UNIQUE(year, month)` から issuer 付きスキーマへ移すときのルール（Alembic 実装時の正本）。

1. `card_issuers` / `csv_import_profiles` を作成する。
2. 移行に必要な最低限の issuer として `rakuten`（およびシードで `amex`）を投入可能にする。
3. `statements` に `card_issuer_id` を追加する（当初は NULL 可）。
4. **既存の `statements` 行はすべて `rakuten` に backfill する**（導入時点の取込は楽天CSV専用だったため）。
5. `card_issuer_id` を NOT NULL にし、FK を張る。
6. 旧制約 `UNIQUE(year, month)`（`uq_statements_year_month`）を削除し、**`UNIQUE(year, month, card_issuer_id)`** を追加する。

## 7. 月次集計ビュー

`monthly_expenses` でカード明細由来データと手動支払いを統合する。

```sql
CREATE VIEW monthly_expenses AS
  SELECT
    si.used_at, si.shop_name, si.amount,
    si.card_holder, si.category_id,
    si.classified_by, si.source,
    s.year, s.month,
    ci.code AS card_issuer_code,
    ci.display_name AS card_issuer_name
  FROM statement_items si
  JOIN statements s ON s.id = si.statement_id
  JOIN card_issuers ci ON ci.id = s.card_issuer_id

  UNION ALL

  SELECT
    me.used_at, me.shop_name, me.amount,
    me.card_holder, me.category_id,
    'manual' AS classified_by, 'manual' AS source,
    me.year, me.month,
    NULL AS card_issuer_code,
    NULL AS card_issuer_name
  FROM manual_expenses me;
```

固定費はビューに物理保存せず、API集計時に対象月条件で動的加算する。

## 8. 初期DDL

```sql
CREATE TABLE users (
  id    TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  role  TEXT NOT NULL
);

CREATE TABLE categories (
  id         SERIAL PRIMARY KEY,
  name       TEXT NOT NULL,
  color      TEXT DEFAULT '#888888',
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE classification_rules (
  id          SERIAL PRIMARY KEY,
  pattern     TEXT NOT NULL,
  is_regex    BOOLEAN DEFAULT FALSE,
  category_id INT REFERENCES categories(id),
  priority    INT DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE card_issuers (
  id                   SERIAL PRIMARY KEY,
  code                 TEXT NOT NULL UNIQUE,
  display_name         TEXT NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT TRUE,
  include_in_reminder  BOOLEAN NOT NULL DEFAULT TRUE,
  remind_day_of_month  INT NOT NULL DEFAULT 1,
  sort_order           INT NOT NULL DEFAULT 0,
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE csv_import_profiles (
  id               SERIAL PRIMARY KEY,
  card_issuer_id   INT NOT NULL UNIQUE REFERENCES card_issuers(id),
  encoding         TEXT NOT NULL DEFAULT 'utf-8',
  header_signature JSONB NOT NULL,
  column_mapping   JSONB NOT NULL,
  transforms       JSONB NOT NULL DEFAULT '{}'::jsonb,
  skip_rules       JSONB NOT NULL DEFAULT '[]'::jsonb,
  custom_hook      TEXT,
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE statements (
  id              SERIAL PRIMARY KEY,
  year            INT NOT NULL,
  month           INT NOT NULL,
  card_issuer_id  INT NOT NULL REFERENCES card_issuers(id),
  file_url        TEXT,
  uploaded_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(year, month, card_issuer_id)
);

CREATE TABLE statement_items (
  id              SERIAL PRIMARY KEY,
  statement_id    INT REFERENCES statements(id) ON DELETE CASCADE,
  used_at         DATE NOT NULL,
  shop_name       TEXT NOT NULL,
  amount          INT NOT NULL,
  card_holder     TEXT,
  category_id     INT REFERENCES categories(id),
  classified_by   TEXT,
  ai_confidence   DOUBLE PRECISION,
  ai_raw_response TEXT,
  source          TEXT DEFAULT 'csv',
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fixed_expenses (
  id           SERIAL PRIMARY KEY,
  name         TEXT NOT NULL,
  amount       INT NOT NULL,
  category_id  INT REFERENCES categories(id),
  billing_day  INT,
  card_holder  TEXT DEFAULT '共通',
  is_active    BOOLEAN DEFAULT TRUE,
  valid_from   DATE NOT NULL DEFAULT CURRENT_DATE,
  valid_until  DATE,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE manual_expenses (
  id           SERIAL PRIMARY KEY,
  used_at      DATE NOT NULL,
  shop_name    TEXT NOT NULL,
  amount       INT NOT NULL,
  category_id  INT REFERENCES categories(id),
  card_holder  TEXT,
  year         INT NOT NULL,
  month        INT NOT NULL,
  note         TEXT,
  created_by   TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

## 9. 初期データ

### カテゴリ

```sql
INSERT INTO categories (name, color, sort_order) VALUES
  ('食費',   '#4CAF50', 1),
  ('日用品', '#2196F3', 2),
  ('光熱費', '#FF9800', 3),
  ('交通費', '#9C27B0', 4),
  ('外食',   '#F44336', 5),
  ('医療費', '#00BCD4', 6),
  ('娯楽',   '#E91E63', 7),
  ('住居費', '#3F51B5', 8),
  ('車関連', '#795548', 9),
  ('その他', '#607D8B', 99);
```

- 「その他」は明示的に分類できないが共通フォルダ的に置く先として使用する。
- ルールでも AI でも分類できなかった明細は `category_id = NULL` とし、UI では「未分類」として表示する（マスタにレコードは持たない）。

### カード発行会社・取込プロファイル（シード）

サンプル実ファイル（`sample/rakuten/`, `sample/amex/`）に基づく初期値。

```sql
INSERT INTO card_issuers (code, display_name, remind_day_of_month, sort_order) VALUES
  ('rakuten', '楽天', 23, 1),
  ('amex', 'Amex', 4, 2);
```

| code | encoding | header_signature（抜粋） | column_mapping | transforms の要点 |
|------|----------|--------------------------|----------------|-------------------|
| `rakuten` | `utf-8-sig`（実ファイル確認） | `利用日`, `利用店名・商品名`, `利用者`, `利用金額` | used_at←利用日, shop_name←利用店名・商品名, amount←利用金額, card_holder←利用者 | `本人`→`夫`, `家族`→`妻` |
| `amex` | `cp932` | `ご利用日`, `データ処理日`, `ご利用内容`, `カード会員様名`, `会員番号 #`, `金額`, … | used_at←ご利用日, shop_name←ご利用内容, amount←金額, card_holder←カード会員様名 | 金額の `,` 除去。名義は氏名マップ（例: `SOTA NAKAJIMA`→`夫`, `SEIRA NAKAJIMA`→`妻`。実装時にシードで設定） |

Amex補足:

- 区切りはカンマ。金額は `"121,509"` のように引用符付きのことがある。
- 追加カード名義は `カード会員様名`（ローマ字氏名）で区別できる。
- `海外通貨利用金額` / `換算レート` は取込対象外（スキップ列）。
