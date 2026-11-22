from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import CardIssuer, CsvImportProfile
from app.schemas import (
    CsvImportProfileCreate,
    CsvImportProfileResponse,
    CsvImportProfileUpdate,
)


router = APIRouter(
    prefix="/csv-import-profiles",
    tags=["csv-import-profiles"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[CsvImportProfileResponse])
def list_csv_import_profiles(db: Session = Depends(get_db)):
    return db.query(CsvImportProfile).order_by(CsvImportProfile.id.asc()).all()


@router.get("/{profile_id}", response_model=CsvImportProfileResponse)
def get_csv_import_profile(profile_id: int, db: Session = Depends(get_db)):
    item = db.query(CsvImportProfile).filter(CsvImportProfile.id == profile_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="CSV import profile not found")
    return item


@router.post("", response_model=CsvImportProfileResponse, status_code=201)
def create_csv_import_profile(body: CsvImportProfileCreate, db: Session = Depends(get_db)):
    issuer = db.query(CardIssuer).filter(CardIssuer.id == body.card_issuer_id).first()
    if issuer is None:
        raise HTTPException(status_code=400, detail="card_issuer_id not found")
    item = CsvImportProfile(**body.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="import profile for this card_issuer_id already exists",
        ) from exc
    db.refresh(item)
    return item


@router.put("/{profile_id}", response_model=CsvImportProfileResponse)
def update_csv_import_profile(
    profile_id: int,
    body: CsvImportProfileUpdate,
    db: Session = Depends(get_db),
):
    item = db.query(CsvImportProfile).filter(CsvImportProfile.id == profile_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="CSV import profile not found")
    issuer = db.query(CardIssuer).filter(CardIssuer.id == body.card_issuer_id).first()
    if issuer is None:
        raise HTTPException(status_code=400, detail="card_issuer_id not found")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    cast(Any, item).updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="import profile for this card_issuer_id already exists",
        ) from exc
    db.refresh(item)
    return item


@router.delete("/{profile_id}", status_code=204)
def delete_csv_import_profile(profile_id: int, db: Session = Depends(get_db)):
    item = db.query(CsvImportProfile).filter(CsvImportProfile.id == profile_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="CSV import profile not found")
    db.delete(item)
    db.commit()
