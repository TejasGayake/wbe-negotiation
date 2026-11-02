"""Add ng_2_candidates.notice_negotiable

Revision ID: 0003_notice_negotiable
Revises: 0002_negotiation_flow
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0003_notice_negotiable"
down_revision = "0002_negotiation_flow"
branch_labels = None
depends_on = None


def tinyint():
    """Signed TINYINT on MySQL (needed for -1), SmallInteger elsewhere."""
    return sa.SmallInteger().with_variant(mysql.TINYINT(), "mysql")


def upgrade() -> None:
    op.add_column("ng_2_candidates", sa.Column("notice_negotiable", tinyint()))


def downgrade() -> None:
    op.drop_column("ng_2_candidates", "notice_negotiable")
