from typing import cast

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.config import AI_CONFIDENCE_REVIEW_THRESHOLD
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


class CardIssuer(Base):
    __tablename__ = "card_issuers"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(Text, nullable=False, unique=True)
    display_name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    include_in_reminder = Column(Boolean, nullable=False, default=True)
    remind_day_of_month = Column(Integer, nullable=False, default=1)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CsvImportProfile(Base):
    __tablename__ = "csv_import_profiles"
    id = Column(Integer, primary_key=True, index=True)
    card_issuer_id = Column(Integer, ForeignKey("card_issuers.id"), nullable=False, unique=True)
    encoding = Column(Text, nullable=False, default="utf-8")
    header_signature = Column(JSONB, nullable=False)
    column_mapping = Column(JSONB, nullable=False)
    transforms = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    skip_rules = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    custom_hook = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "month",
            "card_issuer_id",
            name="uq_statements_year_month_card_issuer_id",
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    card_issuer_id = Column(Integer, ForeignKey("card_issuers.id"), nullable=False)
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

    @property
    def needs_ai_review(self) -> bool:
        classified_by = cast(str | None, self.classified_by)
        confidence = cast(float | None, self.ai_confidence)
        if classified_by != "ai" or confidence is None:
            return False
        return confidence <= AI_CONFIDENCE_REVIEW_THRESHOLD


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


class StatementMailNotification(Base):
    __tablename__ = "statement_mail_notifications"
    id = Column(Integer, primary_key=True, index=True)
    card_issuer_id = Column(Integer, ForeignKey("card_issuers.id"), nullable=False)
    source_message_id = Column(Text, nullable=False, unique=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    mail_url = Column(Text, nullable=False)
    notified = Column(Boolean, nullable=False)
    skip_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
