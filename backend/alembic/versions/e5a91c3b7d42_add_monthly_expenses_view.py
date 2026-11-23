"""add monthly_expenses view

Revision ID: e5a91c3b7d42
Revises: b7c1e2a94d10
Create Date: 2026-11-23 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5a91c3b7d42"
down_revision: Union[str, Sequence[str], None] = "b7c1e2a94d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREATE_VIEW = """
CREATE VIEW monthly_expenses AS
  SELECT
    si.used_at, si.shop_name, si.amount,
    si.card_holder, si.category_id,
    si.classified_by, si.source,
    s.year, s.month,
    ci.code AS card_issuer_code,
    ci.display_name AS card_issuer_name
  FROM statement_items si
  JOIN statements s ON s.id = si.statement_id
  JOIN card_issuers ci ON ci.id = s.card_issuer_id

  UNION ALL

  SELECT
    me.used_at, me.shop_name, me.amount,
    me.card_holder, me.category_id,
    'manual' AS classified_by, 'manual' AS source,
    me.year, me.month,
    NULL AS card_issuer_code,
    NULL AS card_issuer_name
  FROM manual_expenses me
"""


def upgrade() -> None:
    op.execute(_CREATE_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW monthly_expenses")
