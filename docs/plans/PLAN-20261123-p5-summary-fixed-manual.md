# 計画書: P5 集計への手動支払い・固定費反映

| 項目 | 内容 |
|------|------|
| 計画ID | PLAN-20261123-p5-summary-fixed-manual |
| 状態 | done |
| 対象仕様 | `docs/plans/ROADMAP-20261122-resume.md` P5 の集計 / `docs/api/api_specification.md` §3.1 の summary 3本 / `docs/db/db_design.md` §7 / `docs/screens/screen_specification.md` SCR-004 / `docs/requirements/requirements_definition.md` §4.4 と §9 |
| 作成日 | 2026-11-23 |
| 更新日 | 2026-11-23 |
| 前提・制約 | P3 の集計（カテゴリ別・名義人別・月次推移と任意 `card_issuer`）まで完了済み。本計画は P5 のうち集計だけ。ルール追加提案、Supabase Storage、再アップロード時の手動仕分け保持は対象外。明細一覧（SCR-002 / `GET /statements`）には手動か固定費を出さない。集計レスポンスの形は変えない。`fixed_expenses` / `manual_expenses` に発行会社列は足さない。`card_issuers` に固定費用の行は足さない。スキーマ変更は `monthly_expenses` ビューの追加だけ。`sample/` はコミット禁止。コミットメッセージは日本語。 |

## 背景・ゴール

月次の合計に、カード明細に載らない支払いを含める。発行会社を選んでいない集計は、カード明細・手動支払い・対象月に有効な固定費の合計になる。発行会社を選んだ集計は、そのカードの明細だけになる。完了時点で、明細が無い月でも固定費か手動があればグラフが出て、未取込バッジは残る。

## 現状ギャップ

- `GET /statements/summary`、`by-holder`、`monthly-trend` は `statement_items` だけを足している。手動と固定費は CRUD があるが合計に入らない
- `docs/db/db_design.md` の `monthly_expenses` は設計のみで、マイグレーションが無い
- 固定費をどの月に、発行会社フィルタとどう組み合わせるかが、API 仕様と画面仕様に書いていない
- 要件の未決に「固定費と明細の重複計上防止」が残っている。運用は、明細に入らない支払いだけを固定費にする
- SCR-004 は `upload-status.uploaded` が空だと集計 API を呼ばず、グラフを出さない。固定費だけの月が見えない

## 決定済み方針（本計画内）

- 二重計上の自動除外はしない。固定費は明細に載らない支払いとして登録する
- 固定費にも手動支払いにも発行会社は持たせない。ビュー上の発行会社は NULL のまま。固定費用の `card_issuers` 行は作らない
- 発行会社未指定（クエリ省略、または空文字）のとき、次を同じカテゴリ・同じ名義人へ合算する
  - 全発行会社のカード明細
  - `manual_expenses.year` / `month` が対象年月の手動支払い。利用日が別月でも、この年月に従う
  - 対象月に有効、かつ `is_active = true` の固定費
- 発行会社を指定したときは、その `card_issuers.code` の明細だけ。手動と固定費は足さない。未知の code は明細 0 件で、手動と固定費も足さない
- 対象は3本とも。カテゴリ別、名義人別、月次推移。月次推移は期間内の各月に同じ規則を適用する。`category_id` 指定時は、そのカテゴリの手動・固定費だけを足す
- レスポンスのキーは変えない。内訳（明細／手動／固定費）は返さない。同じ `category_id` は一つの `amount` にまとめてから、現状どおり金額の降順にする
- 名義人が NULL の手動は、明細と同じく `共通` にまとめる。固定費の既定は `共通`
- 固定費が対象月に入る条件は、期間がその月のどこか1日でも重なること。`valid_from` がその月の末日以前、かつ `valid_until` が NULL またはその月の1日以降。満額を足し、日割りしない。`billing_day` は集計に使わない。`is_active = false` は期間内でも足さない
- 例: `valid_from = 2026-03-15` かつ `valid_until` が NULL なら 2026-03 から満額。`valid_until = 2026-03-01` なら 2026-03 は含め、2026-04 は含めない。`valid_from = 2026-04-01` なら 2026-03 は含めない
- 明細一覧の空表示と行は変えない
- SCR-004 は、取込の有無にかかわらず3本の集計を取る。表示中の絞り込みで当月のカテゴリ合計が1件以上あれば、集計カードとタブを出す。当月のカテゴリ合計が空、かつ `uploaded` が空のときだけ、今の「対象年月の明細はまだアップロードされていません」を出し、集計カードとタブは出さない。アップロードが1件以上あるのに絞り込み結果が空のときは、今どおり集計カードとタブを出す。未取込バッジはどちらの場合も残す

## 未確定事項

なし

## ステップ一覧

