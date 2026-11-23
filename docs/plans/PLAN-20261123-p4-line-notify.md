# 計画書: P4 LINE通知（アップロード完了・明細メール）

| 項目 | 内容 |
|------|------|
| 計画ID | PLAN-20261123-p4-line-notify |
| 状態 | done |
| 対象仕様 | `docs/plans/ROADMAP-20261122-resume.md` P4 / `docs/notifications/line_notification.md` / `docs/api/api_specification.md` §6 / `docs/db/db_design.md`（`statement_mail_notifications`） / `docs/screens/screen_specification.md` SCR-005 の入口 |
| 作成日 | 2026-11-23 |
| 更新日 | 2026-11-23 |
| 前提・制約 | P3 完了済み。公式アカウント・グループ ID・トークンの取得は人間作業。未設定でも API は完成させ、取込は失敗させない。実 LINE 送信の確認は環境変数があるときだけ。`sample/` はコミット禁止。秘密は `.env` と Apps Script のスクリプトプロパティだけ。コミットメッセージは日本語。 |

## 背景・ゴール

明細案内メールをきっかけに、未取込のカードだけグループへ取込手順を送り、CSV 取込が成功したときも同じグループへ完了を送る。完了時点で、`/upload?year=&month=` からアップロード画面が開き、`statement-mail` とアップロード完了が仕様の条件どおり動くこと。

## 現状ギャップ

- `statement_mail_notifications` は DB 設計のみ。モデルとマイグレーションがない
- `POST /notify/statement-mail` も、アップロード成功時の LINE もない
- `REMIND_CRON_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_GROUP_ID` / `APP_UPLOAD_URL` が `.env.example` にない
- Flutter は `AuthGate` がログイン後に常にメイン画面を出す。`/upload` のパスとクエリを読んでいない
- API 仕様 §6 の `skip_reason` に `upload_url_not_configured` が無く、Gmail URL は前方一致だけになっている。通知仕様は形式を限定し、アップロード URL 未設定も 200 で返す
- 通知仕様の未決に Amex の差出人・件名が残っている。`sample/email/notification_email_info.md` には実メールの値が書いてある
- Apps Script の雛形と README の運用手順がない

## 決定済み方針（本計画内）

- 振る舞いの正本は `docs/notifications/line_notification.md`。API 仕様 §6 は Step 1 でそれに合わせる
- Gmail URL は `https://mail.google.com/mail/u/0/#inbox/{メッセージID}` だけを 200 対象にする。それ以外は 400。メッセージ ID はパス区切りを含まない
- `APP_UPLOAD_URL` はクエリ無しの `https://` で始まる基点だけ有効。未設定・`http://`・クエリ付きは 200 の `upload_url_not_configured`。文面の手順2は `{基点}?year={year}&month={month}`
- `year` と `month` は両方省略なら Asia/Tokyo の今日。片方だけ、または月が 1〜12 以外なら 400
- `is_active` でない、または code が無い issuer は 400。有効だが `include_in_reminder = false` は 200 の `issuer_excluded`
- 400 と 401 では受理記録を書かない。200 は送ったときもスキップのときも書く。同じ `source_message_id` は理由を問わず再送しない（`force=true` でも）
- LINE の push 先はグループ ID へのテキスト1通。トークン未設定、送信失敗、URL 不正でも `POST /statements/upload` の 201 は維持し、警告ログだけ残す。ログにトークン・秘密鍵・メール本文は出さない
- 複数ファイルの成功は1通にまとめる。文面は `3月の明細がアップロードされました（楽天、Amex）。確認してください。` の形で、括弧内は成功した順の `display_name`
- 明細メールの文面は通知仕様の2手順。表示名は `card_issuers.display_name`
- 検索条件は差出人と件名の両方。楽天は `info@mail.rakuten-card.co.jp` かつ件名に `【楽天カード】カードご請求金額のご案内`。Amex は `AmericanExpress@welcome.americanexpress.com` かつ件名に `ご請求金額確定のご案内`
- スクリプト本体の雛形は秘密を含まずリポジトリに置く。設置先の正は Gmail 側の Apps Script
- Web はパス URL にする。`/upload` は SCR-005。未ログインならログイン後に同じ URL のアップロード画面を開く。`/` は今のメイン画面のまま

## 未確定事項

なし

## ステップ一覧

