# LINE通知仕様

## 目次

1. [文書情報](#1-文書情報)
2. [目的と方針](#2-目的と方針)
3. [通知の種類](#3-通知の種類)
4. [共通仕様](#4-共通仕様)
5. [アップロード完了通知](#5-アップロード完了通知)
6. [明細メール着信通知](#6-明細メール着信通知)
7. [API](#7-api)
8. [Google Apps Script](#8-google-apps-script)
9. [データ](#9-データ)
10. [環境変数](#10-環境変数)
11. [今回やらないこと](#11-今回やらないこと)
12. [未決](#12-未決)

HTTP の契約は `docs/api/api_specification.md` §6 と一致させる。

## 1. 文書情報

| 項目 | 内容 |
|------|------|
| 文書名 | LINE通知仕様 |
| 対象 | アップロード完了通知、明細案内メールをきっかけにした取込依頼 |
| 状態 | 確定（2026-11-23） |
| 実装工程 | ロードマップ P4 |

## 2. 目的と方針

カード会社から明細案内メールが届いたことを LINE で知らせ、次の2手順が文面だけで分かるようにする。メールを開いて明細 CSV をダウンロードし、アプリのアップロード画面でその CSV を取り込む。取得とアップロード自体は手作業のままである。

- 配信は LINE Messaging API。宛先は夫婦＋ボットのグループ1つ（個別トークは使わない）。
- きっかけは毎月の固定日ではない。Gmail に明細案内が届いたとき、Google Apps Script が API を1回呼ぶ。
- アプリは受信箱を見にいかない。メールのパスワードも持たない。
- 明細メール着信の LINE には、次の2つの URL だけを載せる。受信メール（Gmail）と、このアプリの明細アップロード画面。メール本文からカード会社サイトの URL は抜かない。
- 金額・口座・会員番号・メール本文は LINE に出さない。リンクを開いて本文を見られるのは、その Gmail にログインしている人だけである。
- 対象月のそのカードが既に取り込まれていれば、LINE は送らない。

`card_issuers.remind_day_of_month`（楽天 23・Amex 4）は P1 で入っている列として残す。通知の条件には使わない。

## 3. 通知の種類

| 種類 | きっかけ | 文面の例 |
|------|----------|----------|
| アップロード完了 | 明細 CSV の取込が成功したとき | `3月の明細がアップロードされました（楽天）。確認してください。` |
| 明細メール着信 | 対象の明細案内メールを Apps Script が受け取ったとき | 下記「文面」の2手順（Gmail とアップロード画面） |

どちらも同じグループへ送る。予算超過や未分類の残件は、この仕様の範囲外とする。

## 4. 共通仕様

- 公式アカウント（Messaging API）を使う。通数はコミュニケーションプラン（月200通）で足りる想定。
- チャネルアクセストークンとグループ ID が未設定のときは送らず、警告ログだけ残す。取込処理は失敗にしない。
- ログにメール本文、LINE のトークン、呼び出し用の秘密鍵を出さない。
- 複数 issuer を1リクエストで取り込んだときは、成功した issuer をまとめてアップロード完了を1通にする。失敗した issuer は文面に含めない。すべて失敗なら送らない。

## 5. アップロード完了通知

- 呼び出し元は `POST /statements/upload` の成功時。Apps Script は関与しない。
- ユーザー JWT の経路で動き、別の秘密鍵は要らない。
- 文面には対象年月と、成功した issuer の表示名を入れる。Gmail の URL は付けない。

## 6. 明細メール着信通知

### 流れ

1. Apps Script が、issuer ごとの差出人・件名に合う未処理メールを見つける。
2. メッセージ ID から Gmail の URL を組み立てる。
3. `POST /notify/statement-mail` を秘密鍵つきで呼ぶ。
4. API が条件を満たすときだけ LINE を送る。
5. API が 200 を返したら、Apps Script はそのメールに処理済みラベルを付ける。

### 送る条件

次をすべて満たすときだけ LINE を送る。

- `card_issuer_code` が有効な issuer で、`include_in_reminder = true`
- 同じ `source_message_id` をまだ受け取っていない
- 対象年月のその issuer の `statements` が無い
- `mail_url` が、下記の `https://mail.google.com/mail/u/0/#inbox/{メッセージID}` である。メッセージ ID にパス区切り・空白・クエリを含まない
- `APP_UPLOAD_URL` が `https://` で設定されている
- LINE のトークンとグループ ID が設定されている

対象年月は、リクエストの `year` / `month` を使う。省略時は API が Asia/Tokyo の今日の年月にする。API はメール本文を解釈しない。請求メールの「お支払月」と CSV の利用月がずれる場合は、Apps Script が渡す年月で合わせる。

### 文面

手順が先、URL が直後に来る形で送る。表示名と年月は依頼の内容に合わせる。

```text
楽天の明細メールが届きました（2026年10月分）。

1. メールを開き、明細のCSVをダウンロードしてください。
https://mail.google.com/mail/u/0/#inbox/{メッセージID}

2. ダウンロードしたCSVを、次の画面からアップロードしてください。
https://example.example/upload?year=2026&month=10
```

2の URL は環境変数 `APP_UPLOAD_URL` を基点にし、API が `year` と `month` をクエリで付ける。アップロード画面はそのクエリを初期の対象年月にする。未ログインならログイン後にこの画面を開く。

Gmail の URL 形式は次だけを許す。

```text
https://mail.google.com/mail/u/0/#inbox/{メッセージID}
```

`{メッセージID}` は Apps Script の `GmailMessage.getId()`。カード会社サイトの URL、計測用 URL、トークン付き URL は載せず、検証で弾く。

現行の Flutter Web はアップロード画面へのパスを持たない。P4 で、`APP_UPLOAD_URL` のパス（例: `/upload`）から SCR-005 が開くようにする。本番のホスト名は P6 の公開 URL が決まってから環境変数に入れる。

## 7. API

### POST `/notify/statement-mail`

- 認証: `Authorization: Bearer <REMIND_CRON_SECRET>`。ユーザー JWT とは別経路。
- 秘密鍵が違う、または未設定のときは 401。

リクエスト例:

```json
{
  "card_issuer_code": "rakuten",
  "source_message_id": "18c0b1ab2f3e4d56",
  "mail_url": "https://mail.google.com/mail/u/0/#inbox/18c0b1ab2f3e4d56",
  "year": 2026,
  "month": 10
}
```

| フィールド | 必須 | 説明 |
|------------|------|------|
| `card_issuer_code` | はい | `card_issuers.code` |
| `source_message_id` | はい | Gmail メッセージ ID。再送判定に使う |
| `mail_url` | はい | 上記形式の Gmail URL |
| `year` / `month` | いいえ | 省略時は Asia/Tokyo の今日 |
| `force` | いいえ | `true` のとき、取込済みでも送る（手動試験用）。同じ `source_message_id` の再送は送らない |

応答例:

```json
{
  "card_issuer_code": "rakuten",
  "year": 2026,
  "month": 10,
  "notified": true,
  "skip_reason": null
}
```

| 結果 | HTTP | `notified` | `skip_reason` |
|------|------|------------|----------------|
| LINE を送った | 200 | `true` | `null` |
| その年月は取込済み | 200 | `false` | `already_uploaded` |
| 同じメッセージ ID を処理済み | 200 | `false` | `duplicate_message` |
| リマインド対象外の issuer | 200 | `false` | `issuer_excluded` |
| LINE 未設定 | 200 | `false` | `line_not_configured` |
| アップロード画面の URL が未設定・不正 | 200 | `false` | `upload_url_not_configured` |
| 秘密鍵が不正 | 401 | — | — |
| issuer 不明、URL 不正、年月不正 | 400 | — | — |

200 は「受理したので再送しなくてよい」。400 / 401 / 5xx のとき Apps Script はラベルを付けず、次の実行でやり直す。

## 8. Google Apps Script

スクリプトはリポジトリの外（Gmail アカウント側）に置く。秘密鍵はスクリプトプロパティに置き、ソースに書かない。

- 時間駆動トリガーで周期実行する（目安: 15分ごと）。Gmail に「着信瞬間」のイベントは無いため、Google 側の定期実行で未処理メールを探す。Render 上の cron は置かない。
- 無料枠の Render はスリープする。`UrlFetchApp` の待ち時間は、起動を見込んで 60 秒以上にする。
- issuer ごとに検索条件（差出人・件名）を持つ。
  - 楽天: 差出人 `info@mail.rakuten-card.co.jp`、件名に `【楽天カード】カードご請求金額のご案内` を含む
  - Amex: 差出人 `AmericanExpress@welcome.americanexpress.com`、件名に `ご請求金額確定のご案内` を含む
- 処理済みラベル（例: `detail-management/notified`）が付いたメールは検索から外す。
- 認証ヘッダは `Authorization: Bearer <REMIND_CRON_SECRET>`。Supabase のアクセストークンは使わない（短時間で期限切れになるため）。

## 9. データ

P4 のマイグレーションで、受信した明細メールの処理結果を残す。本文は保存しない。

| カラム | 型 | 説明 |
|--------|----|------|
| id | SERIAL PK | |
| card_issuer_id | INT FK | `card_issuers.id` |
| source_message_id | TEXT UNIQUE | Gmail メッセージ ID |
| year | INT | 判定に使った年 |
| month | INT | 判定に使った月 |
| mail_url | TEXT | 送った、または送ろうとした Gmail URL |
| notified | BOOLEAN | LINE を送ったか |
| skip_reason | TEXT | 送らなかった理由。送ったときは NULL |
| created_at | TIMESTAMPTZ | 受付時刻 |

`card_issuers.include_in_reminder` は、この通知と画面の未取込表示の対象スイッチとして残す。`remind_day_of_month` は残すが、この仕様では読まない。

## 10. 環境変数

| 名前 | 置く場所 | 用途 |
|------|----------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Render | Messaging API のチャネルアクセストークン |
| `LINE_GROUP_ID` | Render | 送信先グループ ID |
| `APP_UPLOAD_URL` | Render | 明細アップロード画面の基点 URL（`https://.../upload`）。LINE 文面の手順2に使う |
| `REMIND_CRON_SECRET` | Render と Apps Script のスクリプトプロパティ | `/notify/statement-mail` の秘密鍵 |

いずれも Git にコミットしない。

## 11. 今回やらないこと

- cron-job.org や GitHub Actions から毎日 API を叩くこと
- アプリからの IMAP による受信箱の巡回
- メール本文からの URL 抽出、金額の取得
- 固定日リマインド、未取込が残ったときの再通知
- `.ics` の配布
- 未分類残件・予算超過の LINE

## 12. 未決

- 公式アカウント作成、グループへのボット招待、グループ ID とチャネルアクセストークンの取得。P4 の実装中に人間が行う。コードは未設定でも動き、実送信の確認は揃ってからでよい。
