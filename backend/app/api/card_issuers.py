from __future__ import annotations

from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import CardIssuer
from app.schemas import CardIssuerCreate, CardIssuerResponse, CardIssuerUpdate


router = APIRouter(
    prefix="/card-issuers",
    tags=["card-issuers"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[CardIssuerResponse])
def list_card_issuers(db: Session = Depends(get_db)):
    return (
        db.query(CardIssuer)
        .order_by(CardIssuer.sort_order.asc(), CardIssuer.id.asc())
        .all()
    )


@router.post("", response_model=CardIssuerResponse, status_code=201)
def create_card_issuer(body: CardIssuerCreate, db: Session = Depends(get_db)):
    item = CardIssuer(**body.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="card issuer code already exists") from exc
    db.refresh(item)
    return item


@router.put("/{issuer_id}", response_model=CardIssuerResponse)
def update_card_issuer(issuer_id: int, body: CardIssuerUpdate, db: Session = Depends(get_db)):
    item = db.query(CardIssuer).filter(CardIssuer.id == issuer_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Card issuer not found")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="card issuer code already exists") from exc
    db.refresh(item)
    return item


@router.delete("/{issuer_id}", response_model=CardIssuerResponse)
def deactivate_card_issuer(issuer_id: int, db: Session = Depends(get_db)):
    """論理削除: is_active=false。"""
    item = db.query(CardIssuer).filter(CardIssuer.id == issuer_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Card issuer not found")
    cast(Any, item).is_active = False
    db.commit()
    db.refresh(item)
    return item