### Step 1: 集計条件を仕様へ書く

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 実装の前に、合算規則・発行会社の扱い・グラフの空表示を正本で一致させる |
| 対象ファイル（想定） | `docs/api/api_specification.md` §3.1 の summary 3本、`docs/db/db_design.md` §7、`docs/screens/screen_specification.md` SCR-004、`docs/requirements/requirements_definition.md` §4.4 と §9。`requirements_and_design.md` は未決の重複計上の1項目と、固定費を動的加算すると書いた1文だけ |
| 完了条件 | 3本の集計について、未指定時は明細・手動・有効な固定費の合算、指定時は明細だけ、と書いてある。レスポンス例の形は変えていない。DB 設計に、ビューは明細と手動だけ、固定費は API で足す、重なり判定・満額・`is_active`・`billing_day` 不使用・重複除外なし、が書いてある。SCR-004 の空表示が決定済み方針と一致し、SCR-002 の空表示は変えていない。要件 §9 の重複計上の未決が閉じ、明細に載らない支払いを固定費にする運用が §4.4 にある。`requirements_and_design.md` の当該未決が閉じ、古い記述（Claude API 等）は触っていない。見出しを増やした場合は各文書の目次も更新している |
| コミット | 要 |
| 依存 | なし |
| 検証 | 4文書と直下の該当文を目視し、未指定／指定、空表示、重複除外なしが矛盾しないこと |

**コミット案:** 月次集計に手動支払いと固定費を含める条件を仕様へ書く

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `docs/api/api_specification.md`, `docs/db/db_design.md`, `docs/screens/screen_specification.md`, `docs/requirements/requirements_definition.md`, `requirements_and_design.md`
- 検証: 目視。summary / by-holder / monthly-trend は、未指定（省略または空文字）が明細・手動・有効な固定費の合算、指定時と未知 code が明細だけ、で一致。レスポンス例のキーは変更なし。`docs/db/db_design.md` §7 はビューが明細と手動だけ、固定費は API が重なり判定で満額加算、`is_active`、`billing_day` 不使用、重複除外なし。SCR-004 の空表示は決定済み方針と同じ。SCR-002 の空表示は変更なし。要件 §9 から重複計上の未決を外し、§4.4 に明細へ載らない支払いを固定費とする運用を書いた。`requirements_and_design.md` は動的加算の1文と未決1項目だけを閉じ、Claude API の記述は未変更。見出しは増やしていない
- コミット案: 月次集計に手動支払いと固定費を含める条件を仕様へ書く

### Step 2: カード明細と手動支払いの月次ビュー

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 設計済みの `monthly_expenses` を作り、明細と手動を一つの行集合にする |
| 対象ファイル（想定） | `backend/alembic/versions/` の新規リビジョン。列が設計とずれた場合だけ `docs/db/db_design.md` §7 |
| 完了条件 | ビューが設計書の SELECT と一致する。明細側は `card_issuers.code` / `display_name` を持ち、手動側の発行会社は NULL、`classified_by` と `source` は `manual`。固定費の行はビューに無い。既存テーブルの列とデータは変わらない。downgrade でビューだけ消える |
| コミット | 要 |
| 依存 | Step 1 |
| 検証 | `cd backend && .venv/bin/python -m alembic upgrade head`。続けて `downgrade -1` と再 `upgrade head` でビューの出し入れだけであることを確認する。autogenerate はビューを落とすことが多いので、リビジョンは手書きの `CREATE VIEW` / `DROP VIEW` にする |

