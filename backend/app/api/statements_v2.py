from __future__ import annotations

import logging
import re
from typing import Any, List, Optional, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, func, literal_column
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import (
    AI_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from app.core.database import get_db
from app.models import (
    CardIssuer,
    Category,
    ClassificationRule,
    CsvImportProfile,
    Statement,
    StatementItem,
)
from app.services.ai_category_classifier import (
    ShopAiClassification,
    classify_shop_names_openai,
)
from app.services.csv_import_engine import (
    CsvImportError,
    header_signature_matches,
    parse_csv_with_profile,
    peek_csv_headers,
)
from app.schemas import (
    DetectIssuerCandidate,
    DetectIssuerResponse,
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
    StatementUploadResultItem,
    UploadStatusIssuer,
    UploadStatusResponse,
    UploadStatusUploadedIssuer,
    YearMonthValue,
)


router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


def _yyyymm(year: int, month: int) -> int:
    return year * 100 + month


def _classify_by_rules(shop_name: str, rules: list[ClassificationRule]) -> Optional[int]:
    """ルールに最初にマッチしたカテゴリ ID。マッチなしは None。"""
    for rule in rules:
        rule_obj = cast(Any, rule)
        pattern = str(rule_obj.pattern)
        is_regex = bool(rule_obj.is_regex)
        category_id = cast(Optional[int], rule_obj.category_id)
        matched = re.search(pattern, shop_name) if is_regex else pattern in shop_name
        if matched:
            return category_id
    return None


def _active_issuer_profiles(db: Session) -> list[tuple[CardIssuer, CsvImportProfile]]:
    # SQLAlchemy の query(...).all() はスタブ上 Row/Any になりがちなので明示キャストする。
    rows = (
        db.query(CardIssuer, CsvImportProfile)
        .join(CsvImportProfile, CsvImportProfile.card_issuer_id == CardIssuer.id)
        .filter(CardIssuer.is_active.is_(True))
        .order_by(CardIssuer.sort_order.asc(), CardIssuer.id.asc())
        .all()
    )
    return cast(list[tuple[CardIssuer, CsvImportProfile]], rows)


def _match_issuer_candidates(
    content: bytes,
    pairs: list[tuple[CardIssuer, CsvImportProfile]],
) -> list[DetectIssuerCandidate]:
    candidates: list[DetectIssuerCandidate] = []
    for issuer, profile in pairs:
        encoding = str(cast(Any, profile).encoding or "utf-8")
        headers = peek_csv_headers(content, encoding)
        if not headers:
            continue
        signature = list(cast(Any, profile).header_signature or [])
        if header_signature_matches(headers, signature):
            candidates.append(
                DetectIssuerCandidate(
                    code=str(issuer.code),
                    display_name=str(issuer.display_name),
                )
            )
    return candidates


def _resolve_issuer_code(
    content: bytes,
    explicit_code: Optional[str],
    pairs: list[tuple[CardIssuer, CsvImportProfile]],
    file_label: str,
) -> str:
    if explicit_code:
        code = explicit_code.strip()
        if not code:
            raise HTTPException(status_code=400, detail=f"Empty card_issuer_code for {file_label}")
        known = {str(issuer.code) for issuer, _ in pairs}
        if code not in known:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown or inactive card_issuer_code '{code}' for {file_label}",
            )
        return code

    candidates = _match_issuer_candidates(content, pairs)
    if len(candidates) != 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not uniquely detect issuer for {file_label}; "
                "send card_issuer_codes"
            ),
        )
    return candidates[0].code


def _profile_for_code(
    pairs: list[tuple[CardIssuer, CsvImportProfile]],
    code: str,
) -> tuple[CardIssuer, CsvImportProfile]:
    for issuer, profile in pairs:
        if str(issuer.code) == code:
            return issuer, profile
    raise HTTPException(status_code=400, detail=f"Unknown card_issuer_code '{code}'")


