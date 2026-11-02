"""script webhook columns

Revision ID: 0004_script_webhook
Revises: 0003_notice_negotiable
Create Date: 2026-10-29 00:00:00.000000

The live WARS database is created by the N8NHIRING push() DDL, not by these
migrations, so every ADD here is guarded by an existence check. The same
migration is safe to run twice and safe on an empty database.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_script_webhook"
down_revision = "0003_notice_negotiable"
branch_labels = None
depends_on = None

# table -> [(column, type)]
COLUMNS = {
    "ng_2_candidates": [
        ("cv_drive_link", sa.String(length=500)),
    ],
    "ng_4_candidate_evaluation": [
        ("estimated_market_ctc", sa.Numeric(12, 2)),
        ("company_band_min", sa.Numeric(12, 2)),
        ("company_band_target", sa.Numeric(12, 2)),
        ("company_band_max", sa.Numeric(12, 2)),
    ],
    "ng_5_negotiation_results": [
        ("profit_opportunity_score", sa.Numeric(5, 2)),
        ("first_offer", sa.Numeric(12, 2)),
        ("recommended_closing_min", sa.Numeric(12, 2)),
        ("recommended_closing_max", sa.Numeric(12, 2)),
        ("walk_away_point", sa.Numeric(12, 2)),
        ("zopa_low", sa.Numeric(12, 2)),
        ("zopa_high", sa.Numeric(12, 2)),
        ("confidence_level", sa.SmallInteger()),
    ],
}


def _columns_of(table):
    """Existing column names for table, or None when the table is absent."""
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return None
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade():
    for table, columns in COLUMNS.items():
        existing = _columns_of(table)
        if existing is None:
            continue
        for name, type_ in columns:
            if name not in existing:
                op.add_column(table, sa.Column(name, type_, nullable=True))


def downgrade():
    for table, columns in COLUMNS.items():
        existing = _columns_of(table)
        if existing is None:
            continue
        for name, _ in columns:
            if name in existing:
                op.drop_column(table, name)
