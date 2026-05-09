from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Category
from app.schemas import CategoryCreate, CategoryResponse, CategoryUpdate


router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order.asc(), Category.id.asc()).all()


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    item = Category(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, body: CategoryUpdate, db: Session = Depends(get_db)):
    item = db.query(Category).filter(Category.id == category_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Category not found")
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    item = db.query(Category).filter(Category.id == category_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(item)
    db.commit()
