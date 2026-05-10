# 家族家計管理アプリ DB設計書

## 目次

1. [文書概要](#1-文書概要)
2. [設計方針](#2-設計方針)
3. [テーブル一覧](#3-テーブル一覧)
4. [テーブル詳細](#4-テーブル詳細)
5. [主要制約とインデックス方針](#5-主要制約とインデックス方針)
6. [月次集計ビュー](#6-月次集計ビュー)
7. [初期DDL](#7-初期ddl)
8. [初期カテゴリデータ](#8-初期カテゴリデータ)

## 1. 文書概要

- 本書は家族家計管理アプリのDB設計を定義する。
- 対象DBは Supabase 上の PostgreSQL を前提とする。
- 参照元は `requirements_and_design.md` の「データベース設計」節とする。

## 2. 設計方針

- 明細原本（CSV/PDF）と明細行データを分離し、再集計を容易にする。
- 自動分類（ルール/AI）と手動修正の履歴を保持し、運用改善に活かす。
- 固定費はマスタ管理し、適用期間で履歴を表現する。
- 手動支払いを別テーブルで管理し、月次集計で統合する。

## 3. テーブル一覧

| テーブル名 | 用途 |
|------------|------|
| users | ユーザー情報（認証主体は Supabase Auth） |
| categories | カテゴリマスター |
| classification_rules | 店名パターンによる分類ルール |
| statements | 月次明細ファイル情報 |
| statement_items | 明細行データ |
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
| priority | INT | 優先度（0〜100。大きいほど先評価） |
| created_at | TIMESTAMPTZ | 作成日時 |

### statements（明細ファイル）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | 明細ファイルID |
| year | INT | 対象年 |
| month | INT | 対象月 |
| file_url | TEXT | Supabase Storage URL |
| uploaded_at | TIMESTAMPTZ | アップロード日時 |

### statement_items（明細行データ）

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
| source | TEXT | `csv` / `pdf` / `manual` / `fixed` |
| created_at | TIMESTAMPTZ | 作成日時 |

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

- `statements` は `UNIQUE(year, month)` で同年月の重複登録を防止する。
- `statement_items.statement_id` は `ON DELETE CASCADE` を設定し、明細削除時に関連行を連動削除する。
- 分類ルールは `priority` 降順で評価し、高優先ルールを先に適用する。
- 固定費履歴は `valid_from` / `valid_until` の期間管理で整合性を担保する。

## 6. 月次集計ビュー

`monthly_expenses` でカード明細由来データと手動支払いを統合する。

```sql
CREATE VIEW monthly_expenses AS
  SELECT
    si.used_at, si.shop_name, si.amount,
    si.card_holder, si.category_id,
    si.classified_by, si.source,
    s.year, s.month
  FROM statement_items si
  JOIN statements s ON s.id = si.statement_id

  UNION ALL

  SELECT
    me.used_at, me.shop_name, me.amount,
    me.card_holder, me.category_id,
    'manual' AS classified_by, 'manual' AS source,
    me.year, me.month
  FROM manual_expenses me;
```

固定費はビューに物理保存せず、API集計時に対象月条件で動的加算する。

## 7. 初期DDL

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

CREATE TABLE statements (
  id          SERIAL PRIMARY KEY,
  year        INT NOT NULL,
  month       INT NOT NULL,
  file_url    TEXT,
  uploaded_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(year, month)
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

## 8. 初期カテゴリデータ

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
