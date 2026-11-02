"""Excel export: same query + same query string as the candidates list."""
from io import BytesIO

from flask import Blueprint, request, send_file
from flask_login import login_required
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from app import mappings, services
from app.extensions import db
from app.utils.formatting import format_inr, format_ist
from app.utils.timeutil import now_ist

bp = Blueprint("export", __name__, url_prefix="/export")

PRIMARY = "2563EB"
SUCCESS = "059669"
DANGER = "E11D48"
MUTED = "94A3B8"
BORDER = "E2E8F0"

# Indian grouping in Excel: crore / lakh / thousand tiers (two conditions max).
INR_FORMAT = '[>=10000000]"₹"#\\,##\\,##\\,##0.00;[>=100000]"₹"#\\,##\\,##0.00;"₹"#,##0.00'
YEARS_FORMAT = "0.0"
PLAIN_FORMAT = "0.00"
MAX_WIDTH = 48


def _tri(field):
    return lambda c, cl, ev, _f=field: mappings.to_label(_f, _val(c, cl, ev, _f))


def _val(c, cl, ev, name):
    for obj in (c, cl, ev):
        if obj is not None and hasattr(obj, name):
            return getattr(obj, name)
    return None


# (header, getter, kind)  kind: text | label | inr | years | profit | date | int
COLUMNS = [
    ("Candidate Code", lambda c, cl, ev: c.candidate_code, "text"),
    ("Full Name", lambda c, cl, ev: c.full_name, "text"),
    ("Position Applied For", lambda c, cl, ev: c.position_applied_for, "text"),
    ("Department", lambda c, cl, ev: c.department, "text"),
    ("Status", lambda c, cl, ev: c.status, "text"),
    ("Total Experience (Yrs)", lambda c, cl, ev: c.total_years_experience, "years"),
    ("Relevant Experience (Yrs)", lambda c, cl, ev: c.relevant_years_experience, "years"),
    ("Current Company", lambda c, cl, ev: c.current_company, "text"),
    ("Current Designation", lambda c, cl, ev: c.current_designation, "text"),
    ("Notice Period", lambda c, cl, ev: c.notice_period, "text"),
    ("Current Location", lambda c, cl, ev: c.current_location, "text"),
    ("Proposed Work Location", lambda c, cl, ev: c.proposed_work_location, "text"),
    ("Relocation Required", _tri("relocation_required"), "label"),
    ("Primary Motivation", lambda c, cl, ev: c.primary_motivation, "text"),
    ("Client Name", lambda c, cl, ev: cl.client_name if cl else None, "text"),
    ("Client Budget (Annual)", lambda c, cl, ev: cl.client_budget if cl else None, "inr"),
    ("Client Timeline (Days)", lambda c, cl, ev: cl.client_timeline_days if cl else None, "int"),
    ("Client Urgency", _tri("client_urgency"), "label"),
    ("Client Flexibility", _tri("client_flexibility"), "label"),
    ("Skill Required", lambda c, cl, ev: cl.skill_required if cl else None, "text"),
    ("Skill Scarcity", _tri("skill_scarcity"), "label"),
    ("Availability of Talent", _tri("availability_of_talent"), "label"),
    ("Position for Client", lambda c, cl, ev: cl.position_for_client if cl else None, "text"),
    ("Client Location", lambda c, cl, ev: cl.client_location if cl else None, "text"),
    ("Replacement Hiring", _tri("replacement_hiring"), "label"),
    ("Notes from Client", lambda c, cl, ev: cl.notes_from_client if cl else None, "text"),
    ("Current CTC", lambda c, cl, ev: ev.current_ctc if ev else None, "inr"),
    ("Expected CTC", lambda c, cl, ev: ev.expected_ctc if ev else None, "inr"),
    ("Has Another Offer", _tri("has_another_offer"), "label"),
    ("Competing Offer CTC", lambda c, cl, ev: ev.competing_offer_ctc if ev else None, "inr"),
    ("Recommended Offer", lambda c, cl, ev: ev.recommended_offer if ev else None, "inr"),
    ("Maximum Approved Offer", lambda c, cl, ev: ev.maximum_approved_offer if ev else None, "inr"),
    ("On Bench", _tri("is_on_bench"), "label"),
    ("Bench Months", lambda c, cl, ev: ev.bench_months if ev else None, "years"),
    ("Client Selected Candidate", _tri("is_client_selected_candidate"), "label"),
    ("Wants to Switch Domain", _tri("want_to_switch_domain"), "label"),
    ("Technical Gate Status", _tri("technical_gate_status"), "label"),
    ("Company Upgradation", _tri("company_upgradation"), "label"),
    ("Position Upgradation", _tri("position_upgradation"), "label"),
    ("Risk of Losing Candidate", _tri("risk_of_losing_candidate"), "label"),
    ("Technical Skills Rating", lambda c, cl, ev: ev.technical_skills_rating if ev else None, "int"),
    ("Domain Knowledge Rating", lambda c, cl, ev: ev.domain_knowledge_rating if ev else None, "int"),
    ("Communication Rating", lambda c, cl, ev: ev.communication_rating if ev else None, "int"),
    ("Profitability (%)", lambda c, cl, ev: ev.profitability_percentage if ev else None, "profit"),
    ("Key Strengths", lambda c, cl, ev: ev.key_strengths if ev else None, "text"),
    ("Key Concerns", lambda c, cl, ev: ev.key_concerns if ev else None, "text"),
    ("Notes", lambda c, cl, ev: ev.notes if ev else None, "text"),
    ("Created At (IST)", lambda c, cl, ev: format_ist(c.created_at), "date"),
    ("Updated At (IST)", lambda c, cl, ev: format_ist(c.updated_at), "date"),
]


