"""POST /notify/statement-mail の単体テスト。LINE はモックし、ネットワークへ送らない。"""
import unittest
from datetime import datetime
from unittest.mock import patch
from urllib.request import Request

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config
from app.core.database import get_db
from app.models import CardIssuer, Statement, StatementMailNotification
from app.services.line_messaging import LINE_PUSH_URL, LineNotConfiguredError, LineSendError
from app.services.line_messaging import push_text_message
from main import app


MAIL_URL = "https://mail.google.com/mail/u/0/#inbox/18c0b1ab2f3e4d56"
UPLOAD_BASE = "https://example.com/upload"


class _TokyoNow(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls(2026, 11, 23, 10, 0, tzinfo=tz)


class StatementMailNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        CardIssuer.__table__.create(engine)
        Statement.__table__.create(engine)
        StatementMailNotification.__table__.create(engine)
        cls.Session = sessionmaker(bind=engine)

    def setUp(self) -> None:
        self.db = self.Session()
        app.dependency_overrides[get_db] = self._override_db
        self.client = TestClient(app)
        self.config_patch = patch.multiple(
            config,
            REMIND_CRON_SECRET="cron-secret",
            APP_UPLOAD_URL=UPLOAD_BASE,
            LINE_CHANNEL_ACCESS_TOKEN="line-token",
            LINE_GROUP_ID="group-id",
        )
        self.config_patch.start()
        self.push_patch = patch("app.services.statement_mail.push_text_message")
        self.push = self.push_patch.start()
        self.db.query(StatementMailNotification).delete()
        self.db.query(Statement).delete()
        self.db.query(CardIssuer).delete()
        self.db.commit()

    def tearDown(self) -> None:
        self.push_patch.stop()
        self.config_patch.stop()
        app.dependency_overrides.clear()
        self.db.close()

    def _override_db(self):
        try:
            yield self.db
        finally:
            pass

    def _issuer(self, **overrides: object) -> CardIssuer:
        values: dict[str, object] = {
            "code": "rakuten",
            "display_name": "楽天",
            "is_active": True,
            "include_in_reminder": True,
            "remind_day_of_month": 23,
            "sort_order": 1,
        }
        values.update(overrides)
        issuer = CardIssuer(**values)
        self.db.add(issuer)
        self.db.commit()
        return issuer

    def _post(self, payload: dict[str, object], secret: str = "cron-secret"):
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        return self.client.post("/notify/statement-mail", json=payload, headers=headers)

    def _payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "card_issuer_code": "rakuten",
            "source_message_id": "18c0b1ab2f3e4d56",
            "mail_url": MAIL_URL,
            "year": 2026,
            "month": 10,
        }
        payload.update(overrides)
        return payload

    def _rows(self) -> list[StatementMailNotification]:
        return self.db.query(StatementMailNotification).all()

    def test_missing_or_wrong_secret_is_401_and_writes_nothing(self) -> None:
        self._issuer()
        missing = self.client.post("/notify/statement-mail", json=self._payload())
        wrong = self._post(self._payload(), secret="user-jwt-not-the-cron-secret")
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.headers.get("WWW-Authenticate"), "Bearer")
        self.push.assert_not_called()
        self.assertEqual(self._rows(), [])

    def test_unset_secret_is_401_even_when_bearer_matches_empty(self) -> None:
        self._issuer()
        with patch.object(config, "REMIND_CRON_SECRET", ""):
            response = self._post(self._payload(), secret="")
        self.assertEqual(response.status_code, 401)
        self.push.assert_not_called()
        self.assertEqual(self._rows(), [])

    def test_unimported_mail_sends_gmail_and_upload_urls(self) -> None:
        self._issuer()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "card_issuer_code": "rakuten",
                "year": 2026,
                "month": 10,
                "notified": True,
                "skip_reason": None,
            },
        )
        self.push.assert_called_once()
        text = self.push.call_args.args[0]
        self.assertIn("楽天の明細メールが届きました（2026年10月分）。", text)
        self.assertIn(MAIL_URL, text)
        self.assertIn(f"{UPLOAD_BASE}?year=2026&month=10", text)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].notified)
        self.assertIsNone(rows[0].skip_reason)

    def test_omitted_year_and_month_use_tokyo_today(self) -> None:
        self._issuer()
        payload = self._payload()
        del payload["year"]
        del payload["month"]
        with patch("app.services.statement_mail.datetime", _TokyoNow):
            response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["year"], 2026)
        self.assertEqual(response.json()["month"], 11)
        self.assertIn("?year=2026&month=11", self.push.call_args.args[0])

    def test_already_uploaded_does_not_send(self) -> None:
        issuer = self._issuer()
        self.db.add(Statement(year=2026, month=10, card_issuer_id=issuer.id))
        self.db.commit()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["skip_reason"], "already_uploaded")
        self.assertFalse(response.json()["notified"])
        self.push.assert_not_called()
        self.assertEqual(len(self._rows()), 1)

    def test_same_message_id_does_not_send_again_even_with_force(self) -> None:
        self._issuer()
        first = self._post(self._payload())
        second = self._post(self._payload(force=True))
        self.assertTrue(first.json()["notified"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["skip_reason"], "duplicate_message")
        self.assertEqual(self.push.call_count, 1)
        self.assertEqual(len(self._rows()), 1)

    def test_force_sends_when_the_month_is_already_uploaded(self) -> None:
        issuer = self._issuer()
        self.db.add(Statement(year=2026, month=10, card_issuer_id=issuer.id))
        self.db.commit()
        response = self._post(self._payload(force=True))
        self.assertTrue(response.json()["notified"])
        self.push.assert_called_once()

    def test_excluded_issuer_is_recorded_without_sending(self) -> None:
        self._issuer(include_in_reminder=False)
        response = self._post(self._payload())
        self.assertEqual(response.json()["skip_reason"], "issuer_excluded")
        self.push.assert_not_called()
        self.assertEqual(len(self._rows()), 1)

    def test_unknown_or_inactive_issuer_is_400_without_a_record(self) -> None:
        self._issuer(is_active=False)
        inactive = self._post(self._payload())
        unknown = self._post(self._payload(card_issuer_code="missing"))
        self.assertEqual(inactive.status_code, 400)
        self.assertEqual(unknown.status_code, 400)
        self.push.assert_not_called()
        self.assertEqual(self._rows(), [])

    def test_invalid_mail_url_or_partial_month_is_400_without_a_record(self) -> None:
        self._issuer()
        bad_url = self._post(self._payload(mail_url="https://mail.google.com/mail/u/0/#inbox/a/b"))
        only_year = self._post(self._payload(month=None))
        bad_month = self._post(self._payload(month=13))
        self.assertEqual(bad_url.status_code, 400)
        self.assertEqual(only_year.status_code, 400)
        self.assertEqual(bad_month.status_code, 400)
        self.push.assert_not_called()
        self.assertEqual(self._rows(), [])

    def test_invalid_upload_url_is_skipped_without_sending(self) -> None:
        self._issuer()
        with patch.object(config, "APP_UPLOAD_URL", "http://127.0.0.1:8080/upload"):
            response = self._post(self._payload())
        self.assertEqual(response.json()["skip_reason"], "upload_url_not_configured")
        self.push.assert_not_called()
        self.assertEqual(len(self._rows()), 1)

    def test_query_on_upload_url_is_skipped_without_sending(self) -> None:
        self._issuer()
        with patch.object(config, "APP_UPLOAD_URL", "https://example.com/upload?next=1"):
            response = self._post(self._payload(source_message_id="another-message"))
        self.assertEqual(response.json()["skip_reason"], "upload_url_not_configured")
        self.push.assert_not_called()

    def test_missing_line_token_does_not_call_push(self) -> None:
        self._issuer()
        with patch.object(config, "LINE_CHANNEL_ACCESS_TOKEN", ""):
            response = self._post(self._payload())
        self.assertEqual(response.json()["skip_reason"], "line_not_configured")
        self.push.assert_not_called()
        self.assertEqual(self._rows()[0].skip_reason, "line_not_configured")

    def test_line_send_failure_returns_502_without_a_record(self) -> None:
        self._issuer()
        self.push.side_effect = LineSendError()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self._rows(), [])


class LineMessagingTests(unittest.TestCase):
    def test_unconfigured_push_does_not_open_the_network(self) -> None:
        with (
            patch.object(config, "LINE_CHANNEL_ACCESS_TOKEN", ""),
            patch.object(config, "LINE_GROUP_ID", ""),
            patch("app.services.line_messaging.urlopen") as urlopen,
        ):
            with self.assertRaises(LineNotConfiguredError):
                push_text_message("hello")
        urlopen.assert_not_called()

    def test_configured_push_posts_one_text_to_the_group(self) -> None:
        with (
            patch.object(config, "LINE_CHANNEL_ACCESS_TOKEN", "line-token"),
            patch.object(config, "LINE_GROUP_ID", "group-id"),
            patch("app.services.line_messaging.urlopen") as urlopen,
        ):
            urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
            push_text_message("hello")
        request = urlopen.call_args.args[0]
        self.assertIsInstance(request, Request)
        self.assertEqual(request.full_url, LINE_PUSH_URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer line-token")
        self.assertIn(b'"to": "group-id"', request.data)
        self.assertIn("hello".encode(), request.data)


if __name__ == "__main__":
    unittest.main()
