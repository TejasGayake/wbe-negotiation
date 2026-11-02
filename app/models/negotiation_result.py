"""ng_5_negotiation_results (one-to-many; unused in Phase 1)"""
from sqlalchemy.dialects.mysql import LONGTEXT

from app.extensions import db
from app.models.base import TABLE_ARGS


class NegotiationResult(db.Model):
    __tablename__ = "ng_5_negotiation_results"
    __table_args__ = (db.Index("ix_ng5_candidate_id", "candidate_id"), TABLE_ARGS)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    candidate_id = db.Column(
        db.Integer, db.ForeignKey("ng_2_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Everything below is nullable and unused in Phase 1.
    profitability_percentage = db.Column(db.Numeric(10, 2))
    power_score = db.Column(db.Numeric(10, 2))
    profit_opportunity_score = db.Column(db.Numeric(5, 2))
    selected_strategy = db.Column(db.String(100))
    first_offer = db.Column(db.Numeric(12, 2))
    recommended_closing_min = db.Column(db.Numeric(12, 2))
    recommended_closing_max = db.Column(db.Numeric(12, 2))
    walk_away_point = db.Column(db.Numeric(12, 2))
    zopa_low = db.Column(db.Numeric(12, 2))
    zopa_high = db.Column(db.Numeric(12, 2))
    confidence_level = db.Column(db.SmallInteger())
    input_data_json = db.Column(db.Text().with_variant(LONGTEXT(), "mysql"))
    full_playbook_pdf_path = db.Column(db.String(255))
    quick_reference_pdf_path = db.Column(db.String(255))
    generated_at = db.Column(db.DateTime)
    generated_by = db.Column(db.Integer, db.ForeignKey("ng_1_users.id"))

    candidate = db.relationship("Candidate", back_populates="results")
