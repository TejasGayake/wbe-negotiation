"""Business logic: reusable candidates query, profitability, candidate codes,
spider-chart data and the create/update transaction.

Everything that must behave identically for the list page, the dashboard and
the Excel export lives here (build_candidates_query is the single source).
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Optional

from flask import current_app
from sqlalchemy import Select, and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload

from app import mappings
from app.extensions import cache, db
from app.models import (Assessment, Candidate, CandidateEvaluation, ClientDetail,
                        Negotiation, NegotiationResult)
from app.utils.timeutil import now_ist

# ---------------------------------------------------------------------------
# Profitability
# ---------------------------------------------------------------------------
TWO_PLACES = Decimal("0.01")


def calculate_profitability(client_budget, expected_ctc) -> Optional[Decimal]:
    """((client_budget - expected_ctc) / client_budget) * 100, Decimal, 2 dp.

    Returns None when it cannot be computed (missing values or budget <= 0).
    """
    try:
        budget = Decimal(str(client_budget)) if client_budget is not None else None
        expected = Decimal(str(expected_ctc)) if expected_ctc is not None else None
    except InvalidOperation:
        return None
    if budget is None or expected is None or budget <= 0:
        return None
    pct = (budget - expected) / budget * Decimal(100)
    return pct.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Candidate code: WBE-YYYY-XXXX
# ---------------------------------------------------------------------------
def generate_candidate_code() -> str:
    """Next code for the current IST year (resets every year).

    Must be called inside the transaction that inserts the candidate. A locking
    read (FOR UPDATE) serialises concurrent creators on MySQL; the caller also
    retries on a unique-constraint conflict.
    """
    year = now_ist().year
    prefix = f"WBE-{year}-"
    last = db.session.execute(
        select(Candidate.candidate_code)
        .where(Candidate.candidate_code.like(prefix + "%"))
        # length first so 5-digit sequences sort after 4-digit ones
        .order_by(func.length(Candidate.candidate_code).desc(),
                  Candidate.candidate_code.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    seq = 1
    if last:
        try:
            seq = int(last.rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:04d}"


# ---------------------------------------------------------------------------
# Spider chart (server-side data for Chart.js radar)
# ---------------------------------------------------------------------------
SPIDER_LABELS = [
    "Client Urgency", "Skill Scarcity", "Availability of Talent",
    "Risk of Losing Candidate", "Client Flexibility", "On Bench",
]

# Plain-English meaning of each axis, positionally aligned with SPIDER_LABELS.
# Read alongside the limit-index score: a high score always means "more leverage
# for the candidate", even where the underlying rating reads the other way.
SPIDER_NOTES = [
    "How pressed the client is to fill the role. Higher = the client needs someone sooner, which strengthens the candidate's hand.",
    "How hard the required skill is to find in the market. Higher = the client has fewer alternatives.",
    "How many other suitable candidates are on the market. Higher = the client has more alternatives, which weakens the candidate's position.",
    "How likely the candidate is to walk away. Higher = more pressure to agree terms.",
    "How open the client is to adjusting budget or role scope.",
    "How long the candidate has been without work. Higher = more pressure to accept an offer.",
]


def _tri_to_score(value) -> int:
    """-1 / 0 / 1 -> 0 / 50 / 100 (None -> 0)."""
    if value is None:
        return 0
    return {-1: 0, 0: 50, 1: 100}.get(int(value), 0)


def build_spider_data(client: Optional[ClientDetail],
                      evaluation: Optional[CandidateEvaluation]) -> dict:
    """Return {'labels': [...], 'values': [...], 'notes': [...]} scaled 0..100."""
    client_urgency = getattr(client, "client_urgency", None)
    skill_scarcity = getattr(client, "skill_scarcity", None)
    availability = getattr(client, "availability_of_talent", None)
    flexibility = getattr(client, "client_flexibility", None)
    risk = getattr(evaluation, "risk_of_losing_candidate", None)
    on_bench = getattr(evaluation, "is_on_bench", None)
    bench_months = getattr(evaluation, "bench_months", None)

    flex_score = 100 if flexibility == 1 else 0
    if on_bench == 1 and bench_months is not None:
        bench_score = min(float(bench_months) / 6.0, 1.0) * 100
    else:
        bench_score = 0

    values = [
        _tri_to_score(client_urgency),
        _tri_to_score(skill_scarcity),
        _tri_to_score(availability),
        _tri_to_score(risk),
        flex_score,
        round(bench_score, 1),
    ]
    return {"labels": SPIDER_LABELS, "values": values, "notes": SPIDER_NOTES}


# ---------------------------------------------------------------------------
# Reusable candidates query (list page + Excel export)
# ---------------------------------------------------------------------------
SORT_COLUMNS = {
    "code": Candidate.candidate_code,
    "name": Candidate.full_name,
    "position": Candidate.position_applied_for,
    "department": Candidate.department,
    "client": ClientDetail.client_name,
    "status": Candidate.status,
    "profitability": CandidateEvaluation.profitability_percentage,
    "created_at": Candidate.created_at,
    "current_ctc": CandidateEvaluation.current_ctc,
    "expected_ctc": CandidateEvaluation.expected_ctc,
    "budget": ClientDetail.client_budget,
    "recommended": CandidateEvaluation.recommended_offer,
    "urgency": ClientDetail.client_urgency,
}
DEFAULT_SORT = "created_at"
DEFAULT_DIR = "desc"
PAGE_SIZES = (10, 20, 50)
DEFAULT_PAGE_SIZE = 20


@dataclass
class ListParams:
    """Normalised list/export parameters (all come from the query string)."""
    q: str = ""
    sort: str = DEFAULT_SORT
    dir: str = DEFAULT_DIR
    status: str = ""
    department: str = ""
    urgency: Optional[int] = None
    scarcity: Optional[int] = None
    profit: str = ""          # '', 'positive', 'negative'
    page: int = 1
    per_page: int = DEFAULT_PAGE_SIZE

    def as_query(self, **overrides) -> dict:
        """Non-default params as a dict for url_for / links (omits blanks)."""
        data = {
            "q": self.q, "sort": self.sort, "dir": self.dir,
            "status": self.status, "department": self.department,
            "urgency": "" if self.urgency is None else self.urgency,
            "scarcity": "" if self.scarcity is None else self.scarcity,
            "profit": self.profit, "page": self.page, "per_page": self.per_page,
        }
        data.update(overrides)
        return {k: v for k, v in data.items() if v not in ("", None)}

    def filter_query(self) -> dict:
        """Search + filters + sort only (no paging) - used by the export link."""
        q = self.as_query()
        q.pop("page", None)
        q.pop("per_page", None)
        return q


def _opt_int(raw, allowed) -> Optional[int]:
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return None
    return val if val in allowed else None


def parse_list_params(args) -> ListParams:
    """Validate/normalise request.args. Unknown values fall back to defaults."""
    p = ListParams()
    p.q = (args.get("q") or "").strip()[:100]
    sort = args.get("sort", DEFAULT_SORT)
    p.sort = sort if sort in SORT_COLUMNS else DEFAULT_SORT
    p.dir = "asc" if args.get("dir") == "asc" else "desc"
    if "sort" not in args:
        p.dir = DEFAULT_DIR
    status = args.get("status", "")
    p.status = status if status in mappings.STATUS_CHOICES else ""
    p.department = (args.get("department") or "").strip()[:100]
    p.urgency = _opt_int(args.get("urgency"), mappings.valid_values("client_urgency"))
    p.scarcity = _opt_int(args.get("scarcity"), mappings.valid_values("skill_scarcity"))
    profit = args.get("profit", "")
    p.profit = profit if profit in ("positive", "negative") else ""
    try:
        p.page = max(int(args.get("page", 1)), 1)
    except (TypeError, ValueError):
        p.page = 1
    try:
        per_page = int(args.get("per_page", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PAGE_SIZE
    p.per_page = per_page if per_page in PAGE_SIZES else DEFAULT_PAGE_SIZE
    return p


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _joined(stmt: Select) -> Select:
    return (
        stmt.select_from(Candidate)
        .outerjoin(ClientDetail, ClientDetail.candidate_id == Candidate.id)
        .outerjoin(CandidateEvaluation, CandidateEvaluation.candidate_id == Candidate.id)
    )


def _apply_filters(stmt: Select, params: ListParams) -> Select:
    """Search + filters (AND logic). Shared by the data query and the count.

    A closed negotiation stays in the database but is hidden from the
    candidate tables until it is explicitly selected (status=Closed).
    """
    if params.q:
        like = f"%{_escape_like(params.q)}%"
        stmt = stmt.where(or_(
            Candidate.full_name.ilike(like, escape="\\"),
            Candidate.candidate_code.ilike(like, escape="\\"),
            Candidate.position_applied_for.ilike(like, escape="\\"),
            ClientDetail.client_name.ilike(like, escape="\\"),
        ))
    if params.status:
        stmt = stmt.where(Candidate.status == params.status)
    else:
        stmt = stmt.where(Candidate.status != "Closed")
    if params.department:
        stmt = stmt.where(Candidate.department == params.department)
    if params.urgency is not None:
        stmt = stmt.where(ClientDetail.client_urgency == params.urgency)
    if params.scarcity is not None:
        stmt = stmt.where(ClientDetail.skill_scarcity == params.scarcity)
    if params.profit == "positive":
        stmt = stmt.where(CandidateEvaluation.profitability_percentage > 0)
    elif params.profit == "negative":
        stmt = stmt.where(CandidateEvaluation.profitability_percentage < 0)
    return stmt


def build_candidates_query(params: ListParams, *, defer_text: bool = True) -> Select:
    """THE reusable query for the list page and the Excel export.

    * One SELECT joins ng_2 + ng_3 + ng_4 (no N+1). contains_eager reuses the
      very join that search/filter/sort need, so the client/evaluation rows are
      loaded eagerly without a second joinedload JOIN.
    * defer_text=True defers the TEXT columns (list page never shows them).
    * Pagination (LIMIT/OFFSET) is applied by the caller in SQL.
    """
    client_load = contains_eager(Candidate.client)
    eval_load = contains_eager(Candidate.evaluation)
    if defer_text:
        client_load = client_load.defer(ClientDetail.notes_from_client)
        eval_load = (eval_load.defer(CandidateEvaluation.notes)
                     .defer(CandidateEvaluation.key_strengths)
                     .defer(CandidateEvaluation.key_concerns))

    stmt = _apply_filters(_joined(select(Candidate)), params).options(client_load, eval_load)

    col = SORT_COLUMNS[params.sort]
    order = col.asc() if params.dir == "asc" else col.desc()
    # Stable tiebreaker keeps LIMIT/OFFSET pagination deterministic.
    return stmt.order_by(order, Candidate.id.desc())


@dataclass
class Page:
    """One page of list results plus the aggregate KPI summary of the whole filtered set."""
    items: list
    page: int
    per_page: int
    total: int
    summary: dict = field(default_factory=dict)
    pages: int = 1

    def __post_init__(self):
        self.pages = max(math.ceil(self.total / self.per_page), 1) if self.per_page else 1

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def first_item(self) -> int:
        return 0 if self.total == 0 else (self.page - 1) * self.per_page + 1

    @property
    def last_item(self) -> int:
        return min(self.page * self.per_page, self.total)

    def window(self, radius: int = 2) -> list:
        """Page numbers to show, with None marking an ellipsis."""
        nums = sorted({1, self.pages, *range(max(1, self.page - radius), min(self.pages, self.page + radius) + 1)})
        out, prev = [], None
        for n in nums:
            if prev is not None and n - prev > 1:
                out.append(None)
            out.append(n)
            prev = n
        return out


def list_summary(params: ListParams) -> dict:
    """ONE aggregate query for the filtered set: total + KPI figures.

    Replaces the plain COUNT, so the list page still issues a constant number
    of queries while the KPI cards always describe the current search/filters.
    """
    profit = CandidateEvaluation.profitability_percentage
    stmt = _apply_filters(_joined(select(
        func.count(Candidate.id),
        func.avg(profit),
        func.coalesce(func.sum(case((profit < 0, 1), else_=0)), 0),
        func.coalesce(func.sum(case((ClientDetail.client_urgency == 1, 1), else_=0)), 0),
    )), params)
    total, avg, negative, urgent = db.session.execute(stmt).one()
    return {
        "total": int(total or 0),
        "avg_profitability": _q2(avg),
        "negative": int(negative or 0),
        "urgent": int(urgent or 0),
    }


def _q2(value) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def paginate_candidates(params: ListParams) -> Page:
    """SQL-level pagination: one aggregate + one LIMIT/OFFSET query."""
    summary = list_summary(params)
    total = summary["total"]
    pages = max(math.ceil(total / params.per_page), 1)
    page = min(params.page, pages)
    params.page = page
    stmt = build_candidates_query(params).limit(params.per_page).offset((page - 1) * params.per_page)
    items = db.session.execute(stmt).scalars().all()
    return Page(items=items, page=page, per_page=params.per_page, total=total, summary=summary)


def distinct_departments() -> list[str]:
    rows = db.session.execute(
        select(Candidate.department).where(Candidate.department.is_not(None))
        .distinct().order_by(Candidate.department)
    ).scalars().all()
    return [r for r in rows if r]


def get_candidate_full(candidate_id: int) -> Optional[Candidate]:
    """Candidate with client + evaluation + creator in a single query."""
    return db.session.execute(
        select(Candidate)
        .options(joinedload(Candidate.client), joinedload(Candidate.evaluation),
                 joinedload(Candidate.creator))
        .where(Candidate.id == candidate_id)
    ).unique().scalar_one_or_none()


# ---------------------------------------------------------------------------
# Dashboard stats: ONE grouped aggregate query
# ---------------------------------------------------------------------------
def dashboard_stats() -> dict:
    """Status counts, average profitability and pipeline money from ONE grouped query.

    Everything (counts per status, profitability sum/count for a correct overall
    average, pipeline budget/expected, 'this month', negative and urgent counts)
    comes from a single GROUP BY status statement.
    """
    profit = CandidateEvaluation.profitability_percentage
    both = and_(ClientDetail.client_budget.is_not(None),
                CandidateEvaluation.expected_ctc.is_not(None))
    month_start = now_ist().replace(day=1, hour=0, minute=0, second=0)
    rows = db.session.execute(
        select(
            Candidate.status,
            func.count(Candidate.id),
            func.coalesce(func.sum(profit), 0),
            func.count(profit),                                         # COUNT(col) ignores NULLs
            func.coalesce(func.sum(case((both, ClientDetail.client_budget), else_=0)), 0),
            func.coalesce(func.sum(case((both, CandidateEvaluation.expected_ctc), else_=0)), 0),
            func.coalesce(func.sum(case((Candidate.created_at >= month_start, 1), else_=0)), 0),
            func.coalesce(func.sum(case((profit < 0, 1), else_=0)), 0),
            func.coalesce(func.sum(case((ClientDetail.client_urgency == 1, 1), else_=0)), 0),
        )
        .select_from(Candidate)
        .outerjoin(ClientDetail, ClientDetail.candidate_id == Candidate.id)
        .outerjoin(CandidateEvaluation, CandidateEvaluation.candidate_id == Candidate.id)
        .group_by(Candidate.status)
    ).all()

    counts = {s_: 0 for s_ in mappings.STATUS_CHOICES}
    total = profit_n = new_month = attention = urgent = 0
    profit_sum = pipe_budget = pipe_expected = Decimal(0)
    for status, n, p_sum, p_n, budget, expected, month, neg, urg in rows:
        counts[status] = n
        total += n
        profit_sum += Decimal(str(p_sum))
        profit_n += p_n
        if status != "Closed":                       # open pipeline only
            pipe_budget += Decimal(str(budget))
            pipe_expected += Decimal(str(expected))
            attention += int(neg)
            urgent += int(urg)
            new_month += int(month)
    avg = _q2(profit_sum / profit_n) if profit_n else None
    return {
        "total": total, "counts": counts, "avg_profitability": avg,
        "open_total": total - counts["Closed"],
        "new_this_month": new_month, "attention": attention, "urgent": urgent,
        "pipeline_budget": pipe_budget, "pipeline_expected": pipe_expected,
        "pipeline_margin": pipe_budget - pipe_expected,
    }


def _dashboard_row(c: Candidate) -> dict:
    """Plain, cacheable row for the dashboard tables (never an ORM instance)."""
    ev, cl = c.evaluation, c.client
    return {
        "id": c.id,
        "full_name": c.full_name,
        "position_applied_for": c.position_applied_for,
        "candidate_code": c.candidate_code,
        "status": c.status,
        "client_name": cl.client_name if cl else None,
        "expected_ctc": ev.expected_ctc if ev else None,
        "recommended_offer": ev.recommended_offer if ev else None,
        "profitability_percentage": ev.profitability_percentage if ev else None,
    }


def get_dashboard_data(view: str = "all") -> dict:
    """Dashboard data, cached per tab.

    Only plain values are cached: the rows are flattened dicts, so a cache
    backend that serialises (Redis) or a later request whose session is gone
    cannot hit a detached ORM instance. Cache is dropped by
    invalidate_dashboard_cache() whenever a write changes the pipeline.

    Returns dict with keys: stats, recent, attention, spread
    """
    cache_key = f"dashboard_data:{view}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {
        "stats": dashboard_stats(),
        "spread": margin_by(ClientDetail.client_name, 5),
        "recent": [_dashboard_row(c) for c in recent_candidates(6, view)],
        "attention": [_dashboard_row(c) for c in attention_candidates(4)],
    }

    cache.set(cache_key, result)
    return result


def invalidate_dashboard_cache() -> None:
    """Invalidate all dashboard cache entries.
    
    Call this after candidate create/edit/delete to ensure fresh data.
    """
    for view in DASHBOARD_VIEWS:
        cache.delete(f"dashboard_data:{view}")
    # Also invalidate the attention feed cache
    cache.delete("attention_feed")


def _list_options():
    return (
        contains_eager(Candidate.client).defer(ClientDetail.notes_from_client),
        contains_eager(Candidate.evaluation)
        .defer(CandidateEvaluation.notes)
        .defer(CandidateEvaluation.key_strengths)
        .defer(CandidateEvaluation.key_concerns),
    )


DASHBOARD_VIEWS = ("all", "attention", "urgent", "generated")


def recent_candidates(limit: int = 6, view: str = "all") -> list[Candidate]:
    """Latest candidates for the dashboard table, optionally narrowed by a tab.

    Closed negotiations are not shown: they live in the negotiation register.
    """
    profit = CandidateEvaluation.profitability_percentage
    stmt = _joined(select(Candidate)).options(*_list_options())
    if view == "attention":
        stmt = stmt.where(profit < 0, Candidate.status != "Closed")
    elif view == "urgent":
        stmt = stmt.where(ClientDetail.client_urgency == 1, Candidate.status != "Closed")
    elif view == "generated":
        stmt = stmt.where(Candidate.status == "Generated")
    else:
        stmt = stmt.where(Candidate.status != "Closed")
    stmt = stmt.order_by(Candidate.created_at.desc(), Candidate.id.desc()).limit(limit)
    return db.session.execute(stmt).scalars().all()


def attention_candidates(limit: int = 5, only_negative: bool = False) -> list[Candidate]:
    """Open candidates that need action: negative margin, or high urgency + high risk."""
    profit = CandidateEvaluation.profitability_percentage
    cond = profit < 0 if only_negative else or_(
        profit < 0,
        and_(ClientDetail.client_urgency == 1,
             CandidateEvaluation.risk_of_losing_candidate == 1),
    )
    stmt = (
        _joined(select(Candidate)).options(*_list_options())
        .where(Candidate.status != "Closed", cond)
        .order_by(profit.is_(None), profit.asc(), Candidate.id.desc())
        .limit(limit)
    )
    return db.session.execute(stmt).scalars().all()


def attention_count() -> int:
    profit = CandidateEvaluation.profitability_percentage
    stmt = _joined(select(func.count(Candidate.id))).where(
        Candidate.status != "Closed",
        or_(profit < 0, and_(ClientDetail.client_urgency == 1,
                             CandidateEvaluation.risk_of_losing_candidate == 1)))
    return int(db.session.execute(stmt).scalar_one())


def margin_by(column, limit: int = 6) -> list[dict]:
    """Average margin + headcount grouped by a column (client name / department).

    Closed negotiations are excluded: this widget describes the live pipeline.
    """
    profit = CandidateEvaluation.profitability_percentage
    rows = db.session.execute(
        _joined(select(column, func.count(Candidate.id), func.avg(profit)))
        .where(column.is_not(None), Candidate.status != "Closed")
        .group_by(column)
        .order_by(func.count(Candidate.id).desc(), func.avg(profit).desc())
        .limit(limit)
    ).all()
    return [{"name": name, "count": int(n), "avg": _q2(avg)} for name, n, avg in rows]


def distribution(column) -> dict:
    """{value: count} for a TINYINT column of ng_3 / ng_4 (open + closed)."""
    rows = db.session.execute(
        _joined(select(column, func.count(Candidate.id))).group_by(column)
    ).all()
    return {(-9 if v is None else int(v)): int(n) for v, n in rows}


# ---------------------------------------------------------------------------
# Derived display metrics (no extra storage)
# ---------------------------------------------------------------------------
def leverage_index(values: list) -> float:
    """Average of the six radar axes (0-100), shown as x / 10."""
    return round(sum(values) / len(values) / 10.0, 1) if values else 0.0


def margin_tier(profit, target) -> tuple[str, str]:
    """(label, badge-class) for a profitability value against the target margin."""
    if profit is None:
        return "N/A", "badge-muted"
    profit, target = Decimal(str(profit)), Decimal(str(target))
    if profit >= target:
        return "Healthy", "badge-success"
    if profit > 0:
        return "Below target", "badge-warning"
    if profit == 0:
        return "Break-even", "badge-warning"
    return "Deficit", "badge-danger"


def hike_pct(new, current) -> Optional[Decimal]:
    """% change from current CTC to a new figure."""
    try:
        new, current = Decimal(str(new)), Decimal(str(current))
    except Exception:
        return None
    if current <= 0:
        return None
    return ((new - current) / current * Decimal(100)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Negotiation workflow: Draft -> InProcess -> Generated -> Closed
#
# The status is driven by the workflow, never chosen by hand.
#   Draft      the wizard is capturing the data
#   InProcess the script was requested; n8n is generating it
#   Generated  the script exists - the two PDF links are in ng_5
#   Closed     HR recorded the outcome and closed the negotiation (ng_6)
#
# n8n writes ng_5 (and, in the same transaction, the status). The rule
# "Generated only once a link exists" is enforced by sync_script_statuses(),
# which heals a candidate whose links arrived but whose status did not.
# ---------------------------------------------------------------------------
def _as_float(value) -> Optional[float]:
    """Decimal/Numeric -> float for JSON. None stays None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, InvalidOperation, ValueError):
        return None


