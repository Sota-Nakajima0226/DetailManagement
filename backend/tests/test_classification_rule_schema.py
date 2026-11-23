from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import ClassificationRule, User
from app.schemas import ClassificationRuleCreate, ClassificationRuleResponse
from main import app


class TestClassificationRuleSchema(unittest.TestCase):
    def test_priority_can_exceed_100(self) -> None:
        body = ClassificationRuleCreate(
            pattern="ﾀｲﾖ-",
            is_regex=False,
            category_id=1,
            priority=220,
        )

        self.assertEqual(body.priority, 220)

        response = ClassificationRuleResponse.model_validate(
            SimpleNamespace(
                id=1,
                pattern="ﾀｲﾖ-",
                is_regex=False,
                category_id=1,
                priority=220,
                created_at=datetime.now(timezone.utc),
            )
        )

        self.assertEqual(response.priority, 220)

    def test_priority_cannot_be_negative(self) -> None:
        with self.assertRaises(ValidationError):
            ClassificationRuleCreate(
                pattern="ﾀｲﾖ-",
                is_regex=False,
                category_id=1,
                priority=-1,
            )


class TestClassificationRulePatternApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ClassificationRule.__table__.create(engine)
        cls.Session = sessionmaker(bind=engine)

    def setUp(self) -> None:
        self.db = self.Session()
        app.dependency_overrides[get_db] = self._override_db
        app.dependency_overrides[get_current_user] = self._user
        self.client = TestClient(app)
        self.db.query(ClassificationRule).delete()
        self.db.commit()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()

    def _override_db(self):
        try:
            yield self.db
        finally:
            pass

    def _user(self) -> User:
        user = User()
        row = cast(Any, user)
        row.id = "00000000-0000-0000-0000-000000000001"
        row.email = "test@example.com"
        row.role = "owner"
        return user

    def _count(self) -> int:
        return self.db.query(ClassificationRule).count()

    def _seed(self, pattern: str = "既存", is_regex: bool = False) -> ClassificationRule:
        item = ClassificationRule(
            pattern=pattern,
            is_regex=is_regex,
            category_id=1,
            priority=10,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def test_validate_accepts_literal_and_regex(self) -> None:
        before = self._count()
        literal = self.client.post(
            "/rules/validate",
            json={"pattern": "セブン", "is_regex": False},
        )
        regex = self.client.post(
            "/rules/validate",
            json={"pattern": "ネットフリックス.*", "is_regex": True},
        )
        bracket = self.client.post(
            "/rules/validate",
            json={"pattern": "[", "is_regex": False},
        )

        self.assertEqual(literal.status_code, 204)
        self.assertEqual(literal.content, b"")
        self.assertEqual(regex.status_code, 204)
        self.assertEqual(bracket.status_code, 204)
        self.assertEqual(self._count(), before)

    def test_validate_rejects_empty_and_broken_regex(self) -> None:
        before = self._count()
        empty = self.client.post(
            "/rules/validate",
            json={"pattern": "", "is_regex": False},
        )
        blank = self.client.post(
            "/rules/validate",
            json={"pattern": "   ", "is_regex": True},
        )
        broken = self.client.post(
            "/rules/validate",
            json={"pattern": "[", "is_regex": True},
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(blank.status_code, 400)
        self.assertEqual(broken.status_code, 400)
        self.assertEqual(self._count(), before)

    def test_create_accepts_literal_and_regex(self) -> None:
        literal = self.client.post(
            "/rules",
            json={
                "pattern": "セブン",
                "is_regex": False,
                "category_id": 1,
                "priority": 10,
            },
        )
        regex = self.client.post(
            "/rules",
            json={
                "pattern": "ネットフリックス.*",
                "is_regex": True,
                "category_id": 1,
                "priority": 20,
            },
        )

        self.assertEqual(literal.status_code, 201)
        self.assertEqual(regex.status_code, 201)
        self.assertEqual(self._count(), 2)
        stored = {
            (row.pattern, row.is_regex, row.priority)
            for row in self.db.query(ClassificationRule).all()
        }
        self.assertEqual(
            stored,
            {("セブン", False, 10), ("ネットフリックス.*", True, 20)},
        )

    def test_create_rejects_empty_and_broken_regex_without_insert(self) -> None:
        before = self._count()
        empty = self.client.post(
            "/rules",
            json={"pattern": "", "is_regex": False, "category_id": 1, "priority": 10},
        )
        broken = self.client.post(
            "/rules",
            json={"pattern": "[", "is_regex": True, "category_id": 1, "priority": 10},
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(broken.status_code, 400)
        self.assertEqual(self._count(), before)

    def test_update_rejects_empty_and_broken_regex_without_changing_row(self) -> None:
        item = self._seed()
        before = self._count()
        empty = self.client.put(
            f"/rules/{item.id}",
            json={"pattern": "", "is_regex": False, "category_id": 1, "priority": 99},
        )
        broken = self.client.put(
            f"/rules/{item.id}",
            json={"pattern": "[", "is_regex": True, "category_id": 2, "priority": 99},
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(broken.status_code, 400)
        self.assertEqual(self._count(), before)
        self.db.refresh(item)
        self.assertEqual(item.pattern, "既存")
        self.assertEqual(item.is_regex, False)
        self.assertEqual(item.category_id, 1)
        self.assertEqual(item.priority, 10)


if __name__ == "__main__":
    unittest.main()
