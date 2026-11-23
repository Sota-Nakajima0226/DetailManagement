import unittest
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.statements_v2 import (
    get_month_summary,
    get_month_summary_by_holder,
    get_monthly_trend,
    list_statements,
)
from app.models import CardIssuer, Category, FixedExpense, ManualExpense, Statement, StatementItem

_CREATE_VIEW = """
CREATE VIEW monthly_expenses AS
  SELECT
    si.used_at, si.shop_name, si.amount,
    si.card_holder, si.category_id,
    si.classified_by, si.source,
    s.year, s.month,
    ci.code AS card_issuer_code,
    ci.display_name AS card_issuer_name
  FROM statement_items si
  JOIN statements s ON s.id = si.statement_id
  JOIN card_issuers ci ON ci.id = s.card_issuer_id

  UNION ALL

  SELECT
    me.used_at, me.shop_name, me.amount,
    me.card_holder, me.category_id,
    'manual' AS classified_by, 'manual' AS source,
    me.year, me.month,
    NULL AS card_issuer_code,
    NULL AS card_issuer_name
  FROM manual_expenses me
"""


class MonthlySummaryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        for model in (Category, CardIssuer, Statement, StatementItem, ManualExpense, FixedExpense):
            model.__table__.create(engine)
        with engine.begin() as conn:
            conn.execute(text(_CREATE_VIEW))
        self.db = sessionmaker(bind=engine)()
        self.engine = engine
        self._seed()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _seed(self):
        self.db.add_all(
            [
                Category(id=1, name="食費"),
                Category(id=2, name="住居"),
                CardIssuer(id=1, code="rakuten", display_name="楽天"),
                CardIssuer(id=2, code="amex", display_name="Amex"),
                Statement(id=1, year=2026, month=2, card_issuer_id=1),
                Statement(id=2, year=2026, month=3, card_issuer_id=1),
                Statement(id=3, year=2026, month=3, card_issuer_id=2),
                StatementItem(
                    statement_id=1,
                    used_at=date(2026, 2, 10),
                    shop_name="コンビニ",
                    amount=1000,
                    card_holder="夫",
                    category_id=1,
                    classified_by="rule",
                    source="csv",
                ),
                StatementItem(
                    statement_id=2,
                    used_at=date(2026, 3, 10),
                    shop_name="サブスク",
                    amount=2000,
                    card_holder="夫",
                    category_id=1,
                    classified_by="rule",
                    source="csv",
                ),
                StatementItem(
                    statement_id=3,
                    used_at=date(2026, 3, 11),
                    shop_name="家賃カード",
                    amount=3000,
                    card_holder="妻",
                    category_id=2,
                    classified_by="rule",
                    source="csv",
                ),
                ManualExpense(
                    used_at=date(2026, 3, 1),
                    shop_name="現金",
                    amount=400,
                    category_id=1,
                    card_holder=None,
                    year=2026,
                    month=2,
                ),
                ManualExpense(
                    used_at=date(2026, 2, 15),
                    shop_name="振替",
                    amount=999,
                    category_id=1,
                    card_holder="夫",
                    year=2026,
                    month=3,
                ),
                FixedExpense(
                    name="サブスク",
                    amount=5000,
                    category_id=1,
                    billing_day=27,
                    card_holder=None,
                    is_active=True,
                    valid_from=date(2026, 3, 15),
                    valid_until=None,
                ),
                FixedExpense(
                    name="三月だけ",
                    amount=800,
                    category_id=2,
                    billing_day=1,
                    card_holder="妻",
                    is_active=True,
                    valid_from=date(2026, 3, 1),
                    valid_until=date(2026, 3, 1),
                ),
                FixedExpense(
                    name="停止",
                    amount=7000,
                    category_id=1,
                    billing_day=10,
                    card_holder="夫",
                    is_active=False,
                    valid_from=date(2026, 1, 1),
                    valid_until=None,
                ),
                FixedExpense(
                    name="四月開始",
                    amount=1234,
                    category_id=1,
                    billing_day=1,
                    card_holder="共通",
                    is_active=True,
                    valid_from=date(2026, 4, 1),
                    valid_until=None,
                ),
            ]
        )
        self.db.commit()

    def test_march_start_fixed_is_absent_in_february_and_full_from_march(self):
        february = self._category_map(2026, 2, None)
        march = self._category_map(2026, 3, None)
        self.assertEqual(february, {1: 1400})
        self.assertEqual(march[1], 7999)
        self.assertNotIn(5000, february.values())

    def test_valid_until_on_the_first_includes_only_that_month(self):
        self.assertNotIn(2, self._category_map(2026, 2, None))
        self.assertEqual(self._category_map(2026, 3, None)[2], 3800)
        self.assertNotIn(2, self._category_map(2026, 4, None))

    def test_inactive_fixed_expense_is_excluded(self):
        march = self._category_map(2026, 3, None)
        self.assertEqual(march[1], 7999)
        self.assertNotEqual(march[1], 7999 + 7000)

    def test_manual_follows_year_month_not_used_at(self):
        february = self._category_map(2026, 2, None)
        march = self._category_map(2026, 3, None)
        self.assertEqual(february[1], 1400)
        self.assertEqual(march[1], 7999)

    def test_same_category_is_one_row_without_name_dedup(self):
        totals = get_month_summary(2026, 3, None, self.db).totals
        food = [row for row in totals if row.category_id == 1]
        self.assertEqual(len(food), 1)
        self.assertEqual(food[0].amount, 7999)
        self.assertEqual(food[0].category_name, "食費")

    def test_specified_and_unknown_issuer_exclude_manual_and_fixed(self):
        self.assertEqual(self._category_map(2026, 3, "rakuten"), {1: 2000})
        self.assertEqual(self._category_map(2026, 3, "amex"), {2: 3000})
        self.assertEqual(self._category_map(2026, 3, "unknown"), {})
        self.assertEqual(self._holder_map(2026, 3, "rakuten"), {"夫": 2000})

    def test_blank_issuer_matches_unspecified(self):
        self.assertEqual(self._category_map(2026, 3, ""), self._category_map(2026, 3, None))
        self.assertEqual(self._holder_map(2026, 3, ""), self._holder_map(2026, 3, None))

    def test_unspecified_totals_match_across_category_holder_and_trend(self):
        categories = self._category_map(2026, 3, None)
        holders = self._holder_map(2026, 3, None)
        trend = get_monthly_trend(2026, 2, 2026, 4, None, None, self.db)
        march_points = [
            point.amount
            for series in trend.series
            for point in series.points
            if point.year == 2026 and point.month == 3
        ]
        self.assertEqual(sum(categories.values()), 11799)
        self.assertEqual(sum(holders.values()), 11799)
        self.assertEqual(sum(march_points), 11799)
        self.assertEqual(holders, {"夫": 2999, "妻": 3800, "共通": 5000})

    def test_trend_category_filter_and_issuer_filter(self):
        food = get_monthly_trend(2026, 2, 2026, 4, 1, None, self.db)
        self.assertEqual(len(food.series), 1)
        self.assertEqual(
            [(point.month, point.amount) for point in food.series[0].points],
            [(2, 1400), (3, 7999), (4, 6234)],
        )
        rakuten = get_monthly_trend(2026, 2, 2026, 4, None, "rakuten", self.db)
        amounts = {
            (series.category_id, point.month): point.amount
            for series in rakuten.series
            for point in series.points
        }
        self.assertEqual(amounts, {(1, 2): 1000, (1, 3): 2000})

    def test_response_keys_stay_the_same(self):
        summary = get_month_summary(2026, 3, None, self.db).model_dump()
        self.assertEqual(set(summary), {"year", "month", "totals"})
        self.assertEqual(set(summary["totals"][0]), {"category_id", "category_name", "amount"})
        holders = get_month_summary_by_holder(2026, 3, None, self.db).model_dump()
        self.assertEqual(set(holders), {"year", "month", "totals"})
        self.assertEqual(set(holders["totals"][0]), {"card_holder", "amount"})
        trend = get_monthly_trend(2026, 2, 2026, 4, None, None, self.db).model_dump(by_alias=True)
        self.assertEqual(set(trend), {"from", "to", "series"})
        self.assertEqual(set(trend["series"][0]), {"category_id", "category_name", "points"})
        self.assertEqual(set(trend["series"][0]["points"][0]), {"year", "month", "amount"})

    def test_statement_list_stays_card_items_only(self):
        rows = list_statements(2026, 3, None, None, None, None, self.db)
        self.assertEqual(sorted(row.shop_name for row in rows), ["サブスク", "家賃カード"])
        self.assertEqual(sorted(row.amount for row in rows), [2000, 3000])

    def _category_map(self, year, month, card_issuer):
        totals = get_month_summary(year, month, card_issuer, self.db).totals
        return {row.category_id: row.amount for row in totals}

    def _holder_map(self, year, month, card_issuer):
        totals = get_month_summary_by_holder(year, month, card_issuer, self.db).totals
        return {row.card_holder: row.amount for row in totals}


if __name__ == "__main__":
    unittest.main()