**コミット案:** カード明細と手動支払いをまとめる月次ビューを追加

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/alembic/versions/e5a91c3b7d42_add_monthly_expenses_view.py`
- 検証: `alembic upgrade head` で `b7c1e2a94d10` から `e5a91c3b7d42`。ビュー列は設計書の SELECT と同じ（明細側は `card_issuer_code` / `card_issuer_name`、手動側は発行会社 NULL、`classified_by` と `source` は `manual`）。定義に `fixed_expenses` は無い。適用前の行数は card_issuers 2、statements 3、statement_items 219、manual_expenses 0、fixed_expenses 3、categories 10、classification_rules 21、csv_import_profiles 2、users 3、statement_mail_notifications 0。ビュー行は明細 219 件だけ。`downgrade -1` でビューだけ消え、同じ行数のまま `b7c1e2a94d10` に戻った。再 `upgrade head` でビューが戻り、テーブル行数は変わらなかった
- メモ: 手動支払いは 0 件のため、ビュー上の manual 行は出ていない。列は設計とずれていないので `docs/db/db_design.md` は変更していない
- コミット案: カード明細と手動支払いをまとめる月次ビューを追加

### Step 3: 3本の月次集計へ手動と固定費を合算する

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 未指定の集計だけ手動と固定費を足し、指定時はカード明細のままにする |
| 対象ファイル（想定） | `backend/app/services/` の集計用モジュール新規、`backend/app/api/statements_v2.py` の summary 3本、`backend/tests/` の新規テスト。レスポンス用スキーマは変えない |
| 完了条件 | 未指定のカテゴリ別・名義人別・月次推移が、ビューの明細と手動に、重なる有効な固定費を足した金額になる。同じカテゴリは1行にまとまる。発行会社指定時と未知 code では手動と固定費が入らない。空文字の `card_issuer` は未指定と同じ。`billing_day`、日割り、店名での重複除外はしていない。`GET /statements` の行は明細のまま。レスポンスのキーは現状のまま |
| コミット | 要 |
| 依存 | Step 2 |
| 検証 | `cd backend && .venv/bin/python -m unittest tests.test_monthly_summary`（ファイル名は実装に合わせる）。sqlite 上にテーブルと Step 2 と同じビューを作り、次を見る。3月開始の固定費は2月に入らず3月から満額。`valid_until` がその月の1日ならその月だけ入る。`is_active = false` は入らない。手動は `year` / `month` に従い、利用日では振られない。発行会社指定時は明細だけ。未指定時は明細・手動・固定費の合計がカテゴリ別と名義人別と、その月の推移点で一致する |

**コミット案:** 月次集計に手動支払いと固定費を合算する

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/services/monthly_summary.py`, `backend/app/api/statements_v2.py`, `backend/tests/test_monthly_summary.py`
- 検証: `cd backend && .venv/bin/python -m unittest tests.test_monthly_summary` は 11 件成功。sqlite 上の Step 2 と同じビューで、3月15日開始の固定費 5000 円は2月に入らず3月から満額。`valid_until = 2026-03-01` の固定費は3月だけ。`is_active = false` の 7000 円は入らない。手動は `year` / `month` に従い、利用日が別月でも振り替わらない。店名が同じ「サブスク」の明細 2000 円と固定費 5000 円は両方入る。発行会社指定と未知 code は明細だけ。空文字は未指定と同じ。3月の未指定合計 11799 円がカテゴリ別・名義人別・推移点で一致。レスポンスのキーは現状のまま。`GET /statements` の3月は明細2行だけ
- メモ: レスポンス用スキーマは変更していない。`billing_day` と日割りは集計に使っていない
- コミット案: 月次集計に手動支払いと固定費を合算する

### Step 4: 明細が無くても合計があればグラフを出す

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 固定費や手動だけの月を、グラフ画面で見られるようにする |
| 対象ファイル（想定） | `frontend/lib/features/analytics/presentation/analytics_page.dart`。API クライアントのクエリとレスポンス解釈は変えない。明細一覧は触らない |
| 完了条件 | `uploaded` が空でも3本の集計を呼ぶ。当月のカテゴリ合計が1件以上なら集計カードとタブを出す。合計が空かつ `uploaded` が空のときだけ、今の未アップロード文言になり、集計カードとタブは出ない。アップロードがある月の絞り込み結果が空でも、その文言にはしない。未取込バッジは残る。発行会社のドロップダウンは未指定が合算、指定時は3本すべてに同じ code を渡す |
| コミット | 要 |
| 依存 | Step 3 |
| 検証 | グラフ画面で、両カード未取込かつ固定費または手動がある月は合計・円グラフ・名義人別が出る。そこで発行会社を選ぶと未アップロード文言に戻る。両カード未取込かつ手動か固定費も無い月は今の文言のまま。片方だけ取込済みの月は、今どおりグラフと未取込バッジが出る。明細一覧に手動か固定費の行が無いこと。画面を変えたので、ブラウザでこの流れを操作して確認する |

**コミット案:** 明細がなくても固定費と手動があればグラフを出す

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `frontend/lib/features/analytics/presentation/analytics_page.dart`
- 検証: `dart analyze lib/features/analytics/presentation/analytics_page.dart` は問題なし。ブラウザでグラフ画面を操作した。2026年11月の発行会社「すべて」は両カード未取込のまま、合計 27,000 円・円グラフ・カテゴリ別・名義人別が出た。同じ月で楽天を選ぶと「対象年月の明細はまだアップロードされていません」になり、集計カードとタブは消え、未取込バッジは残った。2026年4月の「すべて」は楽天が取込済み、Amex は未取込バッジのままグラフが出た。2026年4月を Amex に絞ると合計 0 円でも集計カードとタブが残り、未アップロード文言にはならなかった。2025年4月の「すべて」は明細も固定費も無く、未アップロード文言のまま。明細一覧の 2026年11月は件数 0 で、固定費の行は無かった
- メモ: API クライアントのクエリとレスポンス解釈、明細一覧は変更していない
- コミット案: 明細がなくても固定費と手動があればグラフを出す

## 実行ルール（人間向け）

- 実行は「計画ファイルパス + Step 番号（複数可）」で指示する
- 状態が `ready` または `in_progress` のときだけ実行スキルを使う
- コミットは人間が行う（実行スキルはメッセージ案のみ提示）
