# 家族家計管理アプリ 要件定義書・設計書

**Version:** 0.3  
**作成日:** 2026年3月  
**更新:** 2026年11月（2カード対応・手動CSV運用・インフラ方針）  
**ステータス:** 仕様見直し反映  

> 分割された正本は `docs/` 配下。インフラコスト比較は `memo/infra_cost_comparison.md`。

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [背景と課題](#2-背景と課題)
3. [機能要件](#3-機能要件)
4. [非機能要件](#4-非機能要件)
5. [技術スタック](#5-技術スタック)
6. [システムアーキテクチャ](#6-システムアーキテクチャ)
7. [データベース設計](#7-データベース設計)
8. [API設計](#8-api設計)
9. [明細分類ロジック](#9-明細分類ロジック)
10. [認証・セキュリティ設計](#10-認証セキュリティ設計)
11. [通知設計](#11-通知設計)
12. [画面設計](#12-画面設計)
13. [開発・デプロイフロー](#13-開発デプロイフロー)
14. [開発フェーズ](#14-開発フェーズ)
15. [未決事項](#15-未決事項)

---

## 1. プロジェクト概要

| 項目 | 内容 |
|------|------|
| プロジェクト名 | 家族家計管理アプリ（仮称） |
| 対象ユーザー | 家族2名（夫・妻） |
| 主要プラットフォーム | PWA（Progressive Web App）— PC・スマホ両対応 |
| 開発目的 | 自己研鑽・家族の家計管理改善 |
| 公開範囲 | 家族内のみ（Web公開なし） |
| 支払手段 | 楽天カードおよび American Express（Amex）の2系統 |
| 将来拡張 | スケジュール共有など家族向け機能全般 |

---

## 2. 背景と課題

- 家計のカード支払いは **楽天カード** と **Amex** の2種類で行われている
- 楽天家族カードの明細閲覧権限は**本会員（夫）のみ**に限られている（Amex も原本取得はログイン会員側）
- 家計管理は**妻が担当**しているが、明細確認のたびに夫経由でCSVを受け取る必要がある
- この手動共有フローが手間であり、タイムリーな家計把握が難しい
- 明細の仕分け（カテゴリ分類）も毎月手作業で行っており、自動化したい
- カード会社の個人向け明細APIは無いため、完全自動取込は非現実的。手動CSVを主経路とし、一括UP・リマインド・未完了表示で運用負荷を下げる

---

## 3. 機能要件

### 3.1 明細アップロード機能

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| 手動アップロード | issuer（カード発行会社）ごとの CSV 明細をアップロード | 高 |
| プロファイル駆動変換 | DBの取込プロファイル＋汎用エンジンで共通モデルへ変換（会社専用パーサは作らない） | 高 |
| 初期シード | 楽天・Amex の issuer / プロファイル。PDFは低優先（将来） | 高 |
| 複数ファイル一括取込 | 複数CSVを一度に選択して取込 | 高 |
| 発行会社の自動判定 | ヘッダ指紋等で自動判定し、**画面で確認してから**取込 | 高 |
| 取込プロファイル管理API | CRUD（カード追加＝マッピング追加）。当面はAPI/SQLでメンテ | 高 |
| 取込プロファイル管理画面 | 上記UI（**低優先**） | 低 |
| アップロード完了通知 | 取込成功時に LINE グループへ通知 | 高 |
| 明細メール着信通知 | 明細案内メールをきっかけに、未取込のときだけ受信メールとアップロード画面の URL を手順つきで LINE 通知 | 高 |
| アプリ内未完了表示 | 対象月の issuer ごとの取込済み／未取込を表示 | 高 |
| 自動アップロード | 個人向け公式APIなし／スクレイピングは非採用 | — |

> **用語**  
> **issuer**: 明細の出所となるカード会社（例: `rakuten` / `amex`）。  
> **custom_hook**: 列マッピング等の設定だけでは表現できない特殊CSV向けの任意逃げ道。通常は未使用（低優先）。
>
> **自動アップロードについて**  
> 楽天・日本Amexとも個人が使える公式明細API／OAuthは現状ない。スクレイピングは規約・Bot対策リスクのため非採用。  
> 代替として (1) 明細案内メールをきっかけにした LINE（未取込の issuer のみ。受信メールとアップロード画面の URL を手順つきで載せる）(2) アプリ内未完了バッジ、で手動CSV取込を促す。詳細は `docs/notifications/line_notification.md`。  
> 同一 `year`/`month`/issuer の再UPは当該発行会社分を置換する。

### 3.2 明細閲覧機能

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| 明細一覧表示 | 日付・利用店名・金額・名義人・カード発行会社・分類元・AI信頼度を一覧表示 | 高 |
| 月次切り替え | 月を選択して過去の明細を参照 | 高 |
| フィルター | カテゴリ・名義人・カード発行会社・未分類でフィルタリング | 中 |
| 月次集計サマリー | カテゴリ別・名義人別の合計金額をグラフで可視化 | 中 |
| 前月比表示 | カテゴリごとに先月との差分を表示 | 低 |

### 3.3 明細仕分け機能

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| カテゴリマスター管理 | 食費・光熱費・交通費・日用品等のCRUD操作 | 高 |
| ルールベース自動分類 | 利用店名の文字列パターンでカテゴリを自動判定 | 高 |
| AI自動分類 | ルール未適用の支払いを OpenAI API で分類 | 高 |
| 手動上書き | AI・ルール分類の結果を手動修正。未分類行と低信頼度AI分類行を色分けし、編集が必要な明細を見つけやすくする | 高 |
| 分類ルール管理 | ルール（店名パターン→カテゴリ）のCRUD操作 | 高 |
| ルール自動追加提案 | 手動修正時に「このルールを追加しますか？」を提案 | 中 |

### 3.4 手動支払い登録・固定費管理

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| 手動支払い登録 | カード明細外の支払いを手動で登録（現金払い等） | 中 |
| 固定費マスター管理 | Netflix・家賃等の固定費をマスターとして管理 | 中 |
| 固定費の月次集計反映 | 固定費マスターから当月分を動的に集計へ反映 | 中 |

### 3.5 通知機能

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| アップロード完了通知 | 取込成功時に、夫婦＋ボットのグループへ LINE 通知 | 高 |
| 明細メール着信通知 | Gmail の明細案内を Apps Script が API に伝え、未取込のときだけ受信メールとアップロード画面の手順を同じグループへ通知する | 高 |
| 予算超過アラート | 設定予算の上限を超えたカテゴリを通知（将来） | 低 |

### 3.6 認証機能

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| メール認証 | Supabase Auth によるメール＋パスワード認証 | 高 |
| ユーザー管理 | 夫・妻の2アカウントのみ登録 | 高 |

### 3.7 その他・将来機能

| 機能 | 詳細 | 優先度 |
|------|------|--------|
| 明細ダウンロード | アップ済み原本ファイルをローカルに保存 | 低 |
| スケジュール共有 | 家族間でのカレンダー・予定共有 | 将来 |

---

## 4. 非機能要件

| 区分 | 要件 |
|------|------|
| セキュリティ | 通信はHTTPS必須。APIキー等は環境変数で管理し、コードにハードコードしない |
| 認証 | Supabase Auth によるメール認証。URLを知っていてもログインなしではアクセス不可 |
| 可用性 | 家族内利用のため24時間稼働は必須でない。Renderのスリープ（15分無操作）は許容 |
| 拡張性 | 将来の機能追加に備え、バックエンドはFeatureごとにモジュール分割する設計 |
| コスト | 無料枠〜低コスト優先（詳細は `memo/infra_cost_comparison.md`）。AIは従量課金 |
| バックアップ | Supabase が自動バックアップを提供（無料プランは7日間保持） |
| 対応デバイス | PC（Chrome/Safari）・iPhone・Android。PWAとしてホーム画面に追加可能 |

---

## 5. 技術スタック

| レイヤー | 技術 | 選定理由 |
|----------|------|----------|
| フロントエンド | Flutter（Dart）— Web ビルド | iOS/Android/Web を1コードでカバー。将来のネイティブ化も容易 |
| 状態管理 | Riverpod | Flutter推奨・テストしやすい |
| HTTPクライアント | Dio | インターセプター・エラーハンドリングが充実 |
| バックエンド | Python 3.11 + FastAPI | CSVパース・AI連携が得意。チュートリアルから入りやすい |
| ORM | SQLAlchemy | FastAPIとの相性が良い |
| データベース | PostgreSQL（Supabase） | 無料枠・GUIで管理しやすい。**本番はコスト優先で維持** |
| ファイルストレージ | Supabase Storage | DBと同サービスで管理が簡単 |
| 認証 | Supabase Auth | Flutter SDKとの連携が数十行で実装可能。無料 |
| AI分類 | OpenAI API | 実装済み経路。店名からのカテゴリ推定 |
| 通知 | LINE Messaging API | 家族運用で導入しやすい |
| ホスティング（API） | Render | GitHub連携で自動デプロイ・無料枠あり |
| ホスティング（Web） | Render（Static Site） | Flutter Webのビルド成果物を配信 |
| CI/CD | GitHub → Render 自動デプロイ | pushするだけで本番反映 |

> AWS への載せ替えは必須としない（学習用は別枠）。比較は `memo/infra_cost_comparison.md`。

---

## 6. システムアーキテクチャ

```
┌─────────────────────────────────────────────┐
│              クライアント                      │
│  ┌─────────────────┐  ┌──────────────────┐  │
│  │  Flutter Web     │  │  PC ブラウザ       │  │
│  │  （スマホ PWA）   │  │  （CSV アップ用）  │  │
│  └────────┬────────┘  └────────┬─────────┘  │
└───────────┼──────────────────────┼────────────┘
            │ HTTPS                │ HTTPS
            ▼                      ▼
┌──────────────────────────────────────────────┐
│              Render                           │
│  ┌──────────────────────────────────────┐   │
│  │  FastAPI サーバー                      │   │
│  │  ├─ 明細アップロード・パース処理         │   │
│  │  ├─ 分類ロジック（ルール / AI）         │   │
│  │  ├─ 月次集計・統計                     │   │
│  │  └─ LINE通知送信                       │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼────────────────────────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
┌──────────────┐    ┌─────────────────┐
│  Supabase    │    │  Claude API      │
│  ├─ PostgreSQL│    │  （Anthropic）   │
│  ├─ Storage  │    │  AI カテゴリ分類 │
│  └─ Auth     │    └─────────────────┘
└──────────────┘
        │
        ▼
┌──────────────┐
│  LINE Notify  │
│  妻・夫へ通知 │
└──────────────┘
```

### データフロー（明細アップロード時）

```
1. 夫がPCブラウザ or スマホから楽天/Amex の CSV（複数可）をアップロード
2. FastAPI がファイルを受け取り、発行会社を判定し Supabase Storage に保存
3. 発行会社別 CSV パーサーが各行を解析（日付・店名・金額・名義人）
4. 分類ロジックを実行
   a. ルールテーブルと照合 → マッチしたらカテゴリ確定
   b. マッチしなければ OpenAI API に店名を渡してカテゴリ推定
   c. AI確信度が低い場合は `category_id = NULL` のまま保存（UI上「未分類」として表示）
5. statement_items テーブルに保存（`year`/`month`/issuer 単位）
6. LINE で妻に「明細がアップされました」と通知
```

---

## 7. データベース設計

### テーブル一覧

#### users（ユーザー）
Supabase Auth が管理。アプリ側では role のみ参照。

| カラム | 型 | 説明 |
|--------|----|------|
| id | UUID PK | Supabase Auth が自動生成 |
| email | TEXT | メールアドレス |
| role | TEXT | `owner`（夫）/ `member`（妻） |

#### categories（カテゴリマスター）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| name | TEXT | 食費・光熱費・交通費 等 |
| color | TEXT | カラーコード（例: `#4CAF50`） |
| sort_order | INT | 表示順 |
| created_at | TIMESTAMPTZ | |

#### classification_rules（分類ルール）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| pattern | TEXT | マッチパターン（例: `イオン`、`AMZN.*`） |
| is_regex | BOOLEAN | 正規表現フラグ |
| category_id | INT FK | 分類先カテゴリ |
| priority | INT | 優先度（大きいほど先に評価） |
| created_at | TIMESTAMPTZ | |

#### statements（明細ファイル）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| year | INT | 対象年 |
| month | INT | 対象月 |
| file_url | TEXT | Supabase Storage の URL |
| uploaded_at | TIMESTAMPTZ | |
| card_issuer_id | INT FK | `card_issuers.id` |
| UNIQUE | (year, month, card_issuer_id) | 同年月・同一 issuer の二重登録防止 |

> 別途 `card_issuers`（code / display_name 等）と `csv_import_profiles`（列マッピング JSON 等）を持つ。詳細は `docs/db/db_design.md`。

#### statement_items（明細行データ＝共通モデル）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| statement_id | INT FK | 明細ファイルへの参照 |
| used_at | DATE | 利用日 |
| shop_name | TEXT | 利用店名・商品名 |
| amount | INT | 利用金額（円） |
| card_holder | TEXT | `夫` / `妻` |
| category_id | INT FK | 分類先カテゴリ |
| classified_by | TEXT | `rule` / `ai` / `manual` |
| ai_confidence | DOUBLE PRECISION | AI確信度 0.0〜1.0 |
| ai_raw_response | TEXT | AIの生レスポンス（デバッグ用） |
| source | TEXT | `csv` / `manual` / `fixed`（PDFは将来） |
| created_at | TIMESTAMPTZ | |

> issuer は `statements.card_issuer_id` 経由。一覧では `card_issuers` を JOIN して code / 表示名を露出する。

#### fixed_expenses（固定費マスター）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| name | TEXT | 例: `Netflix`・`NHK受信料` |
| amount | INT | 金額（円） |
| category_id | INT FK | カテゴリ |
| billing_day | INT | 引き落とし日（例: 27） |
| card_holder | TEXT | `夫` / `妻` / `共通` |
| is_active | BOOLEAN | 有効フラグ |
| valid_from | DATE | 適用開始月 |
| valid_until | DATE | 適用終了月（NULL = 継続中） |

> `valid_from` / `valid_until` で金額変更の履歴を管理する。  
> 値上げ時は旧レコードの `valid_until` を設定し、新レコードを追加することで過去の集計金額を変えずに済む。

#### manual_expenses（手動登録支払い）

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| used_at | DATE | 利用日 |
| shop_name | TEXT | 店名・支払い先 |
| amount | INT | 金額（円） |
| category_id | INT FK | カテゴリ |
| card_holder | TEXT | `夫` / `妻` / `共通` |
| year | INT | 集計対象年 |
| month | INT | 集計対象月 |
| note | TEXT | メモ（任意） |
| created_by | TEXT | `夫` / `妻` |
| created_at | TIMESTAMPTZ | |

### 月次集計ビュー

```sql
CREATE VIEW monthly_expenses AS
  SELECT
    si.used_at, si.shop_name, si.amount,
    si.card_holder, si.category_id,
    si.classified_by, si.source,
    s.year, s.month, s.card_issuer
  FROM statement_items si
  JOIN statements s ON s.id = si.statement_id

  UNION ALL

  SELECT
    me.used_at, me.shop_name, me.amount,
    me.card_holder, me.category_id,
    'manual' AS classified_by, 'manual' AS source,
    me.year, me.month, NULL AS card_issuer
  FROM manual_expenses me;
```

> 固定費は集計時にFastAPI側で `valid_from <= 対象月 AND (valid_until IS NULL OR valid_until >= 対象月)` でフィルタして動的に加算する。

### DDL（初期テーブル作成）

```sql
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

-- 初期カテゴリ
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

---

## 8. API設計

### ベースURL

- 開発環境: `http://localhost:8000`
- 本番環境: `https://xxx.onrender.com`

### エンドポイント一覧

#### 明細

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/statements/detect-issuer` | CSVからissuer推定（確認用） |
| POST | `/statements/upload` | CSV（複数可）をプロファイル駆動で変換・分類（issuer 単位で置換） |
| GET | `/statements` | 明細一覧取得（year・month・category・card_holder・card_issuer 等でフィルタ） |
| GET | `/statements/upload-status` | 対象月の issuer ごとの取込状況 |
| PATCH | `/statements/items/{id}` | カテゴリ手動変更 |
| GET | `/statements/summary` | 月次集計・カテゴリ別合計（任意で card_issuer） |
| CRUD | `/card-issuers`, `/csv-import-profiles` | issuer / 取込プロファイル管理（画面は低優先） |

#### カテゴリ

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/categories` | 一覧取得 |
| POST | `/categories` | 新規作成 |
| PUT | `/categories/{id}` | 更新 |
| DELETE | `/categories/{id}` | 削除 |

#### 分類ルール

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/rules` | 一覧取得 |
| POST | `/rules` | 新規作成 |
| PUT | `/rules/{id}` | 更新 |
| DELETE | `/rules/{id}` | 削除 |

#### 固定費

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/fixed-expenses` | 一覧取得 |
| POST | `/fixed-expenses` | 新規作成 |
| PUT | `/fixed-expenses/{id}` | 更新 |
| DELETE | `/fixed-expenses/{id}` | 無効化（物理削除はしない） |

#### 手動支払い

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/manual-expenses` | 一覧取得（year・monthでフィルタ） |
| POST | `/manual-expenses` | 新規登録 |
| PUT | `/manual-expenses/{id}` | 更新 |
| DELETE | `/manual-expenses/{id}` | 削除 |

---

## 9. 明細分類ロジック

明細の各支払いは以下の優先順位で自動分類される。

```
利用店名
  │
  ▼
① ルールテーブルと照合（priority 降順）
  │ マッチした
  ├──────────────► category_id 確定、classified_by = 'rule'
  │
  │ マッチしなかった
  ▼
② Claude API に店名を渡してカテゴリ推定
  │ 確信度 >= 0.7
  ├──────────────► category_id 確定、classified_by = 'ai'
  │
  │ 確信度 < 0.7
  ▼
③ 未分類のまま保存
     category_id = NULL、classified_by = NULL（UI上は「未分類」と表示）
```

### Claude API へのプロンプト例

```python
f"""
以下のカテゴリ一覧から、「{shop_name}」の支払いに最も合うカテゴリを選んでください。
確信度も0.0〜1.0で答えてください。

カテゴリ:
{category_list}

JSON形式で回答してください:
{{"category_id": 1, "confidence": 0.85}}
"""
```

### 手動修正時のルール追加フロー

```
ユーザーが手動でカテゴリを修正
  │
  ▼
「"店名" を "カテゴリ" のルールに追加しますか？」を提案
  │
  ├─ YES → classification_rules に追加（次回から自動分類）
  └─ NO  → 今回のみ手動分類として保存
```

---

## 10. 認証・セキュリティ設計

### 認証方式

**Supabase Auth（メール＋パスワード）** を採用。

- 登録するアカウントは夫・妻の2件のみ
- 未ログイン状態でURLにアクセスしても、ログイン画面にリダイレクト
- JWTトークンをFlutter側で保持し、APIリクエストのヘッダーに付与

```dart
// ログイン
await supabase.auth.signInWithPassword(
  email: email,
  password: password,
);

// 認証状態の監視
supabase.auth.onAuthStateChange.listen((data) {
  if (data.session == null) {
    // ログイン画面へリダイレクト
  }
});
```

### FastAPI 側の認証検証

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token = Depends(security)):
    user = supabase.auth.get_user(token.credentials)
    if not user:
        raise HTTPException(status_code=401)
    return user
```

### セキュリティ方針

- APIキー・DBパスワードはすべて環境変数で管理（コードにハードコードしない）
- `.env` ファイルは `.gitignore` に追加し、Gitにコミットしない
- Supabase の Row Level Security（RLS）で、ログインユーザー以外のデータアクセスを禁止

---

## 11. 通知設計

正本は `docs/notifications/line_notification.md`（2026-11-23 確定）。

- 配信は LINE Messaging API。宛先は夫婦＋ボットのグループ1つ。
- アップロード完了は、取込成功時にサーバーが送る。
- 取込依頼は、毎月の固定日ではなく、Gmail の明細案内メール。Apps Script が `POST /notify/statement-mail` を呼び、未取込のときだけ「メールで CSV をダウンロードし、アプリのアップロード画面へ上げる」手順と両方の URL を載せる。
- 再通知、cron-job.org、`.ics`、メール本文からの URL 抽出はやらない。

---

## 12. 画面設計

### 画面一覧

| 画面名 | 説明 |
|--------|------|
| ログイン画面 | メール＋パスワード認証 |
| 明細一覧画面 | 月選択・カード種別含むフィルター・取込状況・支払い一覧 |
| 明細仕分け画面 | カテゴリ選択・ルール追加提案 |
| グラフ・集計画面 | カテゴリ別円グラフ・月次推移棒グラフ（カード種別フィルタ可） |
| アップロード画面 | 楽天/Amex CSV の複数一括アップロード |
| カテゴリ管理画面 | カテゴリのCRUD |
| 分類ルール管理画面 | ルールのCRUD |
| 固定費管理画面 | 固定費マスターのCRUD |
| 手動支払い登録画面 | 明細外支払いの手動入力 |

### 設計方針

- **プラットフォーム**: PWA（Flutter Web）— PC・スマホ両対応
- **デザイン**: シンプル・ミニマル
- **スマホ**: ボトムナビゲーション（明細 / グラフ / 履歴 / 設定）
- **PC**: サイドバーナビゲーション（将来対応）

---

## 13. 開発・デプロイフロー

### ローカル開発環境

```
my_app/
├── frontend/          # Flutter プロジェクト
│   ├── lib/
│   │   ├── core/      # APIクライアント・定数
│   │   ├── features/  # 機能ごとのディレクトリ
│   │   │   ├── statements/
│   │   │   ├── categories/
│   │   │   └── auth/
│   │   └── main.dart
│   └── pubspec.yaml
│
└── backend/           # FastAPI プロジェクト
    ├── routers/       # エンドポイント
    ├── models.py      # SQLAlchemy モデル
    ├── database.py    # DB接続設定
    ├── classifier.py  # 分類ロジック
    ├── main.py
    ├── requirements.txt
    └── .env           # ← Gitにコミットしない
```

### 環境変数（backend/.env）

```env
DATABASE_URL=postgresql://...      # Supabase から取得
ANTHROPIC_API_KEY=sk-ant-...
LINE_NOTIFY_TOKEN_WIFE=...
LINE_NOTIFY_TOKEN_HUSBAND=...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=...
```

### デプロイフロー

```
ローカルで開発・動作確認
  │
  ▼
git push origin main
  │
  ▼
GitHub がRenderに通知
  │
  ├─► Render（バックエンド）: pip install → uvicorn 起動
  └─► Render（フロントエンド）: flutter build web → 静的ファイル配信
  │
  ▼
数分で本番に反映
```

### Render の設定

**バックエンド（Web Service）**

```
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Python ランタイムは `runtime.txt` で 3.11 系に固定する。

**フロントエンド（Static Site）**

```
Build Command: flutter build web --dart-define=API_URL=https://xxx.onrender.com
Publish Directory: build/web
```

---

## 14. 開発フェーズ

| フェーズ | 内容 | 目標成果物 |
|----------|------|-----------|
| Phase 1：インフラ基盤 | Supabase DB作成・Render環境構築・FastAPI骨格・Flutter雛形 | `Hello World` APIがFlutterから呼べる状態 |
| Phase 2：認証 | Supabase Auth連携・ログイン画面・ルーティング | ログインしないと使えない状態 |
| Phase 3：コア機能 | 楽天/Amex CSVパース・明細一覧・カテゴリCRUD・ルールベース分類 | 両カードをアップして一覧・手動仕分けができる状態 |
| Phase 4：AI分類・通知 | OpenAI連携・LINE通知・未取込リマインド | 自動分類と通知・リマインドが動く状態 |
| Phase 5：可視化・固定費 | グラフ表示・前月比・固定費管理・手動支払い登録 | 妻が日常的に使えるレベル |
| Phase 6：将来機能 | スケジュール共有・予算アラート・ネイティブアプリ化（検討） | 家族アプリとして拡張 |

---

## 15. 未決事項

- [x] 明細の取込依頼は固定日ではなく明細案内メール（`docs/notifications/line_notification.md`）。再通知はしない
- [ ] LINE のグループ ID とチャネルアクセストークンの取得（P4 着手時）。送信先はグループ1つで確定
- [ ] Amex CSV 実データの列名・文字コード・確定前行の扱い
- [ ] AI分類の確信度しきい値（0.7は仮設定。実際に使いながら調整）
- [ ] Renderのスリープが許容できなくなった場合の有料プラン移行タイミング
- [ ] 楽天カードCSVのカラム名・フォーマット確認（実際にダウンロードして検証が必要）
- [ ] 将来的なネイティブアプリ化の要否（PWAで満足できるか使いながら判断）
- [ ] 固定費と明細の重複計上を防ぐロジックの詳細設計

---

*以上*