def script_payload(candidate) -> dict:
    """The webhook body for the n8n script workflow.

    Keys line up with 'Memory - Locked Values', which matches case- and
    punctuation-insensitively but throws when Current_CTC or
    Maximum_Approved_Offer is missing or zero. The same checks run here so HR
    gets a readable error instead of an orphaned InProcess candidate.

    relocation_required is sent as Yes/No: the workflow compares the literal
    string, so a raw TINYINT 1 would silently read as No.
    """
    detail = candidate.evaluation
    client = candidate.client
    assessment = candidate.assessment
    if not (candidate.cv_drive_link or "").strip():
        raise ValueError(
            "This candidate has no CV Drive link on file. Add one before "
            "requesting a script.")
    current_ctc = _as_float(getattr(detail, "current_ctc", None))
    ceiling = _as_float(getattr(detail, "maximum_approved_offer", None))
    if not current_ctc:
        raise ValueError("Current CTC is required before a script can be written.")
    if not ceiling:
        raise ValueError(
            "Maximum approved offer is required before a script can be written.")

    def label(field: str, value):
        """TINYINT -> the label the assessment sheet uses (Yes/No, High/...)."""
        if value is None:
            return None
        text = mappings.to_label(field, value, empty="")
        return text or None

    def num(value):
        return _as_float(value)

    return {
        # --- Section A: candidate identity -------------------------------
        # candidate_id is the numeric ng_2_candidates.id the N8NHIRING push
        # created (lastrowid); that is the key both systems share. The
        # human-readable code rides along as candidate_code.
        "candidate_id": candidate.id,
        "candidate_code": candidate.candidate_code,
        "candidate_name": candidate.full_name,
        "position_applied_for": candidate.position_applied_for,
        "department": candidate.department,
        "total_years_experience": num(candidate.total_years_experience),
        "relevant_years_experience": num(candidate.relevant_years_experience),
        "current_company": candidate.current_company,
        "current_designation": candidate.current_designation,
        "notice_period": candidate.notice_period,
        "notice_negotiable": label("notice_negotiable", candidate.notice_negotiable),
        "current_location": candidate.current_location,
        "proposed_work_location": candidate.proposed_work_location,
        "relocation_required": "Yes" if candidate.relocation_required else "No",
        "primary_motivation": candidate.primary_motivation,
        "cv_drive_link": candidate.cv_drive_link.strip(),
        "driveFolderId": current_app.config.get("N8N_DRIVE_FOLDER_ID", ""),

        # --- Section B: current compensation ----------------------------
        "current_ctc": current_ctc,
        "current_fixed_ctc": num(getattr(detail, "current_fixed_ctc", None)),
        "current_variable_bonus": num(getattr(detail, "current_variable_bonus", None)),
        "expected_ctc": num(getattr(detail, "expected_ctc", None)),
        "percentage_hike_expected": getattr(detail, "percentage_hike_expected", None),
        "has_another_offer": label("has_another_offer", getattr(detail, "has_another_offer", None)),
        "competing_offer_ctc": num(getattr(detail, "competing_offer_ctc", None)),
        "other_offers_discussion": getattr(detail, "other_offers_discussion", None),
        "profitability_percentage": num(getattr(detail, "profitability_percentage", None)),

        # --- Section D: capability --------------------------------------
        "technical_skills_rating": getattr(detail, "technical_skills_rating", None),
        "domain_knowledge_rating": getattr(detail, "domain_knowledge_rating", None),
        "communication_rating": getattr(detail, "communication_rating", None),
        "average_capability_rating": num(getattr(detail, "average_capability_rating", None)),
        "overall_candidate_potential": getattr(detail, "overall_candidate_potential", None),

        # --- Section E: market ------------------------------------------
        "estimated_market_ctc": num(getattr(detail, "estimated_market_ctc", None)),
        "company_band_min": num(getattr(detail, "company_band_min", None)),
        "company_band_target": num(getattr(detail, "company_band_target", None)),
        "company_band_max": num(getattr(detail, "company_band_max", None)),
        "skill_scarcity": label("skill_scarcity", getattr(client, "skill_scarcity", None)),
        "availability_of_talent": label("availability_of_talent",
                                        getattr(client, "availability_of_talent", None)),

        # --- Section I: negotiation position ----------------------------
        "recommended_offer": num(getattr(detail, "recommended_offer", None)),
        "maximum_approved_offer": ceiling,
        "minimum_acceptable_offer_candidate": num(
            getattr(detail, "minimum_acceptable_offer_candidate", None)),
        "hr_estimated_fair_compensation": num(
            getattr(detail, "hr_estimated_fair_compensation", None)),

        # --- Section J: hiring risk -------------------------------------
        "risk_of_losing_candidate": label("risk_of_losing_candidate",
                                          getattr(detail, "risk_of_losing_candidate", None)),
        "risk_compensation_expectation": getattr(detail, "risk_compensation_expectation", None),
        "risk_counter_offer": getattr(detail, "risk_counter_offer", None),
        "risk_relocation": getattr(detail, "risk_relocation", None),
        "risk_retention": getattr(detail, "risk_retention", None),
        "risk_skill_capability": getattr(detail, "risk_skill_capability", None),
        "risk_cultural_fit": getattr(detail, "risk_cultural_fit", None),
        "risk_notice_period": getattr(detail, "risk_notice_period", None),
        "risk_early_attrition": getattr(detail, "risk_early_attrition", None),
        "average_risk_score": num(getattr(detail, "average_risk_score", None)),
        "overall_hiring_risk": getattr(detail, "overall_hiring_risk", None),

        # --- Section K: classification ----------------------------------
        "candidate_classification": getattr(detail, "candidate_classification", None),

        # --- Internal / app-only ----------------------------------------
        "is_on_bench": label("is_on_bench", getattr(detail, "is_on_bench", None)),
        "bench_months": num(getattr(detail, "bench_months", None)),
        "is_client_selected_candidate": label(
            "is_client_selected_candidate",
            getattr(detail, "is_client_selected_candidate", None)),
        "want_to_switch_domain": label("want_to_switch_domain",
                                       getattr(detail, "want_to_switch_domain", None)),
        "technical_gate_status": label("technical_gate_status",
                                       getattr(detail, "technical_gate_status", None)),
        "company_upgradation": label("company_upgradation",
                                     getattr(detail, "company_upgradation", None)),
        "position_upgradation": label("position_upgradation",
                                      getattr(detail, "position_upgradation", None)),
        "key_strengths": getattr(detail, "key_strengths", None),
        "key_concerns": getattr(detail, "key_concerns", None),
        "notes": getattr(detail, "notes", None),

        # --- Client brief (ng_3) ----------------------------------------
        "client_name": getattr(client, "client_name", None),
        "client_budget": num(getattr(client, "client_budget", None)),
        "client_timeline_days": getattr(client, "client_timeline_days", None),
        "client_urgency": label("client_urgency", getattr(client, "client_urgency", None)),
        "client_flexibility": label("client_flexibility",
                                    getattr(client, "client_flexibility", None)),
        "skill_required": getattr(client, "skill_required", None),
        "position_for_client": getattr(client, "position_for_client", None),
        "client_location": getattr(client, "client_location", None),
        "replacement_hiring": label("replacement_hiring",
                                    getattr(client, "replacement_hiring", None)),
        "notes_from_client": getattr(client, "notes_from_client", None),

        # --- Sections A-L extension (ng_7) ------------------------------
        "other_benefits": getattr(assessment, "other_benefits", None),
        "proposed_designation": getattr(assessment, "proposed_designation", None),
        "proposed_role_level": getattr(assessment, "proposed_role_level", None),
        "key_additional_responsibilities": getattr(
            assessment, "key_additional_responsibilities", None),
        "expected_business_impact": getattr(
            assessment, "expected_business_impact", None),
        "significant_career_growth": getattr(
            assessment, "significant_career_growth", None),
        "expected_vs_market": getattr(assessment, "expected_vs_market", None),
        "relocation_influence_compensation": getattr(
            assessment, "relocation_influence_compensation", None),
        "can_offer_relocation_support": getattr(
            assessment, "can_offer_relocation_support", None),
        "current_org_type": getattr(assessment, "current_org_type", None),
        "proposed_org_type": getattr(assessment, "proposed_org_type", None),
        "significant_career_transition": getattr(
            assessment, "significant_career_transition", None),
        "major_career_benefits": getattr(assessment, "major_career_benefits", None),
        "motivation_salary_rank": getattr(assessment, "motivation_salary_rank", None),
        "motivation_career_growth_rank": getattr(
            assessment, "motivation_career_growth_rank", None),
        "motivation_designation_rank": getattr(
            assessment, "motivation_designation_rank", None),
        "motivation_role_responsibility_rank": getattr(
            assessment, "motivation_role_responsibility_rank", None),
        "motivation_company_brand_rank": getattr(
            assessment, "motivation_company_brand_rank", None),
        "motivation_oem_exposure_rank": getattr(
            assessment, "motivation_oem_exposure_rank", None),
        "motivation_location_rank": getattr(
            assessment, "motivation_location_rank", None),
        "motivation_work_environment_rank": getattr(
            assessment, "motivation_work_environment_rank", None),
        "motivation_technology_learning_rank": getattr(
            assessment, "motivation_technology_learning_rank", None),
        "motivation_international_exposure_rank": getattr(
            assessment, "motivation_international_exposure_rank", None),
        "motivation_other_rank": getattr(
            assessment, "motivation_other_rank", None),
        "candidate_negotiation_power": getattr(
            assessment, "candidate_negotiation_power", None),
        "company_negotiation_power": getattr(
            assessment, "company_negotiation_power", None),
        "recommended_action": getattr(assessment, "recommended_action", None),
        "key_reason_recommended_compensation": getattr(
            assessment, "key_reason_recommended_compensation", None),
        "alternatives_to_ctc": getattr(assessment, "alternatives_to_ctc", None),
    }


