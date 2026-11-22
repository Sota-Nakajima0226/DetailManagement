# 計画書: P1 DB・モデル基盤（issuer / 取込プロファイル）

| 項目 | 内容 |
|------|------|
| 計画ID | PLAN-20261122-p1-issuers-schema |
| 状態 | done |
| 対象仕様 | `docs/plans/ROADMAP-20261122-resume.md` P1 / `docs/db/db_design.md`（`card_issuers`, `csv_import_profiles`, `statements.card_issuer_id`） / `docs/requirements/requirements_definition.md` §4.1 |
| 作成日 | 2026-11-22 |
| 更新日 | 2026-11-22 |
| 前提・制約 | P0確定済み。フロント・汎用CSVエンジン・detect/upload複数・通知APIは **対象外**（P2以降）。空マイグレーション `bb966f0867b6` は使わない。実装はこの計画の Step 実行時のみ。 |

## 背景・ゴール

同月に複数カード会社の明細を持てるよう、issuer マスタ・CSV取込プロファイル・`statements.card_issuer_id` を DB/モデルに導入する。マイグレーション適用後、同月に issuer 違いの `statements` を2件保存でき、シードで楽天・Amexのプロファイル初期値が入っていること。

## 現状ギャップ

- `Statement` は `UNIQUE(year, month)` のみ（`backend/app/models/__init__.py`）
- `card_issuers` / `csv_import_profiles` のモデル・マイグレーション・シードなし
- 取込は楽天列ハードコード（`statements_v2.py`）。プロファイル未使用
- 仕様書側は P0 で更新済み。実装が未追従

## 決定済み方針（本計画内）

- 既存 `statements` 行はすべて **`rakuten` に紐づけて移行**する（現行パーサが楽天専用のため）
- マイグレーション後も現行アップロードが動くよう、**暫定で新規取込も `rakuten` の `card_issuer_id` を付与**する（汎用エンジン化は P2）
- Amex 名義マップはシードで仮置き: `SOTA NAKAJIMA`→`夫`, `SEIRA NAKAJIMA`→`妻`（P0保留どおり。後で変更可）
- `custom_hook` は常に `NULL`（未使用）
- リマインド日初期値: 楽天 `23`、Amex `4`

## 未確定事項

なし

## ステップ一覧

### Step 1: DB設計書に既存データ移行方針を明記

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 破壊的変更の移行ルールを正本に残し、実装とレビューの前提を揃える |
| 対象ファイル（想定） | `docs/db/db_design.md` |
| 完了条件 | 「既存 statements は rakuten に backfill」「制約は UNIQUE(year,month,card_issuer_id)」が本文に明記されている |
| コミット | 要 |
| 依存 | なし |
| 検証 | 該当節を目視確認 |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `docs/db/db_design.md`
- 検証: §5 で `UNIQUE(year, month, card_issuer_id)` を強調。§6「スキーマ移行（issuer 導入時）」に既存行の rakuten backfill 手順を追記。`statements` 補足にも一意制約を明記。目視確認済み
- コミット案: docs: issuer導入時のstatements移行方針をDB設計に明記

### Step 2: SQLAlchemy モデル追加と Alembic マイグレーション

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | スキーマを仕様どおりに変更し、既存行を安全に移行する |
| 対象ファイル（想定） | `backend/app/models/__init__.py`, `backend/alembic/versions/<新リビジョン>.py` |
| 完了条件 | `CardIssuer` / `CsvImportProfile` モデルがある。`Statement.card_issuer_id` FK と `UNIQUE(year, month, card_issuer_id)`。マイグレーションで (1) 新テーブル作成 (2) issuers 最低限の挿入または後続シード前提の FK 可能な順序 (3) `card_issuer_id` 追加・既存行を rakuten に更新 (4) NOT NULL 化 (5) 旧 UNIQUE 削除。`alembic upgrade head` が成功する |
| コミット | 要 |
| 依存 | Step 1 |
| 検証 | `cd backend && python -m alembic upgrade head`。必要なら downgrade も一度試す |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `backend/app/models/__init__.py`, `backend/alembic/versions/0a538038914e_add_card_issuers_and_statement_issuer_fk.py`
- 検証: モデル import OK。`alembic upgrade head --sql` で c91a4f5b3d22→0a538038914e の SQL（テーブル作成・rakuten INSERT・backfill・NOT NULL・旧 UNIQUE 削除・新 UNIQUE）を確認。一方 `alembic upgrade head` は `DATABASE_URL` のホスト `db.ailgbdzljwgdkqglweaf.supabase.co` が NXDOMAIN で接続不可のため未成功。ローカル Postgres / Docker も無し
- メモ: 実装自体は完了条件のコード側を満たす。`backend/.env` の `DATABASE_URL` を到達可能な DB に直し、`cd backend && .venv/bin/python -m alembic upgrade head`（任意で downgrade -1 → 再 upgrade）が通ったら本 Step を `done` にできる
- コミット案: feat: add card_issuers models and migration with rakuten backfill
- 実施日: 2026-11-22（再実行・検証完了）
- 変更ファイル: 同上（追加コード変更なし）
- 検証: Supabase Resume 後に接続復旧。`alembic upgrade head` → `downgrade -1` → `upgrade head` 成功（head=`0a538038914e`）。DB 確認: `card_issuers` に rakuten、`statements.card_issuer_id` NOT NULL・null 0件、UNIQUE は `uq_statements_year_month_card_issuer_id` のみ
- コミット案: feat: add card_issuers models and migration with rakuten backfill

