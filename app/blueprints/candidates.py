"""Candidates: list, add, edit, summary, script request, negotiation, delete."""
from urllib.parse import parse_qsl

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from sqlalchemy import update

from app import services
from app.extensions import db
from app.forms.candidate import CandidateForm, STEP_FIELDS
from app.forms.negotiation import NegotiationForm
from app.models import Candidate
from app.services import invalidate_dashboard_cache
from app.utils.timeutil import now_ist

bp = Blueprint("candidates", __name__, url_prefix="/candidates")


# ------------------------------------------------------------------- helpers
def _admin_required():
    if not current_user.is_admin:
        abort(403)


def _redirect_to_list(raw_qs: str):
    """Redirect to the list with its query string preserved.

    The string is parsed and rebuilt through url_for, so the target is always
    the candidates list (no open-redirect possible).
    """
    params = services.parse_list_params(dict(parse_qsl(raw_qs or "")))
    return redirect(url_for("candidates.list_view", **params.as_query()))


# ---------------------------------------------------------------------- list
SORT_OPTIONS = [
    ("created_at", "desc", "Newest first"),
    ("created_at", "asc", "Oldest first"),
    ("profitability", "desc", "Margin: high to low"),
    ("profitability", "asc", "Margin: low to high"),
    ("recommended", "desc", "Recommended offer: high to low"),
    ("expected_ctc", "desc", "Expected CTC: high to low"),
    ("urgency", "desc", "Client urgency: high first"),
    ("name", "asc", "Name: A to Z"),
]


@bp.route("/")
@login_required
def list_view():
    params = services.parse_list_params(request.args)
    page = services.paginate_candidates(params)
    ctx = dict(
        page=page, params=params,
        list_qs=_qs(params.as_query()),
        export_qs=_qs(params.filter_query()),
        departments=services.distinct_departments(),
        page_sizes=services.PAGE_SIZES,
        sort_options=SORT_OPTIONS,
        sort_match=any(k == params.sort and d == params.dir for k, d, _ in SORT_OPTIONS),
    )
    # Debounced search / filters / sort / paging fetch only the results block.
    if request.args.get("_partial") == "1":
        resp = current_app_response(render_template("candidates/_results.html", **ctx))
        return resp
    return render_template("candidates/list.html", **ctx)


def current_app_response(html: str):
    from flask import make_response
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _qs(data: dict) -> str:
    from urllib.parse import urlencode
    return urlencode(data)


# ------------------------------------------------------------------- summary
@bp.route("/<int:candidate_id>")
@login_required
def summary(candidate_id):
    services.sync_script_statuses_if_due()          # heal a status n8n forgot to set
    candidate = services.get_candidate_full(candidate_id)
    if candidate is None:
        abort(404)
    spider = services.build_spider_data(candidate.client, candidate.evaluation)
    return render_template("candidates/summary.html", c=candidate,
                           client=candidate.client, ev=candidate.evaluation,
                           spider=spider, leverage=services.leverage_index(spider["values"]),
                           script=services.latest_script(candidate),
                           negotiation=candidate.negotiation)


# --------------------------------------------------------------- quick view
@bp.route("/<int:candidate_id>/quick")
@login_required
def quick(candidate_id):
    """Fragment for the list page's fast-inspector drawer (loaded via fetch)."""
    candidate = services.get_candidate_full(candidate_id)
    if candidate is None:
        abort(404)
    spider = services.build_spider_data(candidate.client, candidate.evaluation)
    return render_template("candidates/_quick.html", c=candidate, client=candidate.client,
                           ev=candidate.evaluation, spider=spider,
                           leverage=services.leverage_index(spider["values"]))


# ----------------------------------------------------------------- add / edit
def _handle_form(candidate=None):
    editing = candidate is not None
    if request.method == "POST":
        form = CandidateForm()
        if form.validate_on_submit():
            try:
                saved = services.save_candidate(form, current_user, candidate)
            except Exception:  # noqa: BLE001 - logged, rolled back, user informed
                db.session.rollback()
                from flask import current_app
                current_app.logger.exception("Saving candidate failed")
                flash("Could not save the candidate. Please try again.", "danger")
                return render_template("candidates/form.html", form=form, candidate=candidate,
                                       editing=editing, start_step=len(STEP_FIELDS),
                                       STEP_FIELDS=STEP_FIELDS)
            flash(f"Candidate {saved.candidate_code} {'updated' if editing else 'created'} successfully.",
                  "success")
            return redirect(url_for("candidates.summary", candidate_id=saved.id))
        if form.csrf_token.errors:
            flash("Your session expired. Please review and save again.", "warning")
        start_step = form.first_error_step()
        if not any(form[n].errors for names in STEP_FIELDS.values() for n in names):
            start_step = len(STEP_FIELDS)
        return render_template("candidates/form.html", form=form, candidate=candidate,
                               editing=editing, start_step=start_step, STEP_FIELDS=STEP_FIELDS)

    if editing:
        form = CandidateForm(data=services.candidate_to_form_data(candidate))
    else:
        form = CandidateForm()
    return render_template("candidates/form.html", form=form, candidate=candidate,
                           editing=editing, start_step=1, STEP_FIELDS=STEP_FIELDS)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    return _handle_form()


