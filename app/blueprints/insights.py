"""Negotiation & Insights: portfolio-level analysis + the header bell feed."""
from flask import Blueprint, jsonify, render_template, url_for
from flask_login import login_required

from app import services
from app.extensions import cache
from app.models import Candidate, CandidateEvaluation, ClientDetail

bp = Blueprint("insights", __name__)


@bp.route("/insights")
@login_required
def index():
    stats = services.dashboard_stats()
    return render_template(
        "insights.html",
        stats=stats,
        by_client=services.margin_by(ClientDetail.client_name, 8),
        by_department=services.margin_by(Candidate.department, 8),
        urgency=services.distribution(ClientDetail.client_urgency),
        scarcity=services.distribution(ClientDetail.skill_scarcity),
        risk=services.distribution(CandidateEvaluation.risk_of_losing_candidate),
        negative=services.attention_candidates(8, only_negative=True),
        watch=services.attention_candidates(8),
    )


@bp.route("/api/attention")
@login_required
def attention_feed():
    """Lazy feed for the notification bell (loaded after page render, not during it)."""
    cached = cache.get("attention_feed")
    if cached is not None:
        return jsonify(cached)
    
    items = services.attention_candidates(6)
    result = {
        "count": services.attention_count(),
        "items": [{
            "name": c.full_name,
            "code": c.candidate_code,
            "margin": None if not c.evaluation or c.evaluation.profitability_percentage is None
                      else float(c.evaluation.profitability_percentage),
            "status": c.status,
            "url": url_for("candidates.summary", candidate_id=c.id),
        } for c in items],
    }
    cache.set("attention_feed", result)
    return jsonify(result)
