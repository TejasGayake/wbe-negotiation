"""Negotiations: the register of negotiations in flight and already closed."""
from flask import Blueprint, render_template, request
from flask_login import login_required

from app import services

bp = Blueprint("negotiations", __name__)

STAGES = ("open", "closed", "all")


@bp.route("/negotiations")
@login_required
def index():
    """Open negotiations, closed negotiations, or both.

    A closed negotiation stays in the database but is hidden from the candidate
    tables; this is where it is looked up again.
    """
    stage = request.args.get("stage", "open")
    if stage not in STAGES:
        stage = "open"
    q = (request.args.get("q") or "").strip()[:100]
    services.sync_script_statuses_if_due()
    rows, total = services.negotiation_rows(stage, q)
    scripts = services.latest_scripts([c.id for c in rows])
    return render_template("negotiations/list.html", rows=rows, total=total,
                           stage=stage, q=q, scripts=scripts)