def _post_script_request(payload: dict) -> None:
    """POST the payload to the n8n webhook. Raises ValueError on failure."""
    url = (current_app.config.get("N8N_SCRIPT_WEBHOOK_URL") or "").strip()
    if not url:
        raise ValueError(
            "N8N_SCRIPT_WEBHOOK_URL is not configured; the script cannot be "
            "requested.")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    timeout = int(current_app.config.get("N8N_WEBHOOK_TIMEOUT", 15))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1)
    except (urllib.error.URLError, OSError) as exc:
        raise ValueError(f"The script workflow could not be reached: {exc}") from exc


def request_script(candidate, user=None) -> None:
    """Draft -> InProcess: ask for the negotiation script.

    Creates the ng_5 row that the workflow fills in, then POSTs the payload.
    n8n updates that row by id and, on a generation failure, puts the
    candidate back to Draft. If the POST itself fails nothing was generated,
    so the status and the ng_5 row are rolled back here as well.
    """
    if candidate.status not in ("Draft", "InProcess"):
        raise ValueError(
            "A script can only be requested before the script exists "
            "and before the negotiation is closed.")
    payload = script_payload(candidate)

    result = NegotiationResult(
        candidate_id=candidate.id,
        generated_by=getattr(user, "id", None),
        input_data_json=json.dumps(payload, ensure_ascii=False),
    )
    db.session.add(result)

    previous_status = candidate.status
    previous_requested_at = candidate.script_requested_at
    candidate.status = "InProcess"
    candidate.script_requested_at = now_ist()
    candidate.updated_at = now_ist()
    db.session.commit()
    invalidate_dashboard_cache()

    payload["ng5_id"] = result.id
    try:
        _post_script_request(payload)
    except ValueError:
        candidate.status = previous_status
        candidate.script_requested_at = previous_requested_at
        candidate.updated_at = now_ist()
        db.session.delete(result)
        db.session.commit()
        invalidate_dashboard_cache()
        raise


