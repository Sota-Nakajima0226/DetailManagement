"""汎用 CSV 取込エンジンの単体テスト。

ローカルの sample/ と master_data のプロファイルを参照する（sample は Git 管理外）。
"""
from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from app.services.csv_import_engine import (
    CsvImportError,
    header_signature_matches,
    parse_csv_with_profile,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
PROFILES_PATH = BACKEND_ROOT / "master_data" / "csv_import_profiles.json"
SAMPLE_RAKUTEN = REPO_ROOT / "sample" / "rakuten"
SAMPLE_AMEX = REPO_ROOT / "sample" / "amex"


def _load_profiles() -> dict[str, dict]:
    raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return {p["card_issuer_code"]: p for p in raw}


def _first_csv(directory: Path) -> Path:
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV in {directory}")
    return files[0]


@unittest.skipUnless(SAMPLE_RAKUTEN.is_dir(), "sample/rakuten not found (local only)")
@unittest.skipUnless(SAMPLE_AMEX.is_dir(), "sample/amex not found (local only)")
class TestCsvImportEngineWithSamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = _load_profiles()

    def test_rakuten_sample_parses_via_profile(self) -> None:
        profile = self.profiles["rakuten"]
        path = _first_csv(SAMPLE_RAKUTEN)
        result = parse_csv_with_profile(path.read_bytes(), profile)

        self.assertGreater(len(result.rows), 0)
        self.assertEqual(result.error_count, 0)
        # エンジン内に楽天列名のハードコードが無くても、プロファイル経由で読める
        first = result.rows[0]
        self.assertIsInstance(first.used_at, date)
        self.assertTrue(first.shop_name)
        self.assertIsInstance(first.amount, int)
        self.assertIn(first.card_holder, {"夫", "妻", None})

        holders = {r.card_holder for r in result.rows}
        self.assertTrue(holders & {"夫", "妻"})

    def test_amex_sample_parses_amount_and_holder_map(self) -> None:
        profile = self.profiles["amex"]
        path = SAMPLE_AMEX / "activity_2608.csv"
        if not path.is_file():
            path = _first_csv(SAMPLE_AMEX)
        result = parse_csv_with_profile(path.read_bytes(), profile)

        self.assertGreater(len(result.rows), 0)
        self.assertEqual(result.error_count, 0)

        # カンマ付き金額が整数化されている
        amounts = [r.amount for r in result.rows]
        self.assertTrue(any(a >= 1000 for a in amounts))

        holders = {r.card_holder for r in result.rows}
        self.assertTrue({"夫", "妻"} & holders)
        self.assertNotIn("SOTA NAKAJIMA", holders)
        self.assertNotIn("SEIRA NAKAJIMA", holders)

        # 先頭行（Expedia）の期待値
        top = result.rows[0]
        self.assertEqual(top.used_at, date(2026, 9, 1))
        self.assertEqual(top.card_holder, "妻")
        self.assertEqual(top.amount, 17003)


class TestCsvImportEngineUnit(unittest.TestCase):
    def test_header_signature_order_independent(self) -> None:
        self.assertTrue(
            header_signature_matches(
                ["B", "A", "C"],
                ["A", "B"],
            )
        )
        self.assertFalse(
            header_signature_matches(
                ["A", "C"],
                ["A", "B"],
            )
        )

    def test_skip_rules_equals(self) -> None:
        profile = {
            "encoding": "utf-8",
            "header_signature": ["利用日", "店", "金額"],
            "column_mapping": {
                "used_at": "利用日",
                "shop_name": "店",
                "amount": "金額",
                "card_holder": None,
            },
            "transforms": {
                "date_format": "%Y/%m/%d",
                "default_card_holder": "夫",
            },
            "skip_rules": [{"when_column": "店", "equals": "合計"}],
        }
        csv_text = (
            "利用日,店,金額\n"
            "2026/01/01,合計,100\n"
            "2026/01/02,カフェ,500\n"
        )
        result = parse_csv_with_profile(csv_text.encode("utf-8"), profile)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].shop_name, "カフェ")
        self.assertEqual(result.rows[0].card_holder, "夫")

    def test_signature_mismatch_raises(self) -> None:
        profile = {
            "encoding": "utf-8",
            "header_signature": ["利用日", "利用金額"],
            "column_mapping": {
                "used_at": "利用日",
                "shop_name": "店",
                "amount": "利用金額",
            },
            "transforms": {"date_format": "%Y/%m/%d"},
            "skip_rules": [],
        }
        csv_text = "日付,店,金額\n2026/01/01,A,1\n"
        with self.assertRaises(CsvImportError):
            parse_csv_with_profile(csv_text.encode("utf-8"), profile)


if __name__ == "__main__":
    unittest.main()
