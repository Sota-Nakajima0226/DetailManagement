"""月次集計。発行会社未指定のときだけ、明細と手動支払いに有効な固定費を足す。"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import Column, Date, Integer, MetaData, Table, Text, select
from sqlalchemy.orm import Session

from app.models import Category, FixedExpense

monthly_expenses = Table(
    "monthly_expenses",
    MetaData(),
    Column("used_at", Date),
    Column("shop_name", Text),
    Column("amount", Integer),
    Column("card_holder", Text),
    Column("category_id", Integer),
    Column("classified_by", Text),
    Column("source", Text),
    Column("year", Integer),
    Column("month", Integer),
    Column("card_issuer_code", Text),
    Column("card_issuer_name", Text),
)


@dataclass(frozen=True)
class CategoryTotal:
    category_id: Optional[int]
    category_name: str
    amount: int


@dataclass(frozen=True)
class HolderTotal:
    card_holder: str
    amount: int


@dataclass(frozen=True)
class TrendPoint:
    year: int
    month: int
    amount: int


@dataclass(frozen=True)
class TrendSeries:
    category_id: Optional[int]
    category_name: str
    points: list[TrendPoint]


def category_totals(
    db: Session,
    year: int,
    month: int,
    card_issuer: Optional[str],
) -> list[CategoryTotal]:
    issuer = _specified_issuer(card_issuer)
    names = _category_names(db)
    amounts: dict[Optional[int], int] = {}
    for category_id, _holder, amount in _contributions(db, year, month, issuer, None):
        _add(amounts, category_id, amount)
    totals = [
        CategoryTotal(
            category_id=category_id,
            category_name=_category_name(names, category_id),
            amount=amount,
        )
        for category_id, amount in amounts.items()
    ]
    totals.sort(key=lambda row: (-row.amount, row.category_id is None, row.category_id or 0))
    return totals


def holder_totals(
    db: Session,
    year: int,
    month: int,
    card_issuer: Optional[str],
) -> list[HolderTotal]:
    issuer = _specified_issuer(card_issuer)
    amounts: dict[str, int] = {}
    for _category_id, holder, amount in _contributions(db, year, month, issuer, None):
        key = holder if holder is not None else "共通"
        amounts[key] = amounts.get(key, 0) + int(amount)
    totals = [HolderTotal(card_holder=holder, amount=amount) for holder, amount in amounts.items()]
    totals.sort(key=lambda row: (-row.amount, row.card_holder))
    return totals


def monthly_trend(
    db: Session,
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
    category_id: Optional[int],
    card_issuer: Optional[str],
) -> list[TrendSeries]:
    issuer = _specified_issuer(card_issuer)
    names = _category_names(db)
    by_category: dict[Optional[int], dict[tuple[int, int], int]] = {}
    for year, month in _iter_months(from_year, from_month, to_year, to_month):
        for row_category_id, _holder, amount in _contributions(db, year, month, issuer, category_id):
            points = by_category.setdefault(row_category_id, {})
            key = (year, month)
            points[key] = points.get(key, 0) + int(amount)

    series = [
        TrendSeries(
            category_id=row_category_id,
            category_name=_category_name(names, row_category_id),
            points=[
                TrendPoint(year=year, month=month, amount=amount)
                for (year, month), amount in sorted(points.items())
            ],
        )
        for row_category_id, points in by_category.items()
        if points
    ]
    series.sort(
        key=lambda row: (
            row.points[0].year,
            row.points[0].month,
            row.category_id is None,
            row.category_id or 0,
        )
    )
    return series


def _specified_issuer(card_issuer: Optional[str]) -> Optional[str]:
    if not card_issuer:
        return None
    return card_issuer


def _contributions(
    db: Session,
    year: int,
    month: int,
    issuer: Optional[str],
    category_id: Optional[int],
):
    rows = []
    view_stmt = select(
        monthly_expenses.c.category_id,
        monthly_expenses.c.card_holder,
        monthly_expenses.c.amount,
    ).where(
        monthly_expenses.c.year == year,
        monthly_expenses.c.month == month,
    )
    if issuer is not None:
        view_stmt = view_stmt.where(monthly_expenses.c.card_issuer_code == issuer)
    if category_id is not None:
        view_stmt = view_stmt.where(monthly_expenses.c.category_id == category_id)
    rows.extend(db.execute(view_stmt).all())
    if issuer is None:
        rows.extend(_fixed_contributions(db, year, month, category_id))
    return rows


def _fixed_contributions(db: Session, year: int, month: int, category_id: Optional[int]):
    query = db.query(FixedExpense).filter(FixedExpense.is_active.is_(True))
    if category_id is not None:
        query = query.filter(FixedExpense.category_id == category_id)
    first, last = _month_bounds(year, month)
    contributions = []
    for expense in query.all():
        valid_from = expense.valid_from
        valid_until = expense.valid_until
        if valid_from is None or valid_from > last:
            continue
        if valid_until is not None and valid_until < first:
            continue
        contributions.append((expense.category_id, expense.card_holder, expense.amount))
    return contributions


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _iter_months(from_year: int, from_month: int, to_year: int, to_month: int):
    year, month = from_year, from_month
    while (year, month) <= (to_year, to_month):
        yield year, month
        month += 1
        if month == 13:
            year += 1
            month = 1


def _category_names(db: Session) -> dict[int, str]:
    rows = db.query(Category.id, Category.name).all()
    return {int(row.id): str(row.name) for row in rows}


def _category_name(names: dict[int, str], category_id: Optional[int]) -> str:
    if category_id is None:
        return "未分類"
    return names.get(int(category_id), "未分類")


def _add(amounts: dict[Optional[int], int], category_id: Optional[int], amount: int) -> None:
    key = None if category_id is None else int(category_id)
    amounts[key] = amounts.get(key, 0) + int(amount)
