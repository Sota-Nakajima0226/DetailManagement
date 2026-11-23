from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import ClassificationRule
from app.schemas import (
    ClassificationRuleCreate,
    ClassificationRuleResponse,
    ClassificationRuleUpdate,
    ClassificationRuleValidate,
)
from app.services.classification_rules import RulePatternError, validate_rule_pattern


def _ensure_pattern(pattern: str, is_regex: bool) -> None:
    try:
        validate_rule_pattern(pattern, is_regex)
    except RulePatternError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc


router = APIRouter(
    prefix="/rules",
    tags=["rules"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[ClassificationRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    return (
        db.query(ClassificationRule)
        .order_by(ClassificationRule.priority.desc(), ClassificationRule.id.asc())
        .all()
    )


@router.post("/validate", status_code=204)
def validate_rule(body: ClassificationRuleValidate) -> Response:
    _ensure_pattern(body.pattern, body.is_regex)
    return Response(status_code=204)


@router.post("", response_model=ClassificationRuleResponse, status_code=201)
def create_rule(body: ClassificationRuleCreate, db: Session = Depends(get_db)):
    _ensure_pattern(body.pattern, body.is_regex)
    item = ClassificationRule(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{rule_id}", response_model=ClassificationRuleResponse)
def update_rule(rule_id: int, body: ClassificationRuleUpdate, db: Session = Depends(get_db)):
    item = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    _ensure_pattern(body.pattern, body.is_regex)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    item = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(item)
    db.commit()