async def _classify_rows(
    db: Session,
    shop_names_needing_ai: list[str],
) -> dict[str, ShopAiClassification]:
    ai_by_shop: dict[str, ShopAiClassification] = {}
    if not shop_names_needing_ai:
        return ai_by_shop
    if not OPENAI_API_KEY:
        logger.info("OPENAI_API_KEY is not set; skipping AI classification")
        return ai_by_shop

    category_rows = (
        db.query(Category).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    )
    cat_tuples = [(int(cast(Any, c.id)), str(c.name)) for c in category_rows]
    if not cat_tuples:
        return ai_by_shop
    try:
        return await classify_shop_names_openai(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            confidence_threshold=AI_CLASSIFICATION_CONFIDENCE_THRESHOLD,
            categories=cat_tuples,
            shop_names=shop_names_needing_ai,
        )
    except Exception:
        logger.exception("AI classification aborted")
        return {}


@router.post("/detect-issuer", response_model=DetectIssuerResponse)
async def detect_issuer(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid file name")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV is supported at this moment")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    candidates = _match_issuer_candidates(content, _active_issuer_profiles(db))
    if len(candidates) == 1:
        only = candidates[0]
        return DetectIssuerResponse(
            detected_code=only.code,
            detected_display_name=only.display_name,
            confidence="high",
            candidates=candidates,
        )

    return DetectIssuerResponse(
        detected_code=None,
        detected_display_name=None,
        confidence=None,
        candidates=candidates,
    )


@router.post("/upload", response_model=StatementUploadResponse, status_code=201)
async def upload_statement(
    year: int = Form(...),
    month: int = Form(...),
    files: List[UploadFile] = File(...),
    card_issuer_codes: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    codes = list(card_issuer_codes) if card_issuer_codes else []
    if codes and len(codes) != len(files):
        raise HTTPException(
            status_code=400,
            detail="files and card_issuer_codes must have the same length",
        )

    pairs = _active_issuer_profiles(db)
    if not pairs:
        raise HTTPException(status_code=500, detail="No active card issuers with profiles")

    file_payloads: list[tuple[str, bytes, Optional[str]]] = []
    for index, upload in enumerate(files):
        label = upload.filename or f"files[{index}]"
        if not upload.filename:
            raise HTTPException(status_code=400, detail=f"Invalid file name for {label}")
        if not upload.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"Only CSV is supported: {label}")
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Empty file: {label}")
        explicit = codes[index] if codes else None
        file_payloads.append((upload.filename, content, explicit))

    resolved_codes = [
        _resolve_issuer_code(content, explicit, pairs, filename)
        for filename, content, explicit in file_payloads
    ]
    if len(set(resolved_codes)) != len(resolved_codes):
        raise HTTPException(
            status_code=400,
            detail="Duplicate card_issuer_code in the same upload request",
        )

    rules = db.query(ClassificationRule).order_by(desc(ClassificationRule.priority)).all()
    results: list[StatementUploadResultItem] = []

    for (filename, content, _), issuer_code in zip(file_payloads, resolved_codes):
        issuer, profile = _profile_for_code(pairs, issuer_code)
        issuer_id = int(cast(Any, issuer).id)

        try:
            parsed = parse_csv_with_profile(content, profile)
        except CsvImportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        statement = (
            db.query(Statement)
            .filter(
                Statement.year == year,
                Statement.month == month,
                Statement.card_issuer_id == issuer_id,
            )
            .first()
        )
        if statement is None:
            statement = Statement(
                year=year,
                month=month,
                card_issuer_id=issuer_id,
                file_url=filename,
            )
            db.add(statement)
            db.flush()
        else:
            statement_obj = cast(Any, statement)
            db.query(StatementItem).filter(
                StatementItem.statement_id == statement_obj.id
            ).delete()
            statement_obj.file_url = filename

        prepared: list[dict[str, Any]] = []
        for row in parsed.rows:
            prepared.append(
                {
                    "used_at": row.used_at,
                    "shop_name": row.shop_name,
                    "amount": row.amount,
                    "card_holder": row.card_holder,
                    "rule_category_id": _classify_by_rules(row.shop_name, rules),
                }
            )

        shops_for_ai = list(
            dict.fromkeys(
                r["shop_name"] for r in prepared if r["rule_category_id"] is None
            )
        )
        ai_by_shop = await _classify_rows(db, shops_for_ai)

        inserted_count = 0
        unclassified_count = 0
        statement_id = int(cast(Any, statement).id)
        for row in prepared:
            rule_cat = cast(Optional[int], row["rule_category_id"])
            category_id: Optional[int] = rule_cat
            classified_by: Optional[str] = "rule" if rule_cat is not None else None
            ai_confidence: Optional[float] = None
            ai_raw_response: Optional[str] = None

            if category_id is None:
                ai_result = ai_by_shop.get(row["shop_name"])
                if ai_result is not None:
                    category_id = ai_result.category_id
                    classified_by = ai_result.classified_by
                    ai_confidence = ai_result.ai_confidence
                    ai_raw_response = ai_result.ai_raw_response

            if category_id is None:
                unclassified_count += 1

            db.add(
                StatementItem(
                    statement_id=statement_id,
                    used_at=row["used_at"],
                    shop_name=row["shop_name"],
                    amount=row["amount"],
                    card_holder=row["card_holder"],
                    category_id=category_id,
                    classified_by=classified_by,
                    ai_confidence=ai_confidence,
                    ai_raw_response=ai_raw_response,
                    source="csv",
                )
            )
            inserted_count += 1

        results.append(
            StatementUploadResultItem(
                card_issuer_code=issuer_code,
                statement_id=statement_id,
                inserted_count=inserted_count,
                unclassified_count=unclassified_count,
                error_count=parsed.error_count,
            )
        )

    db.commit()
    return StatementUploadResponse(results=results)


