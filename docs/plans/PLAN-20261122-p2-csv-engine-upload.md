# 計画書: P2 取込エンジン・明細API

| 項目 | 内容 |
|------|------|
| 計画ID | PLAN-20261122-p2-csv-engine-upload |
| 状態 | done |
| 対象仕様 | `docs/plans/ROADMAP-20261122-resume.md` P2 / `docs/api/api_specification.md` §3.1・§3.6・§5 / `docs/db/db_design.md`（取込プロファイル） / `docs/requirements/requirements_definition.md` §4.1 |
| 作成日 | 2026-11-22 |
| 更新日 | 2026-11-23 |
| 前提・制約 | P1（issuer / プロファイル / `statements.card_issuer_id`）完了済み。**フロント（P3）・LINE通知（P4）・Supabase Storage（P5）は対象外**。`custom_hook` は未使用のまま。`sample/` はコミット禁止（ローカル検証のみ）。コミットメッセージは日本語。P2 中は現行フロントの取込が一時壊れる（P3 で復旧）。 |

## 背景・ゴール

楽天ハードコードの CSV 取込をやめ、DB の取込プロファイルを読む汎用エンジンと、detect / 複数 upload / upload-status / issuer 系 CRUD を API として揃える。完了時点で、楽天・Amex サンプルを同じエンジン経路で取り込め、API 仕様の該当節と実装が一致していること。

## 現状ギャップ

- 取込は `statements_v2.py` の楽天列ハードコード＋暫定 `rakuten` 固定（P1 Step 4）
- 汎用エンジン・`detect-issuer`・`upload-status`・複数ファイル `results[]` 未実装
- 一覧／集計に `card_issuer` フィルタ・`card_issuer_code` / `card_issuer_name` 未露出
- `/card-issuers`・`/csv-import-profiles` CRUD 未実装
- シード（楽天・Amex プロファイル）は P1 で投入済み。エンジンが未使用

## 決定済み方針（本計画内）

- 会社専用パーサは追加しない。差分は `csv_import_profiles` のみ
- `custom_hook` は常に無視（NULL 前提）
- Storage 保存・アップロード完了 LINE は本計画ではスキップ（仕様上「未実装の場合あり」）
- detect の照合は、当面 **`header_signature` の全要素が CSV ヘッダに含まれる（順序不問）** を一致とする。複数一致時は候補に並べ、`detected_code` は一意ならその code、曖昧なら `null`
- Amex 名義マップはシードの仮置きをそのまま使う（P0 保留の正式化は本計画外）
- 検証は `sample/rakuten` / `sample/amex` をローカル参照（Git に追加しない）
- **upload 契約（Q1=A）**: `multipart` の `files`（1件以上）とレスポンス `results[]` に切替える。旧単一 `file` / 単一オブジェクト応答は維持しない。P3 でフロントを追従する
- **issuer 指定（Q2=A）**: `card_issuer_codes` を `files` と**同じ順序**の繰り返しフィールドで送る（各要素は `rakuten` / `amex` 等の code）。件数不一致は 400。未指定時のみサーバ再判定可（仕様どおり。確認済み code 送付を正とする）

## 未確定事項

なし

## ステップ一覧

### Step 1: upload / detect の multipart・レスポンス契約を API 仕様に確定

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 決定済みの upload 契約（`files` / `card_issuer_codes` / `results[]`）を API 正本に明記する |
| 対象ファイル（想定） | `docs/api/api_specification.md`（必要なら要件の取込節） |
| 完了条件 | `POST /statements/upload` に `files`・順序付き `card_issuer_codes`・`results[]`、旧 `file` 非互換が本文で分かる |
| コミット | 要 |
| 依存 | なし |
| 検証 | 該当節の目視 |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `docs/api/api_specification.md`
- 検証: §3.1 upload に `files` / 順序付き `card_issuer_codes` / 件数不一致400 / 旧 `file` 非互換 / `results[]` を明記。§5 に detect 照合と codes 添付の流れを追記。目視確認済み
- コミット案: upload APIのfilesとcard_issuer_codes契約を仕様に明記

