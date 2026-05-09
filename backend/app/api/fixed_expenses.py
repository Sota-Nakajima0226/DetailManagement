from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import FixedExpense
from app.schemas import FixedExpenseCreate, FixedExpenseResponse, FixedExpenseUpdate


router = APIRouter(prefix="/fixed-expenses", tags=["fixed-expenses"])


@router.get("", response_model=list[FixedExpenseResponse])
def list_fixed_expenses(db: Session = Depends(get_db)):
    return db.query(FixedExpense).order_by(FixedExpense.id.asc()).all()


@router.post("", response_model=FixedExpenseResponse, status_code=201)
def create_fixed_expense(body: FixedExpenseCreate, db: Session = Depends(get_db)):
    item = FixedExpense(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{fixed_expense_id}", response_model=FixedExpenseResponse)
def update_fixed_expense(
    fixed_expense_id: int, body: FixedExpenseUpdate, db: Session = Depends(get_db)
):
    item = db.query(FixedExpense).filter(FixedExpense.id == fixed_expense_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Fixed expense not found")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{fixed_expense_id}", status_code=204)
def disable_fixed_expense(fixed_expense_id: int, db: Session = Depends(get_db)):
    item = db.query(FixedExpense).filter(FixedExpense.id == fixed_expense_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Fixed expense not found")
    item_obj = cast(Any, item)
    item_obj.is_active = False
    db.commit()