### Step 3: 楽天・Amex のシード（issuer + 取込プロファイル）

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | `sample/rakuten` / `sample/amex` に基づく初期プロファイルを投入できるようにする |
| 対象ファイル（想定） | `backend/master_data/card_issuers.json`（新規）, `backend/master_data/csv_import_profiles.json`（新規）, `backend/scripts/seed_master_data.py`, 必要なら `backend/master_data/README.md` |
| 完了条件 | シード実行で `rakuten`/`amex` と各1件のプロファイルが入る（encoding・header_signature・column_mapping・transforms が `docs/db/db_design.md` の表と整合）。再実行で upsert 可能 |
| コミット | 要 |
| 依存 | Step 2 |
| 検証 | `python scripts/seed_master_data.py`（`backend` カレント、`DATABASE_URL` 設定済み）。DB で2 issuer・2 profile を確認 |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `backend/master_data/card_issuers.json`, `backend/master_data/csv_import_profiles.json`, `backend/scripts/seed_master_data.py`, `backend/master_data/README.md`
- 検証: `python scripts/seed_master_data.py` を2回実行して成功。DB に issuer 2件（rakuten/amex）・profile 2件。encoding・mapping・transforms は db_design §9 と整合、`custom_hook` は NULL
- メモ: シード全体実行時に `fixed_expenses.valid_from` の文字列比較が psycopg で失敗したため、ISO 日付を `date` に変換する最小修正を同スクリプトに追加
- コミット案: feat: seed card issuers and csv import profiles for rakuten and amex

### Step 4: 現行アップロードの暫定互換（常に rakuten）

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | NOT NULL の `card_issuer_id` 導入後も、P2 まで既存の単一CSV取込が落ちないようにする |
| 対象ファイル（想定） | `backend/app/api/statements_v2.py`（最小差分）, 必要ならスキーマ |
| 完了条件 | 新規/再アップロードで `Statement.card_issuer_id` に楽天の id が入る。置換は従来どおり同年月の当該行（現状1件）を消して再作成。複数 issuer の置き換えロジックはまだ入れない |
| コミット | 要 |
| 依存 | Step 2（Step 3 推奨） |
| 検証 | 認証付きで楽天サンプルCSVを1件 upload → DB の `card_issuer_id` が rakuten。一覧取得が 500 にならない |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `backend/app/api/statements_v2.py`
- 検証: TestClient + `get_current_user` override で楽天サンプルCSVを upload（201）。DB の `card_issuer_id` が rakuten。`GET /statements` は 200。検証用 2099/1 行は削除済み
- メモ: 置換対象は `year/month/rakuten` に限定（他 issuer 行は触らない）
- コミット案: fix: attach rakuten issuer on statement upload for interim compatibility

### Step 5: P1 完了検証（同月2 issuer）

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | ロードマップ P1 完了条件を満たすことを確認する |
| 対象ファイル（想定） | なし（SQL または一時スクリプト。成果物は計画書の作業結果のみで可） |
| 完了条件 | 同一 year/month で `card_issuer_id` の異なる `statements` を2件 INSERT できること、および UNIQUE 違反が「同一 issuer の二重」でのみ起きること、を確認し本 Step の作業結果に記録した |
| コミット | 不要 |
| 依存 | Step 2, Step 3 |
| 検証 | psql / SQLAlchemy で手動 INSERT 2件 → 成功。同じ issuer でもう1件 → UNIQUE エラー |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: なし（検証のみ）
- 検証: year=2098/month=6 で rakuten・amex の `statements` を2件 INSERT → 成功。同月・rakuten の二重 INSERT → `uq_statements_year_month_card_issuer_id` の UniqueViolation。検証行は削除済み

## 実行ルール（人間向け）

- 実行は「計画ファイルパス + Step 番号（複数可）」で指示する
- 状態が `ready` または `in_progress` のときだけ実行スキルを使う
- コミットは人間が行う（実行スキルはメッセージ案のみ提示）
- 次工程: P2（汎用CSVエンジン・detect・複数upload）は別計画書で切る
