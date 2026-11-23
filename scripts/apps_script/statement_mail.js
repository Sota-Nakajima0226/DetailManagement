/**
 * 明細案内メールを探し、POST /notify/statement-mail を呼ぶ雛形。
 *
 * このファイルは秘密を含まない。動かす正本は Gmail アカウント側の Apps Script。
 * スクリプトプロパティに REMIND_CRON_SECRET と NOTIFY_API_BASE_URL を置く。
 * 到達確認では TEST_STATEMENT_FROM / TEST_STATEMENT_SUBJECT /
 * TEST_CARD_ISSUER_CODE を足す。年月をずらすときは TEST_YEAR と TEST_MONTH も入れる。
 * 値はこのファイルへ書かない。手順は docs/notifications/line_setup.md。
 */

var STATEMENT_MAIL_LABEL = 'detail-management/notified';

var STATEMENT_MAIL_ISSUERS = [
  {
    code: 'rakuten',
    from: 'info@mail.rakuten-card.co.jp',
    subject: '【楽天カード】カードご請求金額のご案内',
  },
  {
    code: 'amex',
    from: 'AmericanExpress@welcome.americanexpress.com',
    subject: 'ご請求金額確定のご案内',
  },
];

function checkStatementMails() {
  var props = PropertiesService.getScriptProperties();
  var secret = props.getProperty('REMIND_CRON_SECRET');
  var baseUrl = props.getProperty('NOTIFY_API_BASE_URL');
  if (!secret || !baseUrl) {
    console.log('statement mail skipped: script properties are missing');
    return;
  }

  var label = getOrCreateLabel_(STATEMENT_MAIL_LABEL);
  var yearMonth = tokyoYearMonth_();
  issuersToCheck_(props).forEach(function (issuer) {
    notifyIssuer_(issuer, baseUrl, secret, label, yearMonthFor_(issuer, yearMonth));
  });
}

function issuersToCheck_(props) {
  var issuers = STATEMENT_MAIL_ISSUERS.slice();
  var testFrom = (props.getProperty('TEST_STATEMENT_FROM') || '').trim();
  var testSubject = (props.getProperty('TEST_STATEMENT_SUBJECT') || '').trim();
  var testCode = (props.getProperty('TEST_CARD_ISSUER_CODE') || '').trim();
  var testYear = (props.getProperty('TEST_YEAR') || '').trim();
  var testMonth = (props.getProperty('TEST_MONTH') || '').trim();
  if (!testFrom && !testSubject && !testCode && !testYear && !testMonth) {
    return issuers;
  }
  if (!testFrom || !testSubject || !testCode) {
    console.log('statement mail test search skipped: from, subject, and issuer code are required');
    return issuers;
  }
  var entry = {
    code: testCode,
    from: testFrom,
    subject: testSubject,
  };
  if (testYear || testMonth) {
    var year = Number(testYear);
    var month = Number(testMonth);
    if (!testYear || !testMonth || !isFinite(year) || !isFinite(month) || year < 1 || month < 1 || month > 12) {
      console.log('statement mail test search skipped: year and month must both be set');
      return issuers;
    }
    entry.year = year;
    entry.month = month;
  }
  issuers.push(entry);
  return issuers;
}

function yearMonthFor_(issuer, fallback) {
  if (issuer.year && issuer.month) {
    return { year: issuer.year, month: issuer.month };
  }
  return fallback;
}

function installQuarterHourTrigger() {
  var handler = 'checkStatementMails';
  var exists = ScriptApp.getProjectTriggers().some(function (trigger) {
    return trigger.getHandlerFunction() === handler;
  });
  if (exists) {
    return;
  }
  ScriptApp.newTrigger(handler).timeBased().everyMinutes(15).create();
}

function notifyIssuer_(issuer, baseUrl, secret, label, yearMonth) {
  var query = [
    'from:' + issuer.from,
    'subject:"' + issuer.subject + '"',
    '-label:"' + STATEMENT_MAIL_LABEL + '"',
  ].join(' ');
  var threads = GmailApp.search(query, 0, 20);
  threads.forEach(function (thread) {
    var matched = thread.getMessages().filter(function (message) {
      return messageMatches_(message, issuer);
    });
    if (matched.length === 0) {
      return;
    }
    var allAccepted = matched.every(function (message) {
      return postStatementMail_(baseUrl, secret, issuer, message, yearMonth) === 200;
    });
    if (allAccepted) {
      thread.addLabel(label);
    }
  });
}

function messageMatches_(message, issuer) {
  var from = message.getFrom() || '';
  var subject = message.getSubject() || '';
  return from.indexOf(issuer.from) !== -1 && subject.indexOf(issuer.subject) !== -1;
}

function postStatementMail_(baseUrl, secret, issuer, message, yearMonth) {
  var messageId = message.getId();
  var endpoint = baseUrl.replace(/\/+$/, '') + '/notify/statement-mail';
  var payload = {
    card_issuer_code: issuer.code,
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
        Authorization: 'Bearer ' + secret,
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      timeoutSeconds: 90,
    });
    var status = response.getResponseCode();
    var notified = '';
    var skipReason = '';
    try {
      var body = JSON.parse(response.getContentText() || '{}');
      notified = body.notified;
      skipReason = body.skip_reason || '';
    } catch (parseError) {
      skipReason = '';
    }
    console.log(
      'statement mail issuer=' + issuer.code +
      ' status=' + status +
      ' notified=' + notified +
      ' skip_reason=' + skipReason
    );
    return status;
  } catch (error) {
    console.log('statement mail request failed issuer=' + issuer.code);
    return 0;
  }
}

function tokyoYearMonth_() {
  var formatted = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-M');
  var parts = formatted.split('-');
  return {
    year: Number(parts[0]),
    month: Number(parts[1]),
  };
}

function getOrCreateLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}