def _item_to_response(
    item: StatementItem,
    card_issuer_code: Optional[str],
    card_issuer_name: Optional[str],
) -> StatementItemResponse:
    return StatementItemResponse(
        id=int(cast(Any, item).id),
        used_at=cast(Any, item).used_at,
        shop_name=str(item.shop_name),
        amount=int(cast(Any, item).amount),
        card_holder=cast(Any, item).card_holder,
        category_id=cast(Any, item).category_id,
        classified_by=cast(Any, item).classified_by,
        ai_confidence=cast(Any, item).ai_confidence,
        needs_ai_review=bool(item.needs_ai_review),
        source=str(item.source or "csv"),
        created_at=cast(Any, item).created_at,
        card_issuer_code=card_issuer_code,
        card_issuer_name=card_issuer_name,
    )


@router.get("/upload-status", response_model=UploadStatusResponse)
def get_upload_status(year: int, month: int, db: Session = Depends(get_db)):
    expected_rows = (
        db.query(CardIssuer)
        .filter(
            CardIssuer.is_active.is_(True),
            CardIssuer.include_in_reminder.is_(True),
        )
        .order_by(CardIssuer.sort_order.asc(), CardIssuer.id.asc())
        .all()
    )
    expected = [
        UploadStatusIssuer(code=str(i.code), display_name=str(i.display_name))
        for i in expected_rows
    ]
    expected_codes = {e.code for e in expected}

    uploaded: list[UploadStatusUploadedIssuer] = []
    if expected_codes:
        uploaded_rows = (
            db.query(Statement, CardIssuer)
            .join(CardIssuer, CardIssuer.id == Statement.card_issuer_id)
            .filter(Statement.year == year, Statement.month == month)
            .filter(CardIssuer.code.in_(expected_codes))
            .order_by(CardIssuer.sort_order.asc(), CardIssuer.id.asc())
            .all()
        )
        uploaded = [
            UploadStatusUploadedIssuer(
                code=str(issuer.code),
                display_name=str(issuer.display_name),
                statement_id=int(cast(Any, statement).id),
                uploaded_at=cast(Any, statement).uploaded_at,
            )
            for statement, issuer in uploaded_rows
        ]
    uploaded_codes = {u.code for u in uploaded}
    missing = [e for e in expected if e.code not in uploaded_codes]
    return UploadStatusResponse(
        year=year,
        month=month,
        expected_issuers=expected,
        uploaded=uploaded,
        missing=missing,
    )


