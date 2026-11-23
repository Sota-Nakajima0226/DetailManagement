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

Messaging API のチャネルは、LINE Developers コンソールから直接は作れません。公式アカウントを作り、管理画面で Messaging API を有効にするとチャネルができます。操作はパソコンのブラウザで行います。スマホの公式アカウントアプリには、この設定がありません。

### 1-1. 公式アカウントを作る

1. [ビジネスIDの登録](https://account.line.biz/signup) を開く。LINE アカウントかメールアドレスで登録する。
2. 登録が終わると [公式アカウントの作成フォーム](https://entry.line.biz/form/entry/unverified) が出る。必須項目を入れる。アカウント名は、グループに表示される名前になる。業種は個人の家計に近いものを選ぶ。
3. 作成後、[LINE Official Account Manager](https://manager.line.biz/) に同じアカウントでログインし、作ったアカウントが一覧にあることを確認する。
4. 料金プランがコミュニケーションプラン（月額0円、月200通）なら、そのままでよい。上位プランへ変えない。

### 1-2. Messaging API を有効にする

管理画面の操作には「管理者」権限が必要です。プロバイダーは、チャネルを束ねる提供者の名前です。一度選ぶと変更できず、Messaging API の連携も解除できません。この家計アプリ専用に、新しいプロバイダーを1つ作ります。

1. 管理画面で作ったアカウントを開く。
2. 「設定」を押し、「Messaging API」を選ぶ。
3. 「Messaging APIを利用する」を押す。
4. LINE Developers を初めて使うアカウントでは、開発者情報の登録が出る。名前とメールアドレスを入れて進む。
5. プロバイダーの選択で、新しく作る。名前は家計アプリ用と分かるものにする。
6. 利用規約を確認して「同意する」を押し、確認画面で「OK」を押す。これで Messaging API が有効になり、チャネルができる。

### 1-3. グループへの参加を許可し、長期トークンを発行する

1. 管理画面と同じアカウントで [LINE Developers コンソール](https://developers.line.biz/console/) にログインする。
2. 手順 1-2 で作ったプロバイダーを押し、いま有効にしたチャネルを開く。
3. 「Messaging API設定」タブを開く。
4. 「グループトーク・複数人トークへの参加を許可する」をオンにする。初期値はオフです。オフのままだと、グループへ公式アカウントを招待できません。
5. 同じタブの「チャネルアクセストークン（長期）」で「発行」を押す。表示された文字列がトークンです。チャネルごとに1つだけで、有効期限はありません。再発行すると、今のトークンは使えなくなります。
6. トークンは API の `LINE_CHANNEL_ACCESS_TOKEN` にだけ入れる。チャット、ソース、この文書には貼らない。入れる場所は、次の「3. API の環境変数」です。グループ ID が揃うまでは、ファイルへ書かずに控えておいてもよい。

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

## デプロイ前の受信テスト

アプリを公開する前に、メールの検索と POST の形だけを確認します。LINE は届きません。本番の `statement_mail.js` とは別の Apps Script プロジェクトで行います。

雛形は `scripts/apps_script/statement_mail_test.js` です。認証ヘッダは `Bearer mail-test-dummy` 固定で、`REMIND_CRON_SECRET` は使いません。付くラベルは `detail-management/mail-test` です。本番の `detail-management/notified` は付きません。

1. 明細メールを受信する Gmail で [Apps Script](https://script.google.com/) の新しいプロジェクトを作る。本番用のプロジェクトには貼らない。
2. `statement_mail_test.js` の中身を貼って保存する。
3. [webhook.site](https://webhook.site) を開く。画面に出ている `https://webhook.site/` に続く固有の URL をコピーする。`#!/` の付いた画面用の URL は使わない。
4. プロジェクトの設定で、スクリプトプロパティを入れる。

| プロパティ | 値 |
|------------|----|
| `TEST_NOTIFY_URL` | 手順3でコピーした URL |
| `TEST_STATEMENT_FROM` | 自分の Gmail アドレス |
| `TEST_STATEMENT_SUBJECT` | `明細通知テスト`。引用符や改行は入れない |
| `TEST_CARD_ISSUER_CODE` | `rakuten` か `amex`。空なら `rakuten` |

5. その Gmail から自分宛に、件名へ `明細通知テスト` を入れたメールを1通送る。本文は空でよい。
6. 関数 `checkStatementMailsTest` を実行し、Gmail と外部リクエストの権限を許可する。
7. 実行ログが `matched threads=1` と `status=200` なら、検索と POST は成功です。webhook.site に届いた JSON に、カードコード、メッセージ ID、`https://mail.google.com/mail/u/0/#inbox/` で始まる URL、年月があることを確認する。`Authorization` が `Bearer mail-test-dummy` であることも確認する。
8. 同じ関数をもう一度実行する。ログの `matched threads=0` になり、webhook.site に2通目は届かない。メールに `detail-management/mail-test` が付いていれば、未処理だけを探す判定も確認できたことになります。
9. 15分トリガーも見るときは、関数 `installMailTestTrigger` を1回実行する。左の時計「トリガー」に `checkStatementMailsTest` の15分おきが増える。確認が終わったら、そのトリガーは削除する。

やり直すときは、テストメールから `detail-management/mail-test` を外してから、もう一度実行します。本番の秘密鍵はこのプロジェクトに入れません。

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