### Step 1: 通知の HTTP 契約と Amex の検索条件を正本で揃える

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 実装前に、API 仕様と通知仕様の受理結果・URL 形式を一致させ、Amex の検索条件を未決から外す |
| 対象ファイル（想定） | `docs/api/api_specification.md` §6、`docs/notifications/line_notification.md` §8 と §12 |
| 完了条件 | `skip_reason` に `upload_url_not_configured` がある。Gmail URL の許す形が通知仕様の `#inbox/{メッセージID}` と一致する。Amex の差出人・件名が §8 にあり、§12 の当該未決が閉じている |
| コミット | 要 |
| 依存 | なし |
| 検証 | 両文書の該当節を目視し、200 / 400 の分けと検索条件が矛盾しないこと |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `docs/api/api_specification.md`, `docs/notifications/line_notification.md`
- 検証: §6 の `skip_reason` に `upload_url_not_configured` があり、Gmail URL は両文書とも `https://mail.google.com/mail/u/0/#inbox/{メッセージID}` だけを許し、それ以外は 400。通知仕様 §8 に楽天と Amex の差出人・件名があり、§12 から Amex の未決を外した。200 のスキップと 400 の不正 URL は両文書で一致
- コミット案: 明細メール通知のURL形式とAmex検索条件を仕様に揃える

### Step 2: 受理記録テーブルとモデル

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 明細メールの処理結果を、本文なしで残せるようにする |
| 対象ファイル（想定） | `backend/alembic/versions/` の新規リビジョン、`backend/app/models/__init__.py`。設計と差があれば `docs/db/db_design.md` のみ |
| 完了条件 | `statement_mail_notifications` が設計書の列と UNIQUE `source_message_id`、`card_issuers` への FK を持つ。マイグレーションが適用できる |
| コミット | 要 |
| 依存 | Step 1 |
| 検証 | `cd backend && .venv/bin/python -m alembic upgrade head`。既存テーブルを壊さないこと |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/models/__init__.py`, `backend/alembic/versions/b7c1e2a94d10_add_statement_mail_notifications.py`
- 検証: `alembic upgrade head` で `0a538038914e` から `b7c1e2a94d10` を適用。列は id / card_issuer_id / source_message_id / year / month / mail_url / notified / skip_reason / created_at（timestamptz）。`source_message_id` は UNIQUE、`card_issuer_id` は `card_issuers.id` への FK。既存の card_issuers 2件、statements 3件、statement_items 219件、csv_import_profiles 2件はそのまま
- コミット案: 明細メールの受理結果を本文なしで残すテーブルを追加

### Step 3: `POST /notify/statement-mail` と LINE 送信

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 未取込の明細案内だけ、Gmail とアップロード画面の URL を手順つきで送れるようにする |
| 対象ファイル（想定） | `backend/app/services/` の LINE 送信、`backend/app/api/` の通知ルータ、`backend/main.py`、`backend/app/core/config.py`、`backend/app/schemas/`、`backend/.env.example`、`backend/tests/` |
| 完了条件 | ユーザー JWT ではなく `REMIND_CRON_SECRET` で 401 を分ける。決定済みの 200 / 400 と受理記録になる。LINE 呼び出しはテストでモックし、実ネットワークへ送らない。トークン未設定は `line_not_configured` で、push API を呼ばない |
| コミット | 要 |
| 依存 | Step 2 |
| 検証 | `cd backend && .venv/bin/python -m unittest` の通知テスト。未取込で文面に2つの URL、取込済みと同一メッセージ ID では送信関数が呼ばれないこと |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/services/line_messaging.py`, `backend/app/services/statement_mail.py`, `backend/app/api/notifications.py`, `backend/main.py`, `backend/app/core/config.py`, `backend/app/schemas/__init__.py`, `backend/.env.example`, `backend/tests/test_statement_mail_notification.py`
- 検証: `cd backend && .venv/bin/python -m unittest tests.test_statement_mail_notification` は成功。未取込の文面に Gmail URL と `APP_UPLOAD_URL?year=&month=` がある。取込済みと同一メッセージ ID では送信関数を呼ばない。秘密鍵が無い・違うときは 401 で記録しない。トークン未設定は `line_not_configured` で push を呼ばない。LINE の urlopen はモックし、実ネットワークへは送っていない
- コミット案: 未取込の明細案内だけLINEへ手順つきで送る

