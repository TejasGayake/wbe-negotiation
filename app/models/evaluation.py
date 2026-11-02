"""ng_4_candidate_evaluation (one-to-one with candidate)"""
from app.extensions import db
from app.models.base import TABLE_ARGS, TimestampMixin, TinyInt


class CandidateEvaluation(TimestampMixin, db.Model):
    __tablename__ = "ng_4_candidate_evaluation"
    __table_args__ = (
        db.Index("ix_ng4_profitability", "profitability_percentage"),
        TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    candidate_id = db.Column(
        db.Integer, db.ForeignKey("ng_2_candidates.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    current_ctc = db.Column(db.Numeric(12, 2))
    current_fixed_ctc = db.Column(db.Numeric(12, 2))
    current_variable_bonus = db.Column(db.Numeric(12, 2))
    expected_ctc = db.Column(db.Numeric(12, 2))
    percentage_hike_expected = db.Column(db.String(20))
    has_another_offer = db.Column(TinyInt)                  # 1=Yes, 0=No
    competing_offer_ctc = db.Column(db.Numeric(12, 2))
    other_offers_discussion = db.Column(db.Text)
    recommended_offer = db.Column(db.Numeric(12, 2))
    maximum_approved_offer = db.Column(db.Numeric(12, 2))
    estimated_market_ctc = db.Column(db.Numeric(12, 2))
    company_band_min = db.Column(db.Numeric(12, 2))
    company_band_target = db.Column(db.Numeric(12, 2))
    company_band_max = db.Column(db.Numeric(12, 2))
    minimum_acceptable_offer_candidate = db.Column(db.Numeric(12, 2))
    hr_estimated_fair_compensation = db.Column(db.Numeric(12, 2))
    is_on_bench = db.Column(TinyInt)                        # 1=Yes, 0=No
    bench_months = db.Column(db.Numeric(4, 1))
    is_client_selected_candidate = db.Column(TinyInt)       # 1=Yes, 0=No
    want_to_switch_domain = db.Column(TinyInt)              # 1=Yes, 0=No
    technical_gate_status = db.Column(TinyInt)              # 1=Cleared, 0=Pending, -1=Not Cleared
    company_upgradation = db.Column(TinyInt)                # 1=Yes, 0=No
    position_upgradation = db.Column(TinyInt)               # 1=Yes, 0=No
    risk_of_losing_candidate = db.Column(TinyInt)           # 1=High, 0=Medium, -1=Low
    technical_skills_rating = db.Column(db.Integer)         # 1-5
    domain_knowledge_rating = db.Column(db.Integer)         # 1-5
    communication_rating = db.Column(db.Integer)            # 1-5
    average_capability_rating = db.Column(db.Numeric(3, 1))
    overall_candidate_potential = db.Column(db.String(50))
    risk_compensation_expectation = db.Column(db.Integer)   # 1-5
    risk_counter_offer = db.Column(db.Integer)              # 1-5
    risk_relocation = db.Column(db.Integer)                 # 1-5
    risk_retention = db.Column(db.Integer)                  # 1-5
    risk_skill_capability = db.Column(db.Integer)           # 1-5
    risk_cultural_fit = db.Column(db.Integer)               # 1-5
    risk_notice_period = db.Column(db.Integer)              # 1-5
    risk_early_attrition = db.Column(db.Integer)            # 1-5
    average_risk_score = db.Column(db.Numeric(3, 1))
    overall_hiring_risk = db.Column(db.String(50))
    candidate_classification = db.Column(db.String(100))
    # Can be largely negative; NULL only for legacy rows.
    profitability_percentage = db.Column(db.Numeric(10, 2), nullable=True)
    key_strengths = db.Column(db.Text)
    key_concerns = db.Column(db.Text)
    notes = db.Column(db.Text)

    candidate = db.relationship("Candidate", back_populates="evaluation")
