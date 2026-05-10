"""rename '未分類' category to 'その他'

未分類 (id 付きカテゴリ) は category_id = NULL のレコードと意味が重複しないよう、
「その他」(明示的に「その他」として分類するもの) にリネームする。
NULL のレコードは引き続き表示上「未分類」として扱う。

Revision ID: c91a4f5b3d22
Revises: 9e40ed7a5ae1
Create Date: 2026-05-10 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c91a4f5b3d22"
down_revision: Union[str, Sequence[str], None] = "9e40ed7a5ae1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE categories
           SET name = 'その他',
               color = '#607D8B'
         WHERE name = '未分類';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE categories
           SET name = '未分類',
               color = '#9E9E9E'
         WHERE name = 'その他';
        """
    )