@router.get("", response_model=List[StatementItemResponse])
def list_statements(
    year: Optional[int] = None,
    month: Optional[int] = None,
    category: Optional[int] = None,
    card_holder: Optional[str] = None,
    card_issuer: Optional[str] = None,
    is_unclassified: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(StatementItem, CardIssuer.code, CardIssuer.display_name)
        .join(Statement, Statement.id == StatementItem.statement_id)
        .join(CardIssuer, CardIssuer.id == Statement.card_issuer_id)
    )
    if year is not None:
        query = query.filter(Statement.year == year)
    if month is not None:
        query = query.filter(Statement.month == month)
    if category is not None:
        query = query.filter(StatementItem.category_id == category)
    if card_holder:
        query = query.filter(StatementItem.card_holder == card_holder)
    if card_issuer:
        query = query.filter(CardIssuer.code == card_issuer)
    if is_unclassified is True:
        query = query.filter(StatementItem.category_id.is_(None))
    if is_unclassified is False:
        query = query.filter(StatementItem.category_id.is_not(None))
    rows = query.order_by(desc(StatementItem.used_at), desc(StatementItem.id)).all()
    return [
        _item_to_response(item, str(code) if code is not None else None, str(name) if name is not None else None)
        for item, code, name in rows
    ]


@router.patch("/items/{item_id}", response_model=StatementItemResponse)
def patch_statement_item(item_id: int, body: StatementItemUpdateRequest, db: Session = Depends(get_db)):
    row = (
        db.query(StatementItem, CardIssuer.code, CardIssuer.display_name)
        .join(Statement, Statement.id == StatementItem.statement_id)
        .join(CardIssuer, CardIssuer.id == Statement.card_issuer_id)
        .filter(StatementItem.id == item_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Statement item not found")
    item, code, name = row
    item_obj = cast(Any, item)
    item_obj.category_id = body.category_id
    item_obj.classified_by = "manual"
    item_obj.ai_confidence = None
    item_obj.ai_raw_response = None
    db.commit()
    db.refresh(item)
    return _item_to_response(
        item,
        str(code) if code is not None else None,
        str(name) if name is not None else None,
    )


@router.get("/summary", response_model=StatementSummaryResponse)
def get_month_summary(
    year: int,
    month: int,
    card_issuer: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            StatementItem.category_id,
            func.coalesce(Category.name, "未分類").label("category_name"),
            func.sum(StatementItem.amount).label("amount"),
        )
        .join(Statement, Statement.id == StatementItem.statement_id)
        .join(CardIssuer, CardIssuer.id == Statement.card_issuer_id)
        .outerjoin(Category, Category.id == StatementItem.category_id)
        .filter(Statement.year == year, Statement.month == month)
    )
    if card_issuer:
        query = query.filter(CardIssuer.code == card_issuer)
    totals = (
        query.group_by(StatementItem.category_id, Category.name)
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
def get_month_summary_by_holder(
    year: int,
    month: int,
    card_issuer: Optional[str] = None,
    db: Session = Depends(get_db),
):
    holder_expr = func.coalesce(
        StatementItem.card_holder,
        literal_column("'共通'"),
    ).label("card_holder")
    amount_sum = func.sum(StatementItem.amount)
    query = (
        db.query(
            holder_expr,
            amount_sum.label("amount"),
        )
        .join(Statement, Statement.id == StatementItem.statement_id)
        .join(CardIssuer, CardIssuer.id == Statement.card_issuer_id)
        .filter(Statement.year == year, Statement.month == month)
    )
    if card_issuer:
        query = query.filter(CardIssuer.code == card_issuer)
    totals = query.group_by(holder_expr).order_by(amount_sum.desc()).all()
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