def build_workbook(candidates) -> BytesIO:
    wb = Workbook()                    # normal (non write-only) mode
    ws = wb.active
    ws.title = "Candidates"

    header_fill = PatternFill("solid", start_color=PRIMARY, end_color=PRIMARY)
    header_font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    thin = Side(style="thin", color=BORDER)
    cell_border = Border(bottom=thin)

    widths = [len(h) + 4 for h, _, _ in COLUMNS]
    for col, (header, _, _) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill, cell.font = header_fill, header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30

    for r, cand in enumerate(candidates, start=2):
        cl, ev = cand.client, cand.evaluation
        for col, (header, getter, kind) in enumerate(COLUMNS, start=1):
            value = getter(cand, cl, ev)
            cell = ws.cell(row=r, column=col)
            cell.border = cell_border
            shown = ""
            if kind in ("inr", "years", "int"):
                if value is None:
                    cell.value, shown = None, ""
                else:
                    num = float(value) if kind != "int" else int(value)
                    cell.value = num
                    cell.number_format = {"inr": INR_FORMAT, "years": YEARS_FORMAT, "int": "0"}[kind]
                    cell.alignment = Alignment(horizontal="right")
                    shown = format_inr(value) if kind == "inr" else str(num)
            elif kind == "profit":
                if value is None:
                    cell.value, shown = "N/A", "N/A"
                    cell.font = Font(color=MUTED)
                    cell.alignment = Alignment(horizontal="right")
                else:
                    num = float(value)
                    cell.value, shown = num, f"{num:.2f}"
                    cell.number_format = PLAIN_FORMAT
                    cell.font = Font(color=SUCCESS if num > 0 else DANGER if num < 0 else "0F172A", bold=True)
                    cell.alignment = Alignment(horizontal="right")
            else:
                text = "" if value is None else str(value)
                cell.value = text or None
                shown = text
                if kind == "text" and header in ("Notes from Client", "Key Strengths", "Key Concerns", "Notes"):
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            longest = max((len(line) for line in shown.splitlines()), default=0)
            widths[col - 1] = max(widths[col - 1], longest + 2)

    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = min(width, MAX_WIDTH)

    ws.freeze_panes = "A2"
    last_row = max(ws.max_row, 1)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{last_row}"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@bp.route("/candidates.xlsx")
@login_required
def candidates_xlsx():
    # Same parser + same build_candidates_query as the list page; paging ignored.
    params = services.parse_list_params(request.args)
    stmt = services.build_candidates_query(params, defer_text=False)
    candidates = db.session.execute(stmt).scalars().all()
    buf = build_workbook(candidates)
    filename = f"WBE_Candidates_{now_ist().strftime('%Y-%m-%d_%H-%M')}.xlsx"
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        max_age=0,
    )
