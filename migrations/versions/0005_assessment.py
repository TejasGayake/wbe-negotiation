"""assessment table

Revision ID: 0005_assessment
Revises: 0004_script_webhook
Create Date: 2026-10-29 00:00:00.000000

Creates ng_7_assessment, the home of the A-L questionnaire fields that had no
column in ng_2/ng_3/ng_4. The live WARS database is created by the N8NHIRING
push() DDL, so this is guarded: the table is only created when absent, and the
migration is safe to run twice and on an empty database.
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_assessment"
down_revision = "0004_script_webhook"
branch_labels = None
depends_on = None

TABLE = "ng_7_assessment"


def _columns():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return None
    return {column["name"] for column in inspector.get_columns(TABLE)}


def upgrade():
    existing = _columns()
    if existing is None:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("candidate_id", sa.Integer(), nullable=False, unique=True),
            sa.Column("other_benefits", sa.Text()),
            sa.Column("proposed_designation", sa.String(length=150)),
            sa.Column("proposed_role_level", sa.String(length=50)),
            sa.Column("key_additional_responsibilities", sa.Text()),
            sa.Column("expected_business_impact", sa.String(length=20)),
            sa.Column("significant_career_growth", sa.String(length=20)),
            sa.Column("expected_vs_market", sa.String(length=50)),
            sa.Column("relocation_influence_compensation", sa.String(length=20)),
            sa.Column("can_offer_relocation_support", sa.String(length=20)),
            sa.Column("current_org_type", sa.String(length=50)),
            sa.Column("proposed_org_type", sa.String(length=50)),
            sa.Column("significant_career_transition", sa.String(length=20)),
            sa.Column("major_career_benefits", sa.Text()),
            sa.Column("motivation_salary_rank", sa.Integer()),
            sa.Column("motivation_career_growth_rank", sa.Integer()),
            sa.Column("motivation_designation_rank", sa.Integer()),
            sa.Column("motivation_role_responsibility_rank", sa.Integer()),
            sa.Column("motivation_company_brand_rank", sa.Integer()),
            sa.Column("motivation_oem_exposure_rank", sa.Integer()),
            sa.Column("motivation_location_rank", sa.Integer()),
            sa.Column("motivation_work_environment_rank", sa.Integer()),
            sa.Column("motivation_technology_learning_rank", sa.Integer()),
            sa.Column("motivation_international_exposure_rank", sa.Integer()),
            sa.Column("motivation_other_rank", sa.Integer()),
            sa.Column("candidate_negotiation_power", sa.String(length=20)),
            sa.Column("company_negotiation_power", sa.String(length=20)),
            sa.Column("recommended_action", sa.String(length=30)),
            sa.Column("key_reason_recommended_compensation", sa.Text()),
            sa.Column("alternatives_to_ctc", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["candidate_id"], ["ng_2_candidates.id"], ondelete="CASCADE"),
            sa.Index("ix_ng7_recommended_action", "recommended_action"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )


def downgrade():
    if _columns() is not None:
        op.drop_table(TABLE)