### Step 2: 汎用 CSV 取込エンジン（サービス）と単体テスト

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | encoding / header_signature / column_mapping / transforms / skip_rules を解釈し共通モデル行を返すエンジンを切り出す |
| 対象ファイル（想定） | `backend/app/services/csv_import_engine.py`（新規）, `backend/tests/test_csv_import_engine.py`（新規）。必要なら小さなヘルパ |
| 完了条件 | プロファイル dict（またはモデル相当）を渡し、楽天・Amex のローカル `sample/` CSV から `used_at` / `shop_name` / `amount` / `card_holder` が期待どおり取れる。ハードコード列名に依存しない。`custom_hook` は未対応でよい |
| コミット | 要 |
| 依存 | Step 1 |
| 検証 | `cd backend && .venv/bin/python -m unittest tests.test_csv_import_engine`（または同等）。`sample/` はテストからパス参照のみ |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `backend/app/services/csv_import_engine.py`, `backend/tests/test_csv_import_engine.py`
- 検証: `python -m unittest tests.test_csv_import_engine -v` → 5 tests OK（楽天・Amex sample、skip_rules、シグネチャ不一致）
- コミット案: プロファイル駆動の汎用CSV取込エンジンを追加

### Step 3: `POST /statements/detect-issuer`

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | アップロード前確認用の issuer 推定 API を提供する |
| 対象ファイル（想定） | `backend/app/api/statements_v2.py` または分割ルータ, `backend/app/schemas/__init__.py` |
| 完了条件 | 仕様のレスポンス形（`detected_code` / `candidates` 等）で、楽天・Amex サンプルがそれぞれ正しく推定される。判定不能時は `detected_code = null` |
| コミット | 要 |
| 依存 | Step 2 |
| 検証 | 認証付き（または TestClient + auth override）でサンプルを POST |

**作業結果:**
- 実施日: 2026-11-22
- 変更ファイル: `backend/app/api/statements_v2.py`, `backend/app/schemas/__init__.py`, `backend/app/services/csv_import_engine.py`（`peek_csv_headers`）
- 検証: TestClient + auth override で楽天→`rakuten`/`high`、Amex→`amex`/`high`、無関係CSV→`detected_code=null`・candidates空。エンジン既存テストも OK
- コミット案: CSVヘッダからissuerを推定するdetect-issuer APIを追加

### Step 4: `POST /statements/upload` をプロファイルエンジン＋issuer 単位置換へ置換

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 暫定楽天固定／列ハードコードをやめ、Step 1 で確定した契約で取込する |
| 対象ファイル（想定） | `backend/app/api/statements_v2.py`, `backend/app/schemas/__init__.py` |
| 完了条件 | 指定（または再判定）した issuer のプロファイルで変換・分類・保存。同一 year/month/issuer は置換。楽天ハードコードパスが残っていない。レスポンスが Step 1 の契約どおり |
| コミット | 要 |
| 依存 | Step 2, Step 3（再判定パスを使う場合） |
| 検証 | 楽天CSV取込成功。AmexCSV取込成功（同月2 issuer）。再UPで当該 issuer のみ置換 |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/api/statements_v2.py`, `backend/app/schemas/__init__.py`
- 検証: `files`+`card_issuer_codes` で楽天+Amex 同月取込 201/`results[]`。楽天のみ再UPで Amex 行・件数維持。旧 `file` は 422。楽天列ハードコード／暫定 rakuten 固定を削除
- コミット案: 明細uploadをプロファイルエンジンと複数ファイル対応に置換

### Step 5: `upload-status` と一覧・集計の issuer 対応

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | P3/P4 が使う取込状況と、明細・集計の issuer フィルタ／露出を揃える |
| 対象ファイル（想定） | `backend/app/api/statements_v2.py`, `backend/app/schemas/__init__.py` |
| 完了条件 | `GET /statements/upload-status` が `include_in_reminder` かつ `is_active` の expected / uploaded / missing を返す。`GET /statements` に `card_issuer` フィルタと `card_issuer_code` / `card_issuer_name`。summary / by-holder に任意 `card_issuer` |
| コミット | 要 |
| 依存 | Step 4（取込データがある前提の検証が容易） |
| 検証 | 同月に楽天のみ取込 → missing に amex。一覧を issuer で絞れる |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/api/statements_v2.py`, `backend/app/schemas/__init__.py`
- 検証: 楽天のみ取込後 `upload-status` で uploaded=rakuten / missing=amex。一覧 `card_issuer=rakuten` で code/name 付き、amex 絞りは空。summary / by-holder の issuer フィルタ 200
- コミット案: 取込状況APIと明細・集計のissuerフィルタを追加

