# 計画書: P3 デュアルカード UI

| 項目 | 内容 |
|------|------|
| 計画ID | PLAN-20261123-p3-dual-card-ui |
| 状態 | in_progress |
| 対象仕様 | `docs/plans/ROADMAP-20261122-resume.md` P3 / `docs/screens/screen_specification.md` SCR-002・SCR-003（表示のみ）・SCR-004・SCR-005 / `docs/api/api_specification.md` §3.1 |
| 作成日 | 2026-11-23 |
| 更新日 | 2026-11-23 |
| 前提・制約 | P2 完了済み（`files` + 順序付き `card_issuer_codes` + `results[]`、detect、upload-status、一覧・summary・by-holder の `card_issuer`）。**DB スキーマ変更なし。** LINE（完了通知・明細メール・`/upload?year=&month=` の直リンク）、SCR-010、Storage、集計への固定費・手動反映、仕分けのルール追加提案は対象外（P4 以降）。`sample/` はコミット禁止。コミットメッセージは日本語。 |

## 背景・ゴール

P2 で壊れたままの単一ファイル取込 UI を、複数 CSV の判定確認つきアップロードに戻し、一覧と集計で発行会社を区別できるようにする。完了時点で、同じ月の楽天と Amex を画面から続けて取り込み、一覧に両方出て、未取込バッジが `upload-status` と一致していること。

## 現状ギャップ

- `UploadPage` は単一 `file` と PDF 選択肢のまま。`POST /statements/upload` の現行契約（`files` / `results[]`）と不一致で取込できない
- detect、issuer 手動修正、issuer 単位の置換確認、ファイルごとの取込結果がない
- 一覧・集計・仕分けに発行会社の表示・フィルタ・取込状況バッジがない。`StatementItem` は `card_issuer_code` / `card_issuer_name` を読んでいない
- `GET /statements/summary` と `by-holder` は `card_issuer` 対応済み。`GET /statements/summary/monthly-trend` だけ未対応で、SCR-004 のフィルタを月次推移に渡せない
- アプリ内の年月引き渡し（`UploadPage.initialYear` / `initialMonth`）はある。URL 直リンクは未配線（P4）

## 決定済み方針（本計画内）

- 表示名は API の `display_name` または `card_issuer_name` を使う。画面に「楽天」「Amex」を直書きしない
- ファイル選択は CSV のみ・複数可。選択直後にファイルごと `POST /statements/detect-issuer`。判定結果は表示名で見せ、未確定は `GET /card-issuers` の `is_active=true` から選ぶまでアップロードしない
- アップロードは確認済み code を `files` と同じ順の繰り返しフィールド `card_issuer_codes` で送る。旧 `file` / 単一オブジェクト用クライアントは削除する
- 同一選択内で code が重複したら送らない（サーバ 400 を待たない）
- 置換確認は、選択中の code と `upload-status.uploaded` の交差があるときだけ。表示名を列挙して一括で聞く。キャンセルなら送らない。月全体の `hasStatementsInMonth` は使わない
- バッジは `upload-status` の `expected_issuers` を表示し、`missing` を未取込として強調する。一覧・集計・アップロードで同じウィジェットを使う
- 一覧の issuer 絞り込みは既存の絞り込みシートに追加する。集計は画面上の簡易ドロップダウン（未指定は全 issuer 合算）とし、カテゴリ別・名義人別・月次推移の三つに同じ code を渡す
- 一覧が空のとき: 絞り込みなしで `uploaded` が空なら「対象年月の明細はまだアップロードされていません」。絞り込み中の 0 件は「条件に該当する明細はありません」
- 集計は `uploaded` が空のとき、集計カードとタブを出さず「対象年月の明細はまだアップロードされていません」
- 明細行は既存の ListTile の副題に発行会社名を足す。SCR-003 は発行会社名の表示だけ追加する
- 月次推移へフィルタを効かせるため、任意クエリ `card_issuer` を API に追加する（未指定時の合算は維持）

## 未確定事項

なし

## ステップ一覧

### Step 1: 月次推移の `card_issuer` を API 仕様に追記

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | SCR-004 の発行会社フィルタを月次推移にも渡せる契約を正本に書く |
| 対象ファイル（想定） | `docs/api/api_specification.md`（`GET /statements/summary/monthly-trend`） |
| 完了条件 | 任意クエリ `card_issuer`（`card_issuers.code`。未指定時は全 issuer 合算）が、summary / by-holder と同じ意味で当該節に書いてある |
| コミット | 要 |
| 依存 | なし |
| 検証 | 該当節の目視。summary / by-holder の説明と矛盾しないこと |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `docs/api/api_specification.md`
- 検証: `GET /statements/summary/monthly-trend` のクエリに `card_issuer`（任意。`card_issuers.code`。未指定時は全 issuer 合算）を追記。`GET /statements/summary` の同項目と文言が一致し、by-holder の「任意の `card_issuers.code`」とも矛盾しない。レスポンス例は変更なし
- コミット案: 月次推移APIに発行会社の任意絞り込みを仕様へ追記

