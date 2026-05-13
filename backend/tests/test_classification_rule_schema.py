from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from pydantic import ValidationError

from app.schemas import ClassificationRuleCreate, ClassificationRuleResponse


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


if __name__ == "__main__":
    unittest.main()