### Step 6: `/card-issuers`・`/csv-import-profiles` CRUD API

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 画面なしでもカード追加・プロファイルメンテができる API を用意する（SCR-010 は P7） |
| 対象ファイル（想定） | `backend/app/api/card_issuers.py`（新規想定）, `backend/app/api/csv_import_profiles.py`（新規想定）, `backend/main.py`, schemas |
| 完了条件 | 仕様 §3.6 の一覧・作成・更新・削除（issuer は論理削除＝`is_active=false` 想定）が動く。認証必須 |
| コミット | 要 |
| 依存 | Step 1（契約が仕様どおりであることの確認）。DB モデルは P1 済み |
| 検証 | TestClient で作成→取得→更新。削除後は detect / upload-status の対象外になること |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/api/card_issuers.py`, `backend/app/api/csv_import_profiles.py`, `backend/main.py`, `backend/app/schemas/__init__.py`
- 検証: issuer/profile の作成・更新・取得、issuer 論理削除後に upload-status / detect から除外、profile 物理削除 204、未認証 401
- コミット案: カード発行会社と取込プロファイルのCRUD APIを追加

### Step 7: P2 完了検証と API 仕様の最終整合

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | ロードマップ P2 完了条件を満たすことを確認し、docs と実装の差分を残さない |
| 対象ファイル（想定） | 必要なら `docs/api/api_specification.md` のみ（実装に合わせた微修正）。成果の本体は本 Step の作業結果 |
| 完了条件 | 楽天・Amex をプロファイル経由で取込可能。detect →（確認用 code）→ upload 一連が通る。upload-status の missing が妥当。ハードコード列取込が除去済み。仕様と実装の食い違いがあれば同作業で docs を直した |
| コミット | 要（docs 差分がある場合）／不要（記録のみの場合） |
| 依存 | Step 3, Step 4, Step 5, Step 6 |
| 検証 | 上記一連を手動またはスクリプトで実行し、結果を作業結果に記載 |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `docs/api/api_specification.md`, `docs/plans/ROADMAP-20261122-resume.md`（P2 完了条件を checked）
- 検証: detect(楽天/Amex)→codes付き複数upload→両社 uploaded・missing空。Amex行削除後 missing=amex。upload 内に楽天列ハードコードなし。`unittest` エンジン5件 OK。CRUD 一覧 200
- メモ: §3.6 に issuer 論理削除の応答・profile 204・active/reminder 対象範囲・UNIQUE 400 を追記して実装と整合
- コミット案: P2完了検証に合わせAPI仕様とロードマップを更新

## 実行ルール（人間向け）

- 実行は「計画ファイルパス + Step 番号（複数可）」で指示する
- 状態が `ready` または `in_progress` のときだけ実行スキルを使う
- コミットは人間が行う（実行スキルはメッセージ案のみ提示・**日本語**）
- 次工程: P3（デュアルカード UI）は別計画書で切る
