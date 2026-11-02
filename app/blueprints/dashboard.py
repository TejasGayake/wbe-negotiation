"""Dashboard: KPI cards, priority table, side widgets. Cached per view tab."""
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app import services

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def root():
    return redirect(url_for("dashboard.index"))


@bp.route("/dashboard")
@login_required
def index():
    view = request.args.get("view", "all")
    if view not in services.DASHBOARD_VIEWS:
        view = "all"
    services.sync_script_statuses_if_due()          # heal a status n8n forgot to set
    data = services.get_dashboard_data(view)
    return render_template("dashboard.html", stats=data["stats"], recent=data["recent"], view=view,
                           attention=data["attention"], spread=data["spread"])
