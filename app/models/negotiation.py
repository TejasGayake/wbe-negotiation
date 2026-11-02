"""ng_6_negotiations (one-to-one with candidate: the HR negotiation outcome).

This is the human half of the negotiation. The machine half - the generated
script and its two PDF links - lives in ng_5_negotiation_results.
"""
from app.extensions import db
from app.models.base import TABLE_ARGS
from app.utils.timeutil import now_ist


class Negotiation(db.Model):
    __tablename__ = "ng_6_negotiations"
    __table_args__ = (TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # UNIQUE constraint also provides the candidate_id index.
    candidate_id = db.Column(
        db.Integer, db.ForeignKey("ng_2_candidates.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    # What HR offered during the negotiation.
    offered_amount = db.Column(db.Numeric(12, 2))
    # What the candidate confirmed they will accept.
    confirmed_ctc = db.Column(db.Numeric(12, 2))
    negotiation_notes = db.Column(db.Text)
    # Who closed the negotiation, and when.
    closed_by = db.Column(db.Integer, db.ForeignKey("ng_1_users.id"))
    closed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=now_ist, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_ist, onupdate=now_ist, nullable=False)

    candidate = db.relationship("Candidate", back_populates="negotiation")
    closer = db.relationship("User", foreign_keys=[closed_by])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Negotiation candidate_id={self.candidate_id}>"
