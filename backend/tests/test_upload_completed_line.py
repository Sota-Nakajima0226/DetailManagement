"""アップロード完了 LINE の単体テスト。送信はモックし、ネットワークへ送らない。"""
import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import CardIssuer, ClassificationRule, Statement, StatementItem, User
from app.services.csv_import_engine import CommonCsvRow, CsvParseResult
from app.services.line_messaging import LineSendError
from main import app


class UploadCompletedLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        CardIssuer.__table__.create(engine)
        ClassificationRule.__table__.create(engine)
        Statement.__table__.create(engine)
        StatementItem.__table__.create(engine)
        cls.Session = sessionmaker(bind=engine)

    def setUp(self) -> None:
        self.db = self.Session()
        app.dependency_overrides[get_db] = self._override_db
        app.dependency_overrides[get_current_user] = self._user
        self.client = TestClient(app)
        self.config_patch = patch.multiple(
            config,
            LINE_CHANNEL_ACCESS_TOKEN="line-token",
            LINE_GROUP_ID="group-id",
        )
        self.config_patch.start()
        self.push_patch = patch("app.services.line_messaging.push_text_message")
        self.push = self.push_patch.start()
        self.parse_patch = patch(
            "app.api.statements_v2.parse_csv_with_profile",
            side_effect=self._parse,
        )
        self.parse_patch.start()
        self.profile_patch = patch(
            "app.api.statements_v2._active_issuer_profiles",
            side_effect=self._profiles,
        )
        self.profile_patch.start()
        self.ai_patch = patch("app.api.statements_v2.OPENAI_API_KEY", "")
        self.ai_patch.start()
        self._clear()
        self._issuer("rakuten", "楽天", 1)
        self._issuer("amex", "Amex", 2)

    def tearDown(self) -> None:
        self.ai_patch.stop()
        self.profile_patch.stop()
        self.parse_patch.stop()
        self.push_patch.stop()
        self.config_patch.stop()
        app.dependency_overrides.clear()
        self.db.close()

    def _override_db(self):
        try:
            yield self.db
        finally:
            pass

    def _user(self) -> User:
        user = User()
        user.id = "00000000-0000-0000-0000-000000000001"
        user.email = "test@example.com"
        user.role = "owner"
        return user

    def _clear(self) -> None:
        self.db.query(StatementItem).delete()
        self.db.query(Statement).delete()
        self.db.query(ClassificationRule).delete()
        self.db.query(CardIssuer).delete()
        self.db.commit()

    def _issuer(self, code: str, display_name: str, sort_order: int) -> None:
        self.db.add(
            CardIssuer(
                code=code,
                display_name=display_name,
                is_active=True,
                include_in_reminder=True,
                remind_day_of_month=1,
                sort_order=sort_order,
            )
        )
        self.db.commit()

    def _profiles(self, db):
        issuers = db.query(CardIssuer).order_by(CardIssuer.sort_order.asc()).all()
        return [(issuer, object()) for issuer in issuers]

    def _parse(self, content: bytes, profile: object) -> CsvParseResult:
        if content == b"fail":
            return CsvParseResult(rows=[], error_count=1, headers=[])
        return CsvParseResult(
            rows=[
                CommonCsvRow(
                    used_at=date(2026, 3, 1),
                    shop_name="Shop",
                    amount=100,
                    card_holder="共通",
                )
            ],
            error_count=0,
            headers=["shop"],
        )

    def _upload(self, files: list[tuple[str, bytes]], codes: list[str]):
        return self.client.post(
            "/statements/upload",
            data={
                "year": "2026",
                "month": "3",
                "card_issuer_codes": codes,
            },
            files=[("files", (name, content, "text/csv")) for name, content in files],
        )

    def test_multiple_successes_send_one_message_without_a_mail_url(self) -> None:
        response = self._upload(
            [("rakuten.csv", b"ok"), ("amex.csv", b"ok")],
            ["rakuten", "amex"],
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            [item["card_issuer_code"] for item in response.json()["results"]],
            ["rakuten", "amex"],
        )
        self.push.assert_called_once_with(
            "3月の明細がアップロードされました（楽天、Amex）。確認してください。"
        )
        self.assertNotIn("mail.google.com", self.push.call_args.args[0])

    def test_failed_issuer_is_omitted_and_all_failures_send_nothing(self) -> None:
        partial = self._upload(
            [("rakuten.csv", b"ok"), ("amex.csv", b"fail")],
            ["rakuten", "amex"],
        )
        self.assertEqual(partial.status_code, 201)
        self.push.assert_called_once_with(
            "3月の明細がアップロードされました（楽天）。確認してください。"
        )

        self.push.reset_mock()
        failed = self._upload(
            [("rakuten.csv", b"fail"), ("amex.csv", b"fail")],
            ["rakuten", "amex"],
        )
        self.assertEqual(failed.status_code, 201)
        self.push.assert_not_called()

    def test_send_error_keeps_upload_response(self) -> None:
        self.push.side_effect = LineSendError()
        response = self._upload([("rakuten.csv", b"ok")], ["rakuten"])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["results"][0]["inserted_count"], 1)

    def test_missing_token_keeps_upload_response_without_push(self) -> None:
        with patch.object(config, "LINE_CHANNEL_ACCESS_TOKEN", ""):
            response = self._upload([("rakuten.csv", b"ok")], ["rakuten"])
        self.assertEqual(response.status_code, 201)
        self.push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
