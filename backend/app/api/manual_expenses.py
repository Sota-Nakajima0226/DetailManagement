from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ManualExpense
from app.schemas import ManualExpenseCreate, ManualExpenseResponse, ManualExpenseUpdate


router = APIRouter(prefix="/manual-expenses", tags=["manual-expenses"])


@router.get("", response_model=list[ManualExpenseResponse])
def list_manual_expenses(
    year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)
):
    query = db.query(ManualExpense)
    if year is not None:
        query = query.filter(ManualExpense.year == year)
    if month is not None:
        query = query.filter(ManualExpense.month == month)
    return query.order_by(ManualExpense.used_at.desc(), ManualExpense.id.desc()).all()


@router.post("", response_model=ManualExpenseResponse, status_code=201)
def create_manual_expense(body: ManualExpenseCreate, db: Session = Depends(get_db)):
    item = ManualExpense(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{manual_expense_id}", response_model=ManualExpenseResponse)
def update_manual_expense(
    manual_expense_id: int, body: ManualExpenseUpdate, db: Session = Depends(get_db)
):
    item = db.query(ManualExpense).filter(ManualExpense.id == manual_expense_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Manual expense not found")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{manual_expense_id}", status_code=204)
def delete_manual_expense(manual_expense_id: int, db: Session = Depends(get_db)):
    item = db.query(ManualExpense).filter(ManualExpense.id == manual_expense_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Manual expense not found")
    db.delete(item)
    db.commit()
