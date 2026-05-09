import io
import re
from datetime import datetime
from typing import Any, Optional, cast

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Category, ClassificationRule, Statement, StatementItem
from app.schemas import (
    MonthlyTrendPoint,
    MonthlyTrendSeries,
    StatementByHolderItem,
    StatementByHolderSummaryResponse,
    StatementItemResponse,
    StatementItemUpdateRequest,
    StatementMonthlyTrendResponse,
    StatementSummaryItem,
    StatementSummaryResponse,
    StatementUploadResponse,
    YearMonthValue,
)


router = APIRouter()


def _yyyymm(year: int, month: int) -> int:
    return year * 100 + month


def _normalize_card_holder(raw: Optional[str]) -> Optional[str]:
    if raw == "本人":
        return "夫"
    if raw == "家族":
        return "妻"
    return raw


def _parse_used_at(raw: str):
    return datetime.strptime(raw, "%Y/%m/%d").date()


def _classify_shop_name(shop_name: str, rules: list[ClassificationRule]) -> tuple[Optional[int], str]:
    for rule in rules:
        rule_obj = cast(Any, rule)
        pattern = str(rule_obj.pattern)
        is_regex = bool(rule_obj.is_regex)
        category_id = cast(Optional[int], rule_obj.category_id)
        matched = re.search(pattern, shop_name) if is_regex else pattern in shop_name
        if matched:
            return category_id, "rule"
    return None, "ai"


@router.post("/upload", response_model=StatementUploadResponse, status_code=201)
async def upload_statement(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid file name")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV is supported at this moment")

    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8-sig")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}") from exc

    required_columns = {"利用日", "利用店名・商品名", "利用者", "利用金額"}
    if not required_columns.issubset(df.columns):
        raise HTTPException(status_code=400, detail="CSV columns are invalid")

    statement = db.query(Statement).filter(Statement.year == year, Statement.month == month).first()
    if statement is None:
        statement = Statement(year=year, month=month, file_url=file.filename)
        db.add(statement)
        db.flush()
    else:
        statement_obj = cast(Any, statement)
        db.query(StatementItem).filter(StatementItem.statement_id == statement_obj.id).delete()
        statement_obj.file_url = file.filename

    rules = db.query(ClassificationRule).order_by(desc(ClassificationRule.priority)).all()
    inserted_count = 0
    unclassified_count = 0
    error_count = 0

    for _, row in df.iterrows():
        used_at_raw = str(row.get("利用日", "")).strip()
        shop_name = str(row.get("利用店名・商品名", "")).strip()
        amount_raw = str(row.get("利用金額", "")).strip()
        if not used_at_raw or not shop_name or not amount_raw:
            continue
        if used_at_raw == "nan" or shop_name == "nan" or amount_raw == "nan":
            continue

        try:
            amount = int(float(amount_raw))
            used_at = _parse_used_at(used_at_raw)
        except ValueError:
            error_count += 1
            continue

        category_id, classified_by = _classify_shop_name(shop_name, rules)
        if category_id is None:
            unclassified_count += 1
        statement_id = int(cast(Any, statement).id)
        item = StatementItem(
            statement_id=statement_id,
            used_at=used_at,
            shop_name=shop_name,
            amount=amount,
            card_holder=_normalize_card_holder(str(row.get("利用者", "")).strip()),
            category_id=category_id,
            classified_by=classified_by,
            source="csv",
        )
        db.add(item)
        inserted_count += 1

    db.commit()
    statement_id = int(cast(Any, statement).id)
    return StatementUploadResponse(
        statement_id=statement_id,
        inserted_count=inserted_count,
        unclassified_count=unclassified_count,
        error_count=error_count,
    )


