"""ktru_position: справочник КТРУ и индекс для поиска по названию

Таблица наполняется отдельно из локального дампа (см. scripts/catalog/load_catalog.py),
миграция только создаёт схему, данные здесь не грузятся.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "ktru_position",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("okpd2_code", sa.String(32), nullable=True),
        sa.Column("okpd2_name", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_ktru_position_code"),
    )
    op.create_index("ix_ktru_position_okpd2_code", "ktru_position", ["okpd2_code"])
    # Поиск идёт по lower(name) LIKE lower(:pattern) — индекс строим на том же выражении.
    op.execute(
        "CREATE INDEX ix_ktru_position_name_trgm ON ktru_position "
        "USING gin (lower(name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ktru_position_name_trgm")
    op.drop_index("ix_ktru_position_okpd2_code", table_name="ktru_position")
    op.drop_table("ktru_position")