@bp.route("/<int:candidate_id>/edit", methods=["GET", "POST"])
@login_required
def edit(candidate_id):
    candidate = services.get_candidate_full(candidate_id)
    if candidate is None:
        abort(404)
    return _handle_form(candidate)


# ------------------------------------------------------- script + negotiation
@bp.route("/<int:candidate_id>/script", methods=["POST"])
@login_required
def request_script(candidate_id):
    """Draft -> InProcess: ask n8n for the negotiation script.

    The workflow writes the two PDF links into ng_5 and sets the candidate to
    Generated. Until that happens the candidate stays InProcess.
    """
    candidate = services.get_candidate_full(candidate_id)
    if candidate is None:
        abort(404)
    try:
        services.request_script(candidate, user=current_user)
    except ValueError as exc:
        abort(400, description=str(exc))
    flash("Script requested. The candidate moves to InProcess until the PDFs arrive.",
          "success")
    return redirect(url_for("candidates.negotiation", candidate_id=candidate.id))


@bp.route("/<int:candidate_id>/negotiation", methods=["GET", "POST"])
@login_required
def negotiation(candidate_id):
    """The negotiation workspace: the generated script and the HR outcome."""
    services.sync_script_statuses()
    candidate = services.get_candidate_full(candidate_id)
    if candidate is None:
        abort(404)
    script = services.latest_script(candidate)
    record = candidate.negotiation
    closed = candidate.status == "Closed"

    if request.method == "POST":
        if closed:
            flash("This negotiation is already closed.", "warning")
            return redirect(url_for("candidates.negotiation", candidate_id=candidate.id))
        form = NegotiationForm()
        close = request.form.get("action") == "close"
        if form.validate_on_submit() and (not close or form.require_amounts()):
            services.save_negotiation(candidate, form, current_user, close=close)
            flash("Negotiation closed. The candidate is out of the open pipeline."
                  if close else "Negotiation saved.", "success")
            return redirect(url_for("candidates.negotiation", candidate_id=candidate.id))
    else:
        form = NegotiationForm(data={
            "offered_amount": record.offered_amount if record else None,
            "confirmed_ctc": record.confirmed_ctc if record else None,
            "negotiation_notes": record.negotiation_notes if record else None,
        })

    return render_template("candidates/negotiation.html", c=candidate,
                           client=candidate.client, ev=candidate.evaluation,
                           script=script, negotiation=record, form=form,
                           closed=closed)


# -------------------------------------------------------------------- delete
@bp.route("/<int:candidate_id>/delete", methods=["POST"])
@login_required
def delete(candidate_id):
    """Admin only: hidden in the UI for HR AND enforced here with 403."""
    _admin_required()
    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None:
        abort(404)
    code = candidate.candidate_code
    db.session.delete(candidate)   # ng_3/ng_4/ng_5/ng_6 rows go via ON DELETE CASCADE
    db.session.commit()
    invalidate_dashboard_cache()
    flash(f"Candidate {code} deleted.", "success")
    return _redirect_to_list(request.form.get("qs", ""))


# ------------------------------------------------------------ bulk: request
@bp.route("/bulk-script", methods=["POST"])
@login_required
def bulk_script():
    """Request the negotiation script for several selected candidates at once.

    This is the only bulk action: it moves Draft candidates to InProcess.
    The status is never set by hand, so there is no 'set to Closed' here -
    closing a negotiation always goes through the negotiation form.
    """
    try:
        ids = sorted({int(i) for i in request.form.getlist("ids")})
    except ValueError:
        abort(400, description="Invalid selection.")
    if not ids or len(ids) > 200:
        abort(400, description="Select between 1 and 200 candidates.")
    result = db.session.execute(
        update(Candidate)
        .where(Candidate.id.in_(ids), Candidate.status == "Draft")
        .values(status="InProcess", script_requested_at=now_ist(), updated_at=now_ist())
    )
    db.session.commit()
    invalidate_dashboard_cache()
    requested = result.rowcount or 0
    skipped = len(ids) - requested
    if skipped:
        flash(f"{requested} candidate(s) requested; {skipped} skipped (not Draft).", "warning")
    else:
        flash(f"{requested} candidate(s) moved to InProcess.", "success")
    return _redirect_to_list(request.form.get("qs", ""))
