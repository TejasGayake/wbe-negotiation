"""Model package: one module per table."""
from app.models.user import User
from app.models.candidate import Candidate
from app.models.client_detail import ClientDetail
from app.models.evaluation import CandidateEvaluation
from app.models.assessment import Assessment
from app.models.negotiation_result import NegotiationResult
from app.models.negotiation import Negotiation

__all__ = ["User", "Candidate", "ClientDetail", "CandidateEvaluation",
           "Assessment", "NegotiationResult", "Negotiation"]
