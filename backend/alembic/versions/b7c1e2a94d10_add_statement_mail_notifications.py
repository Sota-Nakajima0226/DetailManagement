"""add statement_mail_notifications

Revision ID: b7c1e2a94d10
Revises: 0a538038914e
Create Date: 2026-11-23 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c1e2a94d10"
down_revision: Union[str, Sequence[str], None] = "0a538038914e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "statement_mail_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_issuer_id", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("mail_url", sa.Text(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["card_issuer_id"], ["card_issuers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_message_id"),
    )
    op.create_index(
        op.f("ix_statement_mail_notifications_id"),
        "statement_mail_notifications",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_statement_mail_notifications_id"),
        table_name="statement_mail_notifications",
    )
    op.drop_table("statement_mail_notifications")
