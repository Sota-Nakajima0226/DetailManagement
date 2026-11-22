"""add card_issuers and statement issuer fk

Revision ID: 0a538038914e
Revises: c91a4f5b3d22
Create Date: 2026-11-22 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0a538038914e"
down_revision: Union[str, Sequence[str], None] = "c91a4f5b3d22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_issuers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "include_in_reminder",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "remind_day_of_month",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_card_issuers_id"), "card_issuers", ["id"], unique=False)

    op.create_table(
        "csv_import_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_issuer_id", sa.Integer(), nullable=False),
        sa.Column("encoding", sa.Text(), server_default="utf-8", nullable=False),
        sa.Column("header_signature", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("column_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "transforms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "skip_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("custom_hook", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["card_issuer_id"], ["card_issuers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_issuer_id"),
    )
    op.create_index(
        op.f("ix_csv_import_profiles_id"), "csv_import_profiles", ["id"], unique=False
    )

    # backfill 用に最低限の issuer（楽天）。Amex 等のプロファイルは後続シード。
    op.execute(
        sa.text(
            """
            INSERT INTO card_issuers (code, display_name, remind_day_of_month, sort_order)
            VALUES ('rakuten', '楽天', 23, 1)
            """
        )
    )

    op.add_column("statements", sa.Column("card_issuer_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE statements
            SET card_issuer_id = (
                SELECT id FROM card_issuers WHERE code = 'rakuten' LIMIT 1
            )
            WHERE card_issuer_id IS NULL
            """
        )
    )
    op.alter_column("statements", "card_issuer_id", nullable=False)
    op.create_foreign_key(
        "fk_statements_card_issuer_id",
        "statements",
        "card_issuers",
        ["card_issuer_id"],
        ["id"],
    )
    op.drop_constraint("uq_statements_year_month", "statements", type_="unique")
    op.create_unique_constraint(
        "uq_statements_year_month_card_issuer_id",
        "statements",
        ["year", "month", "card_issuer_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_statements_year_month_card_issuer_id", "statements", type_="unique"
    )
    op.create_unique_constraint(
        "uq_statements_year_month", "statements", ["year", "month"]
    )
    op.drop_constraint("fk_statements_card_issuer_id", "statements", type_="foreignkey")
    op.drop_column("statements", "card_issuer_id")

    op.drop_index(op.f("ix_csv_import_profiles_id"), table_name="csv_import_profiles")
    op.drop_table("csv_import_profiles")
    op.drop_index(op.f("ix_card_issuers_id"), table_name="card_issuers")
    op.drop_table("card_issuers")
