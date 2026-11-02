"""Negotiation workflow: status ENUM change + ng_6_negotiations

Revision ID: 0002_negotiation_flow
Revises: 0001_initial
Create Date: 2026-10-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_negotiation_flow"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

MYSQL = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}

OLD_STATUS = ("Draft", "Ready", "Generated", "Closed")
NEW_STATUS = ("Draft", "InProcess", "Generated", "Closed")


def _set_status_enum(values) -> None:
    """Rewrite the candidate status ENUM.

    MySQL stores the ENUM inline, so this is a MODIFY COLUMN. Written as raw
    SQL on purpose: it is the one statement that has to be exactly right on
    the production database.
    """
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError(
            "Migration 0002 targets MySQL 8 / MariaDB 10.6+. The test suite "
            "builds its schema with db.create_all(), it never runs migrations."
        )
    joined = ", ".join("'%s'" % v for v in values)
    op.execute(
        "ALTER TABLE ng_2_candidates MODIFY COLUMN status "
        "ENUM(%s) NOT NULL DEFAULT 'Draft'" % joined
    )


def upgrade():
    # 'Ready' meant "data entered, no script yet". The new flow starts at
    # Draft, so those rows go back to Draft.
    op.execute("UPDATE ng_2_candidates SET status = 'Draft' WHERE status = 'Ready'")
    _set_status_enum(NEW_STATUS)
    op.add_column("ng_2_candidates", sa.Column("script_requested_at", sa.DateTime()))

    # ------------------------------------------- ng_6_negotiations
    # The HR half of the negotiation: what we offered, what the candidate
    # confirmed, and the remarks. The script half stays in ng_5.
    op.create_table(
        "ng_6_negotiations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("offered_amount", sa.Numeric(12, 2)),
        sa.Column("confirmed_ctc", sa.Numeric(12, 2)),
        sa.Column("negotiation_notes", sa.Text()),
        sa.Column("closed_by", sa.Integer()),
        sa.Column("closed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["ng_2_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["closed_by"], ["ng_1_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
        **MYSQL,
    )
    op.create_index("ix_ng6_closed_at", "ng_6_negotiations", ["closed_at"])


def downgrade():
    op.drop_index("ix_ng6_closed_at", table_name="ng_6_negotiations")
    op.drop_table("ng_6_negotiations")
    op.drop_column("ng_2_candidates", "script_requested_at")
    # 'InProcess' has no 'Ready' equivalent; it falls back to Draft.
    op.execute("UPDATE ng_2_candidates SET status = 'Draft' WHERE status = 'InProcess'")
    _set_status_enum(OLD_STATUS)
