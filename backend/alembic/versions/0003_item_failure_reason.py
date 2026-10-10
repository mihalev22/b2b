"""items.failure_reason: причина, по которой позиция не обработалась

Статус `failed` — строковое значение в существующем поле status (String(16)),
отдельной миграции для него не нужно. См. docs/adr/0001-item-failed-status.md.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("failure_reason", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "failure_reason")