### Step 4: アップロード完了の LINE

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | 取込に成功した発行会社だけを、1通でグループへ知らせる |
| 対象ファイル（想定） | `backend/app/api/statements_v2.py`、Step 3 の送信サービス、必要ならテスト |
| 完了条件 | `db.commit` 後に、成功 issuer の表示名をまとめた1通を送る。成功が0件、またはトークン未設定、または送信例外でもアップロード応答は 201 のまま。Gmail URL は付けない |
| コミット | 要 |
| 依存 | Step 3 |
| 検証 | 送信をモックしたテストで、複数成功は1通、全失敗は0通、送信例外でも 201 |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `backend/app/api/statements_v2.py`, `backend/app/services/line_messaging.py`, `backend/tests/test_upload_completed_line.py`, `docs/api/api_specification.md`
- 検証: `cd backend && .venv/bin/python -m unittest tests.test_upload_completed_line` は成功。楽天と Amex の成功は `3月の明細がアップロードされました（楽天、Amex）。確認してください。` の1通で、Gmail URL は無い。明細を保存できなかった issuer は文面に入らず、両方失敗なら0通。送信例外とトークン未設定でも応答は 201。送信はモックし、実ネットワークへは送っていない
- コミット案: 取込に成功したカードだけを1通のLINEで知らせる

### Step 5: `/upload` を開いて対象年月を初期値にする

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | LINE の手順2の URL から、指定年月のアップロード画面へ入れるようにする |
| 対象ファイル（想定） | `frontend/lib/main.dart`、`frontend/lib/core/presentation/auth_gate.dart`、必要なら小さなルート判定。`UploadPage` の初期年月は既存の引数を使う |
| 完了条件 | Web で `/upload?year=&month=` を開くと SCR-005 になり、年月の初期値がクエリと一致する。未ログイン時はログイン後にその画面になる。`/` は従来の明細・グラフ。クエリが無い、または年月が不正なら、今までどおり今日の年月 |
| コミット | 要 |
| 依存 | なし（API とは独立）。検証の縦通しは Step 7 |
| 検証 | `cd frontend && flutter analyze`。起動中のアプリで `/upload?year=2026&month=1` を開き、対象年・対象月が 2026 と 1 であること。未ログインからログインしても同じ画面に残ること |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `frontend/lib/main.dart`, `frontend/lib/core/presentation/auth_gate.dart`, `frontend/lib/core/navigation/app_location.dart`, `frontend/lib/core/navigation/url_strategy.dart`, `frontend/lib/core/navigation/url_strategy_stub.dart`, `frontend/lib/core/navigation/url_strategy_web.dart`, `frontend/pubspec.yaml`, `frontend/pubspec.lock`, `frontend/test/app_location_test.dart`, `docs/screens/screen_specification.md`
- 検証: `cd frontend && flutter analyze` は問題なし。`flutter test test/app_location_test.dart` で `/` はメイン画面、`/upload?year=2026&month=1` は 2026年1月、クエリ無し・片方だけ・月が 13 は今日の年月になることを確認。起動中の開発サーバは `/upload` に 200 でアプリを返す。ブラウザ自動操作ではローカルの Flutter 画面を描画できず、ログイン後の対象年月の目視は未実施。パス URL の切り替えはプロセス起動時なので、確認前にアプリの再起動が必要
- 実施日: 2026-11-23
- メモ: `/upload` をルートとして登録していなかったため、Flutter が初期画面を `/` に戻していた。`/upload?year=&month=` を初期ルートのまま残すように修正。`flutter analyze` とパス判定のテストは成功
- コミット案: アップロードURLで指定した年月の画面を開く

