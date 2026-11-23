# LINE通知の設定と到達確認

明細案内メールをきっかけにグループへ送る通知の、設定手順です。振る舞いの正本は [line_notification.md](line_notification.md) です。この文書にはトークンや秘密鍵の値を書きません。

## 全体の流れ

1. LINE の公式アカウントを作り、チャネルアクセストークンとグループ ID を控える。
2. API に4つの環境変数を入れる。
3. 明細メールを受信する Gmail に Apps Script を置く。
4. 自分宛のテストメールで、グループに1通届くことを確認する。
5. テスト用のスクリプトプロパティを消す。

Apps Script は Google のサーバから API を呼びます。`http://127.0.0.1` には届きません。到達確認のときは、インターネットから呼べる API の URL を `NOTIFY_API_BASE_URL` にします。

## 1. 公式アカウントとトークン

1. [LINE Developers](https://developers.line.biz/) でプロバイダーと Messaging API チャネルを作る。
2. チャネルの Messaging API 設定で、グループトーク・複数人トークへの参加を許可する。
3. 同じ画面でチャネルアクセストークン（長期）を発行する。この値は API の `LINE_CHANNEL_ACCESS_TOKEN` にだけ入れる。チャット、ソース、この文書には貼らない。
4. 通数はコミュニケーションプラン（月200通）を想定しています。

## 2. グループ ID

このアプリは Webhook を受け取らないので、参加イベントを一度だけ外で見て、ID を控えます。

1. 届いた HTTP リクエストの中身を表示できる一時的な URL を用意する。例として [webhook.site](https://webhook.site) を開き、表示された URL をコピーする。この URL にはトークンを置かない。
2. LINE Developers の Messaging API 設定で、Webhook URL にその URL を入れ、Webhook の利用をオンにする。
3. 夫婦とボットだけのグループを作り、公式アカウントを招待する。
4. 表示された JSON の `events` の中にある `source.groupId` を控える。`C` で始まる文字列です。この値が `LINE_GROUP_ID` です。
5. Webhook URL を消し、Webhook の利用をオフに戻す。

## 3. API の環境変数

公開している API の環境に入れます。ローカルの API で同じ名前を使うときは `backend/.env` です。値の例は `backend/.env.example` に名前だけあります。

| 名前 | 用途 |
|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | 手順1で発行した長期トークン |
| `LINE_GROUP_ID` | 手順2の `source.groupId` |
| `APP_UPLOAD_URL` | アップロード画面の基点。クエリも `#` も無い `https://` だけ有効。文面ではこのうしろに `?year=&month=` が付く |
| `REMIND_CRON_SECRET` | `POST /notify/statement-mail` の秘密鍵。ユーザーのログイン JWT とは別の、自分で決めた文字列 |

`APP_UPLOAD_URL` が空、`http://`、またはクエリ付きだと、明細メールの LINE は送られません。画面の公開 URL がまだ無い到達確認では、クエリ無しの `https://` であれば仮の基点でも送られます。あとで本番のアップロード画面の URL に差し替えます。

`.env` はプロセス起動時に読まれます。保存したあとは API を再起動します。

## 4. Apps Script

1. 明細メールを受信する Gmail で [Apps Script](https://script.google.com/) を新規作成する。
2. `scripts/apps_script/statement_mail.js` の中身を貼る。秘密は入っていません。
3. プロジェクトの設定で、スクリプトプロパティを入れる。ソースには書かない。

| 名前 | 値 |
|------|----|
| `REMIND_CRON_SECRET` | API に入れた秘密鍵と同じ文字列 |
| `NOTIFY_API_BASE_URL` | API の基点。パスは付けない。形の例は `https://api.example.com` |

4. 関数 `checkStatementMails` を1回実行し、Gmail と外部リクエストの権限を許可する。
5. 関数 `installQuarterHourTrigger` を1回実行する。`checkStatementMails` が15分ごとに動きます。エディタのトリガー画面で、時間主導型の15分おきを同じ関数に付けても同じです。

処理済みラベルは `detail-management/notified` です。API が 200 を返したスレッドだけに付きます。400、401、5xx のときは付かないので、次の実行でやり直します。待ち時間は 90 秒です。

本番の検索条件はソースに入っています。

| カード | 差出人 | 件名に含む文字列 |
|--------|--------|------------------|
| 楽天 | `info@mail.rakuten-card.co.jp` | `【楽天カード】カードご請求金額のご案内` |
| Amex | `AmericanExpress@welcome.americanexpress.com` | `ご請求金額確定のご案内` |

## 5. 自分宛メールで到達確認する

カード会社のアドレスからは送れません。到達確認のあいだだけ、自分のアドレスと件名をスクリプトプロパティに足します。本番の2件はそのまま残ります。

先に手順3の4つを入れて API を再起動してから、テストメールを送ります。トークンが無い状態で先にスクリプトを動かすと、そのメールは「LINE 未設定」として受理され、同じメールでは二度と送られません。

スクリプトプロパティ:

| 名前 | 例 | 説明 |
|------|----|------|
| `TEST_STATEMENT_FROM` | 自分の Gmail アドレス | 差出人にこの文字列が含まれるメールを探す |
| `TEST_STATEMENT_SUBJECT` | `明細通知テスト` | 件名にこの文字列が含まれるものを探す。引用符や改行は入れない |
| `TEST_CARD_ISSUER_CODE` | `rakuten` | `rakuten` か `amex`。文面の表示名はこのカードになる |
| `TEST_YEAR` | `2026` | 任意。入れるときは `TEST_MONTH` も入れる |
| `TEST_MONTH` | `1` | 任意。1 から 12。未取込の年月にする |

`TEST_YEAR` と `TEST_MONTH` を空にすると、Asia/Tokyo の今日の年月で判定します。その月が取込済みだと LINE は届きません。アップロード画面で、選んだカードが未取込の年月を指定します。

手順:

1. 上のプロパティを保存し、Apps Script に最新の `statement_mail.js` が貼られていることを確認する。
2. その Gmail から自分宛に、件名へ `TEST_STATEMENT_SUBJECT` の文字列を入れたメールを1通送る。本文は空でよい。API は本文を読みません。
3. エディタで `checkStatementMails` を実行する。15分待たなくてよい。
4. 実行ログに `notified=true` と `skip_reason=` が出ていれば、グループに1通届いています。文面は取込手順で、金額やメール本文は入りません。
5. 確認が終わったら `TEST_STATEMENT_FROM`、`TEST_STATEMENT_SUBJECT`、`TEST_CARD_ISSUER_CODE`、`TEST_YEAR`、`TEST_MONTH` を消す。残すと、同じ差出人・件名のメールが来るたびに通知の対象になります。

同じメールをもう一度送っても届きません。Gmail のメッセージ ID は一度受理すると再送しません。やり直すときは新しいメールを送ります。ラベルを外すだけでは足りません。

## 6. 届かないとき

実行ログの `status`、`notified`、`skip_reason` を見ます。ログにトークンや秘密鍵は出ません。

| ログ | 意味 | 次にすること |
|------|------|----------------|
| `script properties are missing` | 秘密鍵か API の基点が無い | `REMIND_CRON_SECRET` と `NOTIFY_API_BASE_URL` を入れる |
| `test search skipped` | テスト用プロパティが足りない | 差出人、件名、カードコードを3つ入れる。年月は両方入れるか、両方空にする |
| `status=401` | 秘密鍵が API と違う | 両側の `REMIND_CRON_SECRET` を同じにして、API を再起動する |
| `skip_reason=line_not_configured` | トークンかグループ ID が無い | 2つを入れて API を再起動し、新しいメールでやり直す |
| `skip_reason=upload_url_not_configured` | アップロード URL が空、`http://`、またはクエリ付き | クエリ無しの `https://` にして API を再起動し、新しいメールでやり直す |
| `skip_reason=already_uploaded` | そのカードのその年月は取込済み | 未取込の年月を `TEST_YEAR` と `TEST_MONTH` に入れ、新しいメールでやり直す |
| `skip_reason=duplicate_message` | そのメールは受理済み | 新しいメールを送る |
| `skip_reason=issuer_excluded` | そのカードはリマインド対象外 | `include_in_reminder` がオンのカードコードにする |
| `status=400` | カードコードが無い、無効、または URL や年月が不正 | `TEST_CARD_ISSUER_CODE` を `rakuten` か `amex` にする |
| `status=0` または 5xx | API に届いていない、または送信に失敗した | `NOTIFY_API_BASE_URL` が公開 URL か、待ち時間のあとにもう一度実行する。ラベルは付いていない |

200 でラベルが付いたあとに環境変数を直しても、同じメールは `duplicate_message` になります。修正後は新しいメールを使います。
