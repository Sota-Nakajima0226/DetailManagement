/**
 * 明細メールの検索と POST の形だけを確認する雛形。
 *
 * 本番の statement_mail.js とは別の Apps Script プロジェクトに貼る。
 * LINE は送らない。REMIND_CRON_SECRET は使わない。
 * ラベルは detail-management/mail-test で、本番の detail-management/notified は付けない。
 * 手順は docs/notifications/line_setup.md の「デプロイ前の受信テスト」。
 */

var MAIL_TEST_LABEL = 'detail-management/mail-test';
var MAIL_TEST_DUMMY_TOKEN = 'mail-test-dummy';

function checkStatementMailsTest() {
  var props = PropertiesService.getScriptProperties();
  var endpoint = (props.getProperty('TEST_NOTIFY_URL') || '').trim();
  var from = (props.getProperty('TEST_STATEMENT_FROM') || '').trim();
  var subject = (props.getProperty('TEST_STATEMENT_SUBJECT') || '').trim();
  var code = (props.getProperty('TEST_CARD_ISSUER_CODE') || 'rakuten').trim();
  if (!endpoint || !from || !subject) {
    console.log('mail test skipped: TEST_NOTIFY_URL, TEST_STATEMENT_FROM, and TEST_STATEMENT_SUBJECT are required');
    return;
  }

  var label = getOrCreateMailTestLabel_();
  var yearMonth = mailTestYearMonth_();
  var query = [
    'from:' + from,
    'subject:"' + subject + '"',
    '-label:"' + MAIL_TEST_LABEL + '"',
  ].join(' ');
  var threads = GmailApp.search(query, 0, 20);
  console.log('mail test matched threads=' + threads.length);
  threads.forEach(function (thread) {
    var matched = thread.getMessages().filter(function (message) {
      return mailTestMessageMatches_(message, from, subject);
    });
    if (matched.length === 0) {
      return;
    }
    var allAccepted = matched.every(function (message) {
      return postMailTest_(endpoint, code, message, yearMonth) === 200;
    });
    if (allAccepted) {
      thread.addLabel(label);
    }
  });
}

function installMailTestTrigger() {
  var handler = 'checkStatementMailsTest';
  var exists = ScriptApp.getProjectTriggers().some(function (trigger) {
    return trigger.getHandlerFunction() === handler;
  });
  if (exists) {
    return;
  }
  ScriptApp.newTrigger(handler).timeBased().everyMinutes(15).create();
}

function mailTestMessageMatches_(message, from, subject) {
  var messageFrom = message.getFrom() || '';
  var messageSubject = message.getSubject() || '';
  return messageFrom.indexOf(from) !== -1 && messageSubject.indexOf(subject) !== -1;
}

function postMailTest_(endpoint, code, message, yearMonth) {
  var messageId = message.getId();
  var payload = {
    card_issuer_code: code,
    source_message_id: messageId,
    mail_url: 'https://mail.google.com/mail/u/0/#inbox/' + messageId,
    year: yearMonth.year,
    month: yearMonth.month,
  };
  try {
    var response = UrlFetchApp.fetch(endpoint, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + MAIL_TEST_DUMMY_TOKEN,
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      timeoutSeconds: 90,
    });
    var status = response.getResponseCode();
    console.log('mail test issuer=' + code + ' status=' + status);
    return status;
  } catch (error) {
    console.log('mail test request failed issuer=' + code);
    return 0;
  }
}

function mailTestYearMonth_() {
  var formatted = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-M');
  var parts = formatted.split('-');
  return {
    year: Number(parts[0]),
    month: Number(parts[1]),
  };
}

function getOrCreateMailTestLabel_() {
  return GmailApp.getUserLabelByName(MAIL_TEST_LABEL) || GmailApp.createLabel(MAIL_TEST_LABEL);
}
