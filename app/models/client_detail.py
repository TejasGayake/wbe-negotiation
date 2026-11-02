"""ng_3_client_details (one-to-one with candidate)"""
from app.extensions import db
from app.models.base import TABLE_ARGS, TimestampMixin, TinyInt


class ClientDetail(TimestampMixin, db.Model):
    __tablename__ = "ng_3_client_details"
    __table_args__ = (
        db.Index("ix_ng3_client_name", "client_name"),
        db.Index("ix_ng3_client_urgency", "client_urgency"),
        db.Index("ix_ng3_skill_scarcity", "skill_scarcity"),
        TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # UNIQUE constraint also provides the candidate_id index.
    candidate_id = db.Column(
        db.Integer, db.ForeignKey("ng_2_candidates.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    client_name = db.Column(db.String(150))
    client_budget = db.Column(db.Numeric(12, 2))            # annual, INR, required by forms
    client_timeline_days = db.Column(db.Integer)
    client_urgency = db.Column(TinyInt)                     # 1=High, 0=Medium, -1=Low
    client_flexibility = db.Column(TinyInt)                 # 1=Yes, 0=No
    skill_required = db.Column(db.String(150))
    skill_scarcity = db.Column(TinyInt)                     # 1=Extremely Niche, 0=Semi-niche, -1=Generic
    availability_of_talent = db.Column(TinyInt)             # 1=Easily, 0=Moderately, -1=Difficult
    position_for_client = db.Column(db.String(150))
    client_location = db.Column(db.String(100))
    replacement_hiring = db.Column(TinyInt)                 # 1=Yes, 0=No
    notes_from_client = db.Column(db.Text)

    candidate = db.relationship("Candidate", back_populates="client")