@router.get("", response_model=list[StatementItemResponse])
def list_statements(
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[int] = None,
    card_holder: Optional[str] = None,
    is_unclassified: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(StatementItem).join(Statement, Statement.id == StatementItem.statement_id)
    if year is not None:
        query = query.filter(Statement.year == year)
    if month is not None:
        query = query.filter(Statement.month == month)
    if category is not None:
        query = query.filter(StatementItem.category_id == category)
    if card_holder:
        query = query.filter(StatementItem.card_holder == card_holder)
    if is_unclassified is True:
        query = query.filter(StatementItem.category_id.is_(None))
    if is_unclassified is False:
        query = query.filter(StatementItem.category_id.is_not(None))
    return query.order_by(desc(StatementItem.used_at), desc(StatementItem.id)).all()


@router.patch("/items/{item_id}", response_model=StatementItemResponse)
def patch_statement_item(item_id: int, body: StatementItemUpdateRequest, db: Session = Depends(get_db)):
    item = db.query(StatementItem).filter(StatementItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Statement item not found")
    item_obj = cast(Any, item)
    item_obj.category_id = body.category_id
    item_obj.classified_by = "manual"
    db.commit()
    db.refresh(item)
    return item


@router.get("/summary", response_model=StatementSummaryResponse)
def get_month_summary(year: int, month: int, db: Session = Depends(get_db)):
    totals = (
        db.query(
            StatementItem.category_id,
            func.coalesce(Category.name, "未分類").label("category_name"),
            func.sum(StatementItem.amount).label("amount"),
        )
        .join(Statement, Statement.id == StatementItem.statement_id)
        .outerjoin(Category, Category.id == StatementItem.category_id)
        .filter(Statement.year == year, Statement.month == month)
        .group_by(StatementItem.category_id, Category.name)
        .order_by(func.sum(StatementItem.amount).desc())
        .all()
    )
    return StatementSummaryResponse(
        year=year,
        month=month,
        totals=[
            StatementSummaryItem(
                category_id=row.category_id, category_name=row.category_name, amount=int(row.amount)
            )
            for row in totals
        ],
    )


@router.get("/summary/by-holder", response_model=StatementByHolderSummaryResponse)
def get_month_summary_by_holder(year: int, month: int, db: Session = Depends(get_db)):
    totals = (
        db.query(
            func.coalesce(StatementItem.card_holder, "共通").label("card_holder"),
            func.sum(StatementItem.amount).label("amount"),
        )
        .join(Statement, Statement.id == StatementItem.statement_id)
        .filter(Statement.year == year, Statement.month == month)
        .group_by(func.coalesce(StatementItem.card_holder, "共通"))
        .order_by(func.sum(StatementItem.amount).desc())
        .all()
    )
    return StatementByHolderSummaryResponse(
        year=year,
        month=month,
        totals=[StatementByHolderItem(card_holder=row.card_holder, amount=int(row.amount)) for row in totals],
    )


@router.get("/summary/monthly-trend", response_model=StatementMonthlyTrendResponse)
def get_monthly_trend(
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    from_ym = _yyyymm(from_year, from_month)
    to_ym = _yyyymm(to_year, to_month)
    if from_ym > to_ym:
        raise HTTPException(status_code=400, detail="from period must be before to period")

    query = (
        db.query(
            Statement.year,
            Statement.month,
            StatementItem.category_id,
            func.coalesce(Category.name, "未分類").label("category_name"),
            func.sum(StatementItem.amount).label("amount"),
        )
        .join(Statement, Statement.id == StatementItem.statement_id)
        .outerjoin(Category, Category.id == StatementItem.category_id)
        .filter((Statement.year * 100 + Statement.month) >= from_ym)
        .filter((Statement.year * 100 + Statement.month) <= to_ym)
    )
    if category_id is not None:
        query = query.filter(StatementItem.category_id == category_id)

    rows = (
        query.group_by(Statement.year, Statement.month, StatementItem.category_id, Category.name)
        .order_by(Statement.year.asc(), Statement.month.asc())
        .all()
    )

    grouped: dict[tuple[Optional[int], str], list[dict]] = {}
    for row in rows:
        key = (row.category_id, row.category_name)
        grouped.setdefault(key, []).append(
            {"year": row.year, "month": row.month, "amount": int(row.amount)}
        )

    series = [
        MonthlyTrendSeries(
            category_id=key[0],
            category_name=key[1],
            points=[
                MonthlyTrendPoint(
                    year=point["year"],
                    month=point["month"],
                    amount=point["amount"],
                )
                for point in points
            ],
        )
        for key, points in grouped.items()
    ]

    return StatementMonthlyTrendResponse(
        from_=YearMonthValue(year=from_year, month=from_month),
        to=YearMonthValue(year=to_year, month=to_month),
        series=series,
    )
