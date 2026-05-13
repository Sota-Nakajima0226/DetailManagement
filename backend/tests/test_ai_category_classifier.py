import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_category_classifier import (
    ShopAiClassification,
    classify_shop_names_openai,
)


class TestAiCategoryClassifier(unittest.IsolatedAsyncioTestCase):
    async def test_high_confidence_applies_category(self) -> None:
        categories = [(1, "食費"), (2, "交通費")]
        shops = ["セブンイレブン"]

        fake_payload = {
            "items": [
                {"shop_name": "セブンイレブン", "category_id": 1, "confidence": 0.9},
            ]
        }
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps(fake_payload, ensure_ascii=False)))
        ]

        with patch(
            "app.services.ai_category_classifier.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(create=AsyncMock(return_value=mock_response)),
                ),
            ),
        ):
            out = await classify_shop_names_openai(
                api_key="sk-test",
                model="gpt-4o-mini",
                confidence_threshold=0.7,
                categories=categories,
                shop_names=shops,
            )

        self.assertIn("セブンイレブン", out)
        r = out["セブンイレブン"]
        self.assertEqual(r.category_id, 1)
        self.assertEqual(r.classified_by, "ai")
        self.assertEqual(r.ai_confidence, 0.9)
        self.assertIsNotNone(r.ai_raw_response)

    async def test_low_confidence_leaves_unclassified(self) -> None:
        categories = [(1, "食費")]
        shops = ["不明な店"]

        fake_payload = {
            "items": [
                {"shop_name": "不明な店", "category_id": 1, "confidence": 0.3},
            ]
        }
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps(fake_payload, ensure_ascii=False)))
        ]

        with patch(
            "app.services.ai_category_classifier.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(create=AsyncMock(return_value=mock_response)),
                ),
            ),
        ):
            out = await classify_shop_names_openai(
                api_key="sk-test",
                model="gpt-4o-mini",
                confidence_threshold=0.7,
                categories=categories,
                shop_names=shops,
            )

        r = out["不明な店"]
        self.assertIsNone(r.category_id)
        self.assertIsNone(r.classified_by)
        self.assertEqual(r.ai_confidence, 0.3)

    async def test_invalid_category_id_rejected(self) -> None:
        categories = [(1, "食費")]
        shops = ["店A"]

        fake_payload = {
            "items": [
                {"shop_name": "店A", "category_id": 999, "confidence": 0.99},
            ]
        }
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps(fake_payload, ensure_ascii=False)))
        ]

        with patch(
            "app.services.ai_category_classifier.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(create=AsyncMock(return_value=mock_response)),
                ),
            ),
        ):
            out = await classify_shop_names_openai(
                api_key="sk-test",
                model="gpt-4o-mini",
                confidence_threshold=0.7,
                categories=categories,
                shop_names=shops,
            )

        r = out["店A"]
        self.assertIsNone(r.category_id)
        self.assertIsNone(r.classified_by)

    def test_shop_ai_classification_dataclass(self) -> None:
        s = ShopAiClassification(1, "ai", 0.8, "{}")
        self.assertEqual(s.category_id, 1)


if __name__ == "__main__":
    unittest.main()
