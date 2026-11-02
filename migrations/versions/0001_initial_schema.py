"""Initial schema: ng_1_users .. ng_5_negotiation_results

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-17 10:50:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

MYSQL = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def tinyint():
    """Signed TINYINT on MySQL (needed for -1), SmallInteger elsewhere."""
    return sa.SmallInteger().with_variant(mysql.TINYINT(), "mysql")


def upgrade():
    # ------------------------------------------------------------ ng_1_users
    op.create_table(
        "ng_1_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="HR"),
        sa.Column("is_active", tinyint(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        **MYSQL,
    )

    # -------------------------------------------------------- ng_2_candidates
    op.create_table(
        "ng_2_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_code", sa.String(50), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("position_applied_for", sa.String(150), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("total_years_experience", sa.Numeric(4, 1)),
        sa.Column("relevant_years_experience", sa.Numeric(4, 1)),
        sa.Column("current_company", sa.String(150)),
        sa.Column("current_designation", sa.String(150)),
        sa.Column("notice_period", sa.String(50)),
        sa.Column("current_location", sa.String(100)),
        sa.Column("proposed_work_location", sa.String(100)),
        sa.Column("relocation_required", tinyint()),
        sa.Column("primary_motivation", sa.String(100)),
        sa.Column("created_by", sa.Integer()),
        sa.Column(
            "status",
            sa.Enum("Draft", "Ready", "Generated", "Closed", name="candidate_status"),
            nullable=False, server_default="Draft",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["ng_1_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_code"),
        **MYSQL,
    )
    op.create_index("ix_ng2_status", "ng_2_candidates", ["status"])
    op.create_index("ix_ng2_department", "ng_2_candidates", ["department"])
    op.create_index("ix_ng2_full_name", "ng_2_candidates", ["full_name"])
    op.create_index("ix_ng2_created_at", "ng_2_candidates", ["created_at"])
    op.create_index("ix_ng2_created_by", "ng_2_candidates", ["created_by"])

    # ------------------------------------------------- ng_3_client_details
    op.create_table(
        "ng_3_client_details",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(150)),
        sa.Column("client_budget", sa.Numeric(12, 2)),
        sa.Column("client_timeline_days", sa.Integer()),
        sa.Column("client_urgency", tinyint()),
        sa.Column("client_flexibility", tinyint()),
        sa.Column("skill_required", sa.String(150)),
        sa.Column("skill_scarcity", tinyint()),
        sa.Column("availability_of_talent", tinyint()),
        sa.Column("position_for_client", sa.String(150)),
        sa.Column("client_location", sa.String(100)),
        sa.Column("replacement_hiring", tinyint()),
        sa.Column("notes_from_client", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["ng_2_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
        **MYSQL,
    )
    op.create_index("ix_ng3_client_name", "ng_3_client_details", ["client_name"])
    op.create_index("ix_ng3_client_urgency", "ng_3_client_details", ["client_urgency"])
    op.create_index("ix_ng3_skill_scarcity", "ng_3_client_details", ["skill_scarcity"])

    # -------------------------------------- ng_4_candidate_evaluation
    op.create_table(
        "ng_4_candidate_evaluation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("current_ctc", sa.Numeric(12, 2)),
        sa.Column("expected_ctc", sa.Numeric(12, 2)),
        sa.Column("has_another_offer", tinyint()),
        sa.Column("competing_offer_ctc", sa.Numeric(12, 2)),
        sa.Column("recommended_offer", sa.Numeric(12, 2)),
        sa.Column("maximum_approved_offer", sa.Numeric(12, 2)),
        sa.Column("is_on_bench", tinyint()),
        sa.Column("bench_months", sa.Numeric(4, 1)),
        sa.Column("is_client_selected_candidate", tinyint()),
        sa.Column("want_to_switch_domain", tinyint()),
        sa.Column("technical_gate_status", tinyint()),
        sa.Column("company_upgradation", tinyint()),
        sa.Column("position_upgradation", tinyint()),
        sa.Column("risk_of_losing_candidate", tinyint()),
        sa.Column("technical_skills_rating", sa.Integer()),
        sa.Column("domain_knowledge_rating", sa.Integer()),
        sa.Column("communication_rating", sa.Integer()),
        sa.Column("profitability_percentage", sa.Numeric(10, 2), nullable=True),
        sa.Column("key_strengths", sa.Text()),
        sa.Column("key_concerns", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["ng_2_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
        **MYSQL,
    )
    op.create_index("ix_ng4_profitability", "ng_4_candidate_evaluation", ["profitability_percentage"])

    # --------------------------------------- ng_5_negotiation_results
    op.create_table(
        "ng_5_negotiation_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("profitability_percentage", sa.Numeric(10, 2)),
        sa.Column("power_score", sa.Numeric(10, 2)),
        sa.Column("selected_strategy", sa.String(100)),
        sa.Column("input_data_json", sa.Text().with_variant(mysql.LONGTEXT(), "mysql")),
        sa.Column("full_playbook_pdf_path", sa.String(255)),
        sa.Column("quick_reference_pdf_path", sa.String(255)),
        sa.Column("generated_at", sa.DateTime()),
        sa.Column("generated_by", sa.Integer()),
        sa.ForeignKeyConstraint(["candidate_id"], ["ng_2_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["ng_1_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        **MYSQL,
    )
    op.create_index("ix_ng5_candidate_id", "ng_5_negotiation_results", ["candidate_id"])


def downgrade():
    op.drop_index("ix_ng5_candidate_id", table_name="ng_5_negotiation_results")
    op.drop_table("ng_5_negotiation_results")
    op.drop_index("ix_ng4_profitability", table_name="ng_4_candidate_evaluation")
    op.drop_table("ng_4_candidate_evaluation")
    op.drop_index("ix_ng3_skill_scarcity", table_name="ng_3_client_details")
    op.drop_index("ix_ng3_client_urgency", table_name="ng_3_client_details")
    op.drop_index("ix_ng3_client_name", table_name="ng_3_client_details")
    op.drop_table("ng_3_client_details")
    for ix in ("ix_ng2_created_by", "ix_ng2_created_at", "ix_ng2_full_name",
               "ix_ng2_department", "ix_ng2_status"):
        op.drop_index(ix, table_name="ng_2_candidates")
    op.drop_table("ng_2_candidates")
    op.drop_table("ng_1_users")
