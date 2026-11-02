"""ng_2_candidates"""
from app.extensions import db
from app.mappings import STATUS_CHOICES
from app.models.base import TABLE_ARGS, TimestampMixin, TinyInt


class Candidate(TimestampMixin, db.Model):
    __tablename__ = "ng_2_candidates"
    __table_args__ = (
        db.Index("ix_ng2_status", "status"),
        db.Index("ix_ng2_department", "department"),
        db.Index("ix_ng2_full_name", "full_name"),
        db.Index("ix_ng2_created_at", "created_at"),
        db.Index("ix_ng2_created_by", "created_by"),
        TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # WBE-YYYY-XXXX; generated once on create, never regenerated.
    candidate_code = db.Column(db.String(50), nullable=False, unique=True)
    full_name = db.Column(db.String(150), nullable=False)
    position_applied_for = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    total_years_experience = db.Column(db.Numeric(4, 1))
    relevant_years_experience = db.Column(db.Numeric(4, 1))
    current_company = db.Column(db.String(150))
    current_designation = db.Column(db.String(150))
    notice_period = db.Column(db.String(50))
    notice_negotiable = db.Column(TinyInt)              # 1=Yes, 0=No
    current_location = db.Column(db.String(100))
    proposed_work_location = db.Column(db.String(100))
    relocation_required = db.Column(TinyInt)          # 1=Yes, 0=No
    primary_motivation = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey("ng_1_users.id"))
    status = db.Column(
        db.Enum(*STATUS_CHOICES, name="candidate_status"),
        nullable=False, default="Draft", server_default="Draft",
    )
    # When the negotiation script was requested (n8n generates it from here).
    script_requested_at = db.Column(db.DateTime)
    # Drive share URL of the CV; copied from candidates_dump.resume_link.
    cv_drive_link = db.Column(db.String(500))

    creator = db.relationship("User", foreign_keys=[created_by], lazy="select")
    client = db.relationship(
        "ClientDetail", back_populates="candidate", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )
    evaluation = db.relationship(
        "CandidateEvaluation", back_populates="candidate", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )
    assessment = db.relationship(
        "Assessment", back_populates="candidate", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )
    results = db.relationship(
        "NegotiationResult", back_populates="candidate",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    negotiation = db.relationship(
        "Negotiation", back_populates="candidate", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Candidate {self.candidate_code}>"