def sync_script_statuses() -> int:
    """Flip InProcess -> Generated for candidates whose script links exist.

    n8n writes the links and the status together; this repairs the case where
    the links landed but the status update did not. One statement, no N+1.
    """
    ready = select(NegotiationResult.candidate_id).where(
        NegotiationResult.full_playbook_pdf_path.is_not(None))
    result = db.session.execute(
        update(Candidate)
        .where(Candidate.status == "InProcess")
        .where(Candidate.id.in_(ready))
        .values(status="Generated", updated_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount:
        db.session.commit()
        invalidate_dashboard_cache()
    return result.rowcount


def sync_script_statuses_if_due(interval: int = 60) -> None:
    """Run the heal at most once per interval instead of on every page view."""
    if cache.get("script_status_sync_due") is not None:
        return
    cache.set("script_status_sync_due", 1, timeout=interval)
    sync_script_statuses()


def latest_script(candidate) -> Optional[NegotiationResult]:
    """The newest script generation record (ng_5) of one candidate."""
    return db.session.execute(
        select(NegotiationResult)
        .where(NegotiationResult.candidate_id == candidate.id)
        .order_by(NegotiationResult.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_scripts(candidate_ids) -> dict:
    """{candidate_id: newest ng_5 row} for many candidates in ONE query."""
    ids = list(candidate_ids)
    if not ids:
        return {}
    rows = db.session.execute(
        select(NegotiationResult)
        .where(NegotiationResult.candidate_id.in_(ids))
        .order_by(NegotiationResult.candidate_id, NegotiationResult.id.desc())
    ).scalars().all()
    out = {}
    for row in rows:
        out.setdefault(row.candidate_id, row)   # ordered newest first per candidate
    return out


def save_negotiation(candidate, form, user, *, close: bool = False) -> Negotiation:
    """Record the HR negotiation outcome (ng_6). close=True also closes it.

    Saving without closing keeps the candidate in its current stage, so HR can
    note the offer and come back to it.
    """
    negotiation = candidate.negotiation or Negotiation()
    candidate.negotiation = negotiation
    negotiation.offered_amount = form.offered_amount.data
    negotiation.confirmed_ctc = form.confirmed_ctc.data
    negotiation.negotiation_notes = _clean(form.negotiation_notes.data)
    if close:
        negotiation.closed_by = user.id
        negotiation.closed_at = now_ist()
        candidate.status = "Closed"
        candidate.updated_at = now_ist()
    db.session.add(negotiation)
    db.session.commit()
    invalidate_dashboard_cache()
    return negotiation


NEGOTIATION_ROW_LIMIT = 200


def negotiation_rows(stage: str = "all", q: str = "") -> tuple[list, int]:
    """The negotiation register: candidates in the negotiation stage.

    Returns (rows, total). stage is 'open' (script ready or a negotiation in
    progress), 'closed' or 'all'.
    """
    stmt = (
        select(Candidate)
        .outerjoin(ClientDetail, ClientDetail.candidate_id == Candidate.id)
        .outerjoin(Negotiation, Negotiation.candidate_id == Candidate.id)
        .options(contains_eager(Candidate.client), contains_eager(Candidate.negotiation))
    )
    if stage == "closed":
        stmt = stmt.where(Candidate.status == "Closed")
    else:
        stmt = stmt.where(or_(
            Candidate.status.in_(("Generated", "Closed")),
            Negotiation.id.is_not(None),
        ))
        if stage == "open":
            stmt = stmt.where(Candidate.status != "Closed")
    term = (q or "").strip()[:100]
    if term:
        like = f"%{_escape_like(term)}%"
        stmt = stmt.where(or_(
            Candidate.full_name.ilike(like, escape="\\"),
            Candidate.candidate_code.ilike(like, escape="\\"),
            ClientDetail.client_name.ilike(like, escape="\\"),
        ))
    total = db.session.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = db.session.execute(
        stmt.order_by(Candidate.updated_at.desc(), Candidate.id.desc())
        .limit(NEGOTIATION_ROW_LIMIT)
    ).scalars().all()
    return rows, int(total)


# ---------------------------------------------------------------------------
# Create / update transaction
# ---------------------------------------------------------------------------
CANDIDATE_FIELDS = [
    "full_name", "position_applied_for", "department", "total_years_experience",
    "relevant_years_experience", "current_company", "current_designation",
    "notice_period", "notice_negotiable", "current_location", "proposed_work_location",
    "relocation_required", "primary_motivation",
]
CLIENT_FIELDS = [
    "client_name", "client_budget", "client_timeline_days", "client_urgency",
    "client_flexibility", "skill_required", "skill_scarcity",
    "availability_of_talent", "position_for_client", "client_location",
    "replacement_hiring", "notes_from_client",
]
EVALUATION_FIELDS = [
    "current_ctc", "current_fixed_ctc", "current_variable_bonus",
    "expected_ctc", "has_another_offer", "competing_offer_ctc",
    "other_offers_discussion", "recommended_offer", "maximum_approved_offer",
    "estimated_market_ctc", "company_band_min", "company_band_target",
    "company_band_max", "minimum_acceptable_offer_candidate",
    "hr_estimated_fair_compensation",
    "is_on_bench", "bench_months",
    "is_client_selected_candidate", "want_to_switch_domain", "technical_gate_status",
    "company_upgradation", "position_upgradation", "risk_of_losing_candidate",
    "technical_skills_rating", "domain_knowledge_rating", "communication_rating",
    "overall_candidate_potential",
    "risk_compensation_expectation", "risk_counter_offer", "risk_relocation",
    "risk_retention", "risk_skill_capability", "risk_cultural_fit",
    "risk_notice_period", "risk_early_attrition",
    "overall_hiring_risk", "candidate_classification",
    "key_strengths", "key_concerns", "notes",
]
ASSESSMENT_FIELDS = [
    "other_benefits",
    "proposed_designation", "proposed_role_level",
    "key_additional_responsibilities", "expected_business_impact",
    "significant_career_growth",
    "expected_vs_market",
    "relocation_influence_compensation", "can_offer_relocation_support",
    "current_org_type", "proposed_org_type", "significant_career_transition",
    "major_career_benefits",
    "motivation_salary_rank", "motivation_career_growth_rank",
    "motivation_designation_rank", "motivation_role_responsibility_rank",
    "motivation_company_brand_rank", "motivation_oem_exposure_rank",
    "motivation_location_rank", "motivation_work_environment_rank",
    "motivation_technology_learning_rank",
    "motivation_international_exposure_rank", "motivation_other_rank",
    "candidate_negotiation_power", "company_negotiation_power",
    "recommended_action", "key_reason_recommended_compensation",
    "alternatives_to_ctc",
]


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _apply(model, form, names) -> None:
    for name in names:
        setattr(model, name, _clean(form[name].data))


def candidate_to_form_data(candidate: Candidate) -> dict:
    """Flatten candidate + client + evaluation + assessment into form values."""
    data = {n: getattr(candidate, n) for n in CANDIDATE_FIELDS}
    if candidate.client:
        data.update({n: getattr(candidate.client, n) for n in CLIENT_FIELDS})
    if candidate.evaluation:
        data.update({n: getattr(candidate.evaluation, n) for n in EVALUATION_FIELDS})
    if candidate.assessment:
        data.update({n: getattr(candidate.assessment, n) for n in ASSESSMENT_FIELDS})
    return data


def save_candidate(form, user, candidate: Optional[Candidate] = None) -> Candidate:
    """Create or update candidate + client + evaluation + assessment in ONE transaction.

    * Recalculates and stores profitability on every create and edit.
    * candidate_code is generated on create only and NEVER touched on edit.
    """
    is_new = candidate is None
    if is_new:
        candidate = Candidate(created_by=user.id)
        candidate.client = ClientDetail()
        candidate.evaluation = CandidateEvaluation()
        candidate.assessment = Assessment()
    else:
        candidate.client = candidate.client or ClientDetail()
        candidate.evaluation = candidate.evaluation or CandidateEvaluation()
        candidate.assessment = candidate.assessment or Assessment()

    _apply(candidate, form, CANDIDATE_FIELDS)
    _apply(candidate.client, form, CLIENT_FIELDS)
    _apply(candidate.evaluation, form, EVALUATION_FIELDS)
    _apply(candidate.assessment, form, ASSESSMENT_FIELDS)
    # The status is NEVER taken from the form: it is driven by the workflow
    # (Draft -> InProcess -> Generated -> Closed). A new candidate starts at
    # Draft (model default); an edit leaves the current stage untouched.

    # Conditional fields are cleared when their trigger is "No".
    ev = candidate.evaluation
    if ev.has_another_offer != 1:
        ev.competing_offer_ctc = None
    if ev.is_on_bench != 1:
        ev.bench_months = None

    ev.profitability_percentage = calculate_profitability(
        candidate.client.client_budget, ev.expected_ctc)

    if not is_new:
        candidate.updated_at = now_ist()  # touch even if only child rows changed
        db.session.commit()
        invalidate_dashboard_cache()
        return candidate

    # --- create: generate the code inside the transaction, retry on conflict
    last_error = None
    for _ in range(5):
        try:
            with db.session.begin_nested():
                candidate.candidate_code = generate_candidate_code()
                db.session.add(candidate)
                db.session.flush()
            db.session.commit()
            invalidate_dashboard_cache()
            return candidate
        except IntegrityError as exc:
            last_error = exc
            # savepoint rolled back; make the instance pending-free and retry
            if candidate in db.session:
                db.session.expunge(candidate)
    db.session.rollback()
    raise last_error  # type: ignore[misc]
