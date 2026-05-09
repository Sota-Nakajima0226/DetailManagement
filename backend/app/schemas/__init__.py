from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class StatementItemResponse(BaseModel):
    id: int
    used_at: date
    shop_name: str
    amount: int
    card_holder: Optional[str] = None
    category_id: Optional[int] = None
    classified_by: Optional[str] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class StatementItemUpdateRequest(BaseModel):
    category_id: int


class StatementUploadResponse(BaseModel):
    statement_id: int
    inserted_count: int
    unclassified_count: int
    error_count: int


class StatementSummaryItem(BaseModel):
    category_id: Optional[int] = None
    category_name: str
    amount: int


class StatementSummaryResponse(BaseModel):
    year: int
    month: int
    totals: list[StatementSummaryItem]


class StatementByHolderItem(BaseModel):
    card_holder: str
    amount: int


class StatementByHolderSummaryResponse(BaseModel):
    year: int
    month: int
    totals: list[StatementByHolderItem]


class YearMonthValue(BaseModel):
    year: int
    month: int


class MonthlyTrendPoint(BaseModel):
    year: int
    month: int
    amount: int


class MonthlyTrendSeries(BaseModel):
    category_id: Optional[int] = None
    category_name: str
    points: list[MonthlyTrendPoint]


class StatementMonthlyTrendResponse(BaseModel):
    from_: YearMonthValue = Field(serialization_alias="from")
    to: YearMonthValue
    series: list[MonthlyTrendSeries]


class CategoryBase(BaseModel):
    name: str
    color: str = "#888888"
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ClassificationRuleBase(BaseModel):
    pattern: str
    is_regex: bool = False
    category_id: int
    priority: int = Field(default=0, ge=0, le=100)


class ClassificationRuleCreate(ClassificationRuleBase):
    pass


class ClassificationRuleUpdate(ClassificationRuleBase):
    pass


class ClassificationRuleResponse(ClassificationRuleBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class FixedExpenseBase(BaseModel):
    name: str
    amount: int
    category_id: int
    billing_day: Optional[int] = None
    card_holder: str = "共通"
    is_active: bool = True
    valid_from: date
    valid_until: Optional[date] = None


class FixedExpenseCreate(FixedExpenseBase):
    pass


class FixedExpenseUpdate(FixedExpenseBase):
    pass


class FixedExpenseResponse(FixedExpenseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ManualExpenseBase(BaseModel):
    used_at: date
    shop_name: str
    amount: int
    category_id: int
    card_holder: Optional[str] = None
    year: int
    month: int
    note: Optional[str] = None
    created_by: Optional[str] = None


class ManualExpenseCreate(ManualExpenseBase):
    pass


class ManualExpenseUpdate(ManualExpenseBase):
    pass


class ManualExpenseResponse(ManualExpenseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