### Step 2: `monthly-trend` に issuer 絞り込みを実装

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | Step 1 のクエリを集計 API に足し、過去6ヶ月の系列を発行会社で切れるようにする |
| 対象ファイル（想定） | `backend/app/api/statements_v2.py`。レスポンス形は変えないため schema 変更は不要な想定 |
| 完了条件 | `card_issuer` 指定時はその code の明細だけが series に入る。未指定時は現状の合算のまま。未知 code は 0 件（他の集計 API と同じ。新規エラーにはしない） |
| コミット | 要 |
| 依存 | Step 1 |
| 検証 | ローカル DB で同月に楽天と Amex がある状態にし、片方の code と未指定を比べる。既存の summary / by-holder の絞り込みが変わっていないこと |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/api/statements_v2.py`
- 検証: 既存の明細が無かったため、2099年1月に楽天 150・Amex 70、2月に楽天 30 を同一セッションへ入れ、関数を直接呼んでからロールバックした（残件 0）。未指定 250、楽天 180、Amex 70、未知 code は series 0 件。1月の summary / by-holder は未指定 220・楽天 150・Amex 70・未知 0 で、同じ月の monthly-trend と一致。レスポンスの `from` / `to` / `series` は維持
- メモ: `card_issuer` が空文字のときは summary と同様に未指定扱い。指定時だけ `card_issuers` を結合する
- コミット案: 月次推移を発行会社で絞り込めるようにする

### Step 3: API クライアントを複数ファイル・issuer 契約に合わせる

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 画面が使う detect / 複数 upload / upload-status / issuer 一覧 / issuer 付き一覧・集計を型付きで呼べるようにする |
| 対象ファイル（想定） | `frontend/lib/features/statements/data/statements_api.dart`, `frontend/lib/features/statements/models/statement_item.dart`, `frontend/lib/features/upload/models/`（detect 結果・`results[]`・upload-status・issuer のモデル。配置は既存の feature 分割に合わせる） |
| 完了条件 | 次がクライアントにある。画面はまだ旧 upload を呼んでよく、この Step 単体で解析が通る。旧メソッドの削除は Step 4。Dio では `files` と `card_issuer_codes` を同じ順の繰り返しフィールドにする（`FormData.fromMap` のリスト一括ではなく、順序が崩れない追加方法） |
| コミット | 要 |
| 依存 | Step 1（月次推移のクエリ名が確定していること）。呼び出し先の API 実体は Step 2 と P2 |
| 検証 | `cd frontend && flutter analyze` |

クライアントに含めるもの:

- `POST /statements/detect-issuer`（単一 `file`）
- `POST /statements/upload`（`files` + 同順 `card_issuer_codes` → `results[]`）
- `GET /statements/upload-status`
- `GET /card-issuers`（呼び出し側が `is_active` を見る）
- `GET /statements` の任意 `card_issuer` と、明細の `card_issuer_code` / `card_issuer_name`
- summary / by-holder / monthly-trend の任意 `card_issuer`

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `frontend/lib/features/statements/data/statements_api.dart`, `frontend/lib/features/statements/models/statement_item.dart`, `frontend/lib/features/statements/models/card_issuer.dart`, `frontend/lib/features/upload/models/detect_issuer_result.dart`, `frontend/lib/features/upload/models/upload_file_payload.dart`, `frontend/lib/features/upload/models/statement_upload_batch_result.dart`, `frontend/lib/features/upload/models/upload_status.dart`
- 検証: `cd frontend && flutter analyze` → No issues found
- メモ: 旧 `uploadStatement`（単一 `file`）は Step 4 まで残している。`uploadStatements` は `files` と `card_issuer_codes` を同じ順の繰り返しフィールドで送る。発行会社マスタは一覧・集計でも使うため `statements/models` に置いた
- コミット案: 複数CSVと発行会社を扱えるAPIクライアントを追加

### Step 4: SCR-005 複数 CSV・判定確認・PDF 削除

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 取込を、複数 CSV の自動判定を確認してから実行する流れに戻す |
| 対象ファイル（想定） | `frontend/lib/features/upload/presentation/upload_page.dart`, 取込状況バッジの共有ウィジェット（`frontend/lib/features/statements/presentation/` 配下を想定）, `statements_api.dart` の旧 `uploadStatement` / `hasStatementsInMonth` |
| 完了条件 | CSV 複数選択のみ（PDF のラベル・許可拡張子がない）。各ファイルに判定結果と手動修正がある。未確定または code 重複では実行できない。既存 issuer があるときだけ置換確認が出る。成功後に issuer ごとの件数・未分類件数・エラー件数が出る。対象年月の取込状況が見える。年月変更で状況を取り直す。旧単一 `file` 送信が残っていない |
| コミット | 要 |
| 依存 | Step 3 |
| 検証 | `flutter analyze`。起動中のアプリで、CSV を2件選んで判定表示まで進むこと（本取込の縦通しは Step 7） |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `frontend/lib/features/upload/presentation/upload_page.dart`, `frontend/lib/features/statements/presentation/upload_status_badge.dart`, `frontend/lib/features/statements/data/statements_api.dart`, `frontend/lib/features/upload/models/upload_result.dart`（削除）
- 検証: `cd frontend && flutter analyze` → No issues found。開発サーバは起動していなかったため、CSV 2件の判定表示はブラウザでは未確認。PDF のラベルと許可拡張子、単一 `file` の `uploadStatement` / `hasStatementsInMonth` はコード上から除いた
- メモ: 選択直後にファイルごと detect。未確定と code 重複は実行ボタンを無効。置換確認は `upload-status.uploaded` との交差があるときだけ。年月変更で取込状況を取り直す
- コミット案: アップロードを複数CSVの判定確認に切り替える

### Step 5: SCR-002 のバッジ・フィルタ・発行会社表示と SCR-003 の表示

| 項目 | 内容 |
|------|------|
| 状態 | pending |
| 目的 | 明細一覧で、どのカードが未取込かと、行がどの発行会社かを分かるようにする |
| 対象ファイル（想定） | `frontend/lib/features/statements/presentation/statements_list_page.dart`, `frontend/lib/features/statements/presentation/statement_classification_page.dart`, Step 4 のバッジウィジェット |
| 完了条件 | 年月の近くに upload-status のバッジがある。絞り込みシートで発行会社を選べ、`card_issuer` クエリで再検索する。行の副題に `card_issuer_name` がある。空表示が決定済み方針の2文言になる。仕分け画面に発行会社名がある。ルール追加の UI は足さない |
| コミット | 要 |
| 依存 | Step 3, Step 4 |
| 検証 | `flutter analyze`。一覧でバッジと発行会社名、絞り込みの再検索が見えること |

**作業結果:**

### Step 6: SCR-004 のバッジと発行会社フィルタ

| 項目 | 内容 |
|------|------|
| 状態 | pending |
| 目的 | 集計を、未取込が分かり、発行会社ごとに見られるようにする |
| 対象ファイル（想定） | `frontend/lib/features/analytics/presentation/analytics_page.dart` |
| 完了条件 | 一覧と同じバッジがある。簡易ドロップダウンの未指定は合算、指定時はカテゴリ別・名義人別・月次推移のすべてに同じ `card_issuer` を渡す。`uploaded` が空の月は集計カードとタブを出さず、未アップロード文言だけになる。検索条件シートは増やさない |
| コミット | 要 |
| 依存 | Step 2, Step 3, Step 4 |
| 検証 | `flutter analyze`。発行会社を切り替えて当月合計と月次推移が変わること |

**作業結果:**

### Step 7: P3 完了検証とロードマップの完了条件

| 項目 | 内容 |
|------|------|
| 状態 | pending |
| 目的 | ロードマップ P3 の完了条件を画面で確認し、仕様との差分を残さない |
| 対象ファイル（想定） | 差分があれば `docs/screens/screen_specification.md` または `docs/api/api_specification.md` の文言のみ。`docs/plans/ROADMAP-20261122-resume.md` の P3 完了条件チェック。成果の本体はこの Step の作業結果 |
| 完了条件 | 同じ月に楽天 CSV と Amex CSV を UI から取り込み、一覧に両方出る。未取込の issuer がバッジの欠落と `upload-status` で一致する。SCR-002 / SCR-004 / SCR-005 と実装が矛盾しない（矛盾したらこの Step で docs を直す） |
| コミット | 要（docs 差分またはロードマップ更新がある場合）／不要（記録のみの場合） |
| 依存 | Step 4, Step 5, Step 6 |
| 検証 | ブラウザで次を行う。結果を作業結果に書く。`sample/` はローカル参照のみで Git に追加しない |

検証手順:

1. 対象月を選び、楽天 CSV と Amex CSV を同時に選ぶ。表示名での判定を確認してアップロードする
2. 明細一覧に両方の発行会社が出ること。バッジが両方取込済みであること
3. 片方の issuer だけ再アップロードし、置換確認のあと、もう片方の件数が残ること
4. 一覧フィルタで片方に絞れ、0 件時の文言が切り替わること
5. 集計で未指定（合算）と片方指定を切り替え、当月合計と月次推移が変わること
6. どちらか一方だけ取込済みの月で、バッジの未取込と一覧の通常表示が同時に見えること

**作業結果:**

## 実行ルール（人間向け）

- 実行は「計画ファイルパス + Step 番号（複数可）」で指示する
- 状態が `ready` または `in_progress` のときだけ実行スキルを使う
- コミットは人間が行う（実行スキルはメッセージ案のみ提示・**日本語**）
- 次工程: P4（LINE 通知）は別計画書で切る
