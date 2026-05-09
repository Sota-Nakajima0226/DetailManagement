from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False)
    role = Column(Text, nullable=False)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    color = Column(Text, default="#888888")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClassificationRule(Base):
    __tablename__ = "classification_rules"
    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(Text, nullable=False)
    is_regex = Column(Boolean, default=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_statements_year_month"),)
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    file_url = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class StatementItem(Base):
    __tablename__ = "statement_items"
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id", ondelete="CASCADE"))
    used_at = Column(Date, nullable=False)
    shop_name = Column(Text, nullable=False)
    amount = Column(Integer, nullable=False)
    card_holder = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"))
    classified_by = Column(Text)
    ai_confidence = Column(Float)
    ai_raw_response = Column(Text)
    source = Column(Text, default="csv")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FixedExpense(Base):
    __tablename__ = "fixed_expenses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    amount = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    billing_day = Column(Integer)
    card_holder = Column(Text, default="共通")
    is_active = Column(Boolean, default=True)
    valid_from = Column(Date, nullable=False, server_default=func.current_date())
    valid_until = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ManualExpense(Base):
    __tablename__ = "manual_expenses"
    id = Column(Integer, primary_key=True, index=True)
    used_at = Column(Date, nullable=False)
    shop_name = Column(Text, nullable=False)
    amount = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    card_holder = Column(Text)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    note = Column(Text)
    created_by = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
