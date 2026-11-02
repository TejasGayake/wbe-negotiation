"""ng_7_assessment (one-to-one with candidate)

The A-L questionnaire fields that had no home in ng_2/ng_3/ng_4: proposed
role shape, market positioning, relocation, career transition, the motivation
ranking and the HR recommendation. Derived values (averages, % hike, overall
risk band) are computed on read and never stored here.
"""
from app.extensions import db
from app.models.base import TABLE_ARGS, TimestampMixin


class Assessment(TimestampMixin, db.Model):
    __tablename__ = "ng_7_assessment"
    __table_args__ = (
        db.Index("ix_ng7_recommended_action", "recommended_action"),
        TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # UNIQUE constraint also provides the candidate_id index.
    candidate_id = db.Column(
        db.Integer, db.ForeignKey("ng_2_candidates.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )

    # A: compensation that is not cash CTC
    other_benefits = db.Column(db.Text)

    # C: proposed role
    proposed_designation = db.Column(db.String(150))
    proposed_role_level = db.Column(db.String(50))          # Same level, Higher responsibility, ...
    key_additional_responsibilities = db.Column(db.Text)
    expected_business_impact = db.Column(db.String(20))     # Low, Medium, High, Critical
    significant_career_growth = db.Column(db.String(20))    # Yes, No, Moderate

    # E: market positioning
    expected_vs_market = db.Column(db.String(50))           # Below Market ... Significantly Above

    # F: relocation
    relocation_influence_compensation = db.Column(db.String(20))   # Low, Medium, High, Very High
    can_offer_relocation_support = db.Column(db.String(20))        # Yes, No

    # G: career transition
    current_org_type = db.Column(db.String(50))
    proposed_org_type = db.Column(db.String(50))
    significant_career_transition = db.Column(db.String(20))       # Yes, No
    major_career_benefits = db.Column(db.Text)

    # H: motivation ranking, 1 = most important, blank = not applicable
    motivation_salary_rank = db.Column(db.Integer)
    motivation_career_growth_rank = db.Column(db.Integer)
    motivation_designation_rank = db.Column(db.Integer)
    motivation_role_responsibility_rank = db.Column(db.Integer)
    motivation_company_brand_rank = db.Column(db.Integer)
    motivation_oem_exposure_rank = db.Column(db.Integer)
    motivation_location_rank = db.Column(db.Integer)
    motivation_work_environment_rank = db.Column(db.Integer)
    motivation_technology_learning_rank = db.Column(db.Integer)
    motivation_international_exposure_rank = db.Column(db.Integer)
    motivation_other_rank = db.Column(db.Integer)

    # I: each side's leverage, judged by HR (ng_5.power_score is the AI score)
    candidate_negotiation_power = db.Column(db.String(20))  # Low, Medium, High
    company_negotiation_power = db.Column(db.String(20))    # Low, Medium, High

    # L: HR recommendation
    recommended_action = db.Column(db.String(30))           # Proceed with Offer, Negotiate Further, ...
    key_reason_recommended_compensation = db.Column(db.Text)
    alternatives_to_ctc = db.Column(db.Text)

    candidate = db.relationship("Candidate", back_populates="assessment")