### Step 6: Apps Script の雛形と運用手順

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | Gmail 側へ同じ条件で設置でき、秘密をリポジトリに置かないようにする |
| 対象ファイル（想定） | 秘密を含まない雛形（例: `scripts/apps_script/statement_mail.js`）、`README.md` |
| 完了条件 | 雛形が差出人・件名で未処理メールを探し、`Authorization: Bearer` にスクリプトプロパティの秘密鍵を付け、待ち時間 60 秒以上で `POST /notify/statement-mail` する。200 のときだけ処理済みラベルを付ける。README に環境変数、ラベル、15分トリガー、楽天の検索条件、Amex の検索条件、公式アカウントとグループ ID の取得手順がある |
| コミット | 要 |
| 依存 | Step 1 |
| 検証 | 雛形と README を目視し、トークン・秘密鍵の実値が無いこと。Amex が「未設定」ではなく決定済みの差出人・件名であること |

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `scripts/apps_script/statement_mail.js`, `README.md`, `docs/notifications/line_notification.md`
- 検証: 雛形は差出人と件名で未処理メールを探し、スクリプトプロパティの秘密鍵を `Authorization: Bearer` に付け、待ち時間 90 秒で `POST /notify/statement-mail` する。200 のスレッドだけに `detail-management/notified` を付ける。トークンや秘密鍵の実値は無い。楽天は `info@mail.rakuten-card.co.jp` と `【楽天カード】カードご請求金額のご案内`、Amex は `AmericanExpress@welcome.americanexpress.com` と `ご請求金額確定のご案内`。README に環境変数、ラベル、15分トリガー、両社の検索条件、公式アカウントとグループ ID の取得手順がある
- コミット案: 明細メールを探すApps Scriptの雛形と手順を追加

### Step 7: P4 完了検証

| 項目 | 内容 |
|------|------|
| 状態 | done |
| 目的 | ロードマップ P4 の完了条件を確認し、仕様との差分を残さない |
| 対象ファイル（想定） | 差分があれば通知仕様・API 仕様の文言のみ。`docs/plans/ROADMAP-20261122-resume.md` の P4 完了条件。成果の本体はこの Step の作業結果 |
| 完了条件 | 未取込の `statement-mail` が手順つき URL の条件を満たす。トークン未設定では `line_not_configured` で、取込 API は成功したまま。取込済みと同一メッセージ ID では送らない。アップロード完了は成功 issuer だけ。`/upload?year=&month=` が SCR-005 の初期値になる。README に運用手順がある |
| コミット | 要（ロードマップまたは仕様の差分がある場合）／不要（記録のみの場合） |
| 依存 | Step 4, Step 5, Step 6 |
| 検証 | 下記を実行し、結果を作業結果に書く。実 LINE 送信は4つの環境変数が揃っているときだけ。揃っていなければ自動テストと画面の結果を書き、実送信は未実施と残す |

検証手順:

1. 通知の単体テストが成功する
2. トークン未設定で `statement-mail` が `line_not_configured`、続けて同じメッセージ ID が `duplicate_message` になる
3. 取込済みの年月は `already_uploaded` で、送信関数が呼ばれない
4. CSV のアップロードが、LINE 未設定でも 201 になる
5. ブラウザで `/upload?year=2026&month=1` を開き、ログイン前後とも対象年月が 2026年1月である
6. 環境変数が揃っていれば、試験用の1通がグループに届き、文面に金額やメール本文が無い

**作業結果:**
- 実施日: 2026-11-23
- 変更ファイル: `docs/plans/ROADMAP-20261122-resume.md`
- 検証: `tests.test_statement_mail_notification` と `tests.test_upload_completed_line` は 20 件成功。未取込の文面に Gmail URL と `APP_UPLOAD_URL?year=&month=` がある。トークン未設定は `line_not_configured` で push を呼ばず、同じメッセージ ID の再送は `duplicate_message`。取込済みは `already_uploaded` で送信しない。LINE 未設定の CSV アップロードは 201。ブラウザで `http://127.0.0.1:8080/upload?year=2026&month=1` を開くと、アドレスはそのままで「明細アップロード」の対象年 2026・対象月 1 になる。このブラウザはログイン済みだったため、ログイン画面そのものは表示されなかった。`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_GROUP_ID`、`APP_UPLOAD_URL`、`REMIND_CRON_SECRET` は未設定なので、実グループへの送信は未実施
- メモ: ロードマップ P4 の完了条件を、検証した文面・スキップと README の楽天・Amex の検索条件に合わせた。通知仕様と API 仕様に追加の差分は無かった
- コミット案: P4の通知完了条件を検証結果に合わせる

## 実行ルール（人間向け）

- 実行は「計画ファイルパス + Step 番号（複数可）」で指示する
- 状態が `ready` または `in_progress` のときだけ実行スキルを使う
- コミットは人間が行う（実行スキルはメッセージ案のみ提示・**日本語**）
- 公式アカウントとグループ ID が未取得でも Step 1〜6 は実行できる。実送信は Step 7 で環境変数がある場合だけ確認する
