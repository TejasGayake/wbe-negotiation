"""Single source of truth for TINYINT label <-> integer mappings.

Templates, forms, filters and the Excel export must use these helpers and
never hard-code labels anywhere else.
"""

# ---------------------------------------------------------------- definitions
YES_NO = {1: "Yes", 0: "No"}
HIGH_MED_LOW = {1: "High", 0: "Medium", -1: "Low"}
SCARCITY = {1: "Extremely Niche", 0: "Semi-niche", -1: "Generic"}
# Stored as TINYINT, so only three of the sheet's four levels fit: its
# "Highly Scarce" collapses into "Difficult to Find" until the column changes.
AVAILABILITY = {1: "Easily Available", 0: "Moderately Available",
                -1: "Difficult to Find"}
TECH_GATE = {1: "Cleared", 0: "Pending", -1: "Not Cleared"}

# String vocabularies for the ng_7_assessment questionnaire (the sheet's own
# wording, so exports and the wizard speak the same language).
YES_NO_TEXT = ("Yes", "No")
ROLE_LEVEL = ("Same level", "Higher responsibility", "Leadership role",
              "Managerial role")
BUSINESS_IMPACT = ("Low", "Medium", "High", "Critical")
YES_NO_MODERATE = ("Yes", "No", "Moderate")
POTENTIAL = ("Low", "Moderate", "High", "Exceptional")
VS_MARKET = ("Below Market", "Market Aligned", "Above Market",
             "Significantly Above Market")
RELOCATION_INFLUENCE = ("Low", "Medium", "High", "Very High")
LOW_MED_HIGH = ("Low", "Medium", "High")
ORG_TYPE = ("Small Company", "Mid-size Company", "Large Company", "MNC",
            "OEM", "Supplier")
RECOMMENDED_ACTION = ("Proceed with Offer", "Negotiate Further", "Hold",
                      "Reject")
CLASSIFICATION = ("High Potential + High Compensation Demand",
                  "High Potential + Fair Compensation",
                  "Lower Potential + Fair Compensation", "Other (specify)")
RANK_CHOICES = (1, 2, 3, 4, 5)

# ng_7 field name -> allowed string values (dropdown fields only)
ASSESSMENT_CHOICES = {
    "proposed_role_level": ROLE_LEVEL,
    "expected_business_impact": BUSINESS_IMPACT,
    "significant_career_growth": YES_NO_MODERATE,
    "expected_vs_market": VS_MARKET,
    "relocation_influence_compensation": RELOCATION_INFLUENCE,
    "can_offer_relocation_support": YES_NO_TEXT,
    "current_org_type": ORG_TYPE,
    "proposed_org_type": ORG_TYPE,
    "significant_career_transition": YES_NO_TEXT,
    "candidate_negotiation_power": LOW_MED_HIGH,
    "company_negotiation_power": LOW_MED_HIGH,
    "recommended_action": RECOMMENDED_ACTION,
}

# ng_4 columns that hold the sheet's string vocabulary instead of a TINYINT.
NG4_TEXT_CHOICES = {
    "overall_candidate_potential": POTENTIAL,
    "overall_hiring_risk": LOW_MED_HIGH,
    "candidate_classification": CLASSIFICATION,
}

# field name -> mapping dict
FIELD_MAPS = {
    "relocation_required": YES_NO,
    "notice_negotiable": YES_NO,
    "client_urgency": HIGH_MED_LOW,
    "client_flexibility": YES_NO,
    "skill_scarcity": SCARCITY,
    "availability_of_talent": AVAILABILITY,
    "replacement_hiring": YES_NO,
    "has_another_offer": YES_NO,
    "is_on_bench": YES_NO,
    "is_client_selected_candidate": YES_NO,
    "want_to_switch_domain": YES_NO,
    "technical_gate_status": TECH_GATE,
    "company_upgradation": YES_NO,
    "position_upgradation": YES_NO,
    "risk_of_losing_candidate": HIGH_MED_LOW,
}

# The candidate lifecycle. The status is NEVER chosen by hand: it moves
# Draft -> InProcess -> Generated -> Closed through the workflow buttons.
#   Draft      data is being captured (the wizard)
#   InProcess the negotiation script was requested; n8n is generating it
#   Generated  the script exists (the two PDF links are in ng_5)
#   Closed     HR closed the negotiation (the outcome is in ng_6)
STATUS_CHOICES = ("Draft", "InProcess", "Generated", "Closed")
ROLES = ("Admin", "HR")

# What the user sees; the stored values stay as STATUS_CHOICES.
STATUS_LABELS = {
    "Draft": "Draft",
    "InProcess": "In progress",
    "Generated": "Script ready",
    "Closed": "Closed",
}

# Bootstrap-ish badge classes (our own CSS) for statuses
STATUS_BADGE = {
    "Draft": "badge-muted",
    "InProcess": "badge-warning",
    "Generated": "badge-primary",
    "Closed": "badge-success",
}


# -------------------------------------------------------------------- helpers
def choices_for(field: str):
    """WTForms choices [(int, label), ...] preserving mapping order."""
    return [(k, v) for k, v in FIELD_MAPS[field].items()]


def text_choices_for(field: str):
    """WTForms choices [(value, label), ...] for the string dropdowns.

    Covers both the ng_7 questionnaire vocabularies and the ng_4 columns that
    store a label instead of a TINYINT.
    """
    values = ASSESSMENT_CHOICES.get(field) or NG4_TEXT_CHOICES.get(field)
    if values is None:
        raise KeyError(field)
    return [(v, v) for v in values]


def to_label(field: str, value, empty: str = "—") -> str:
    """Integer -> label (None-safe)."""
    if value is None:
        return empty
    return FIELD_MAPS[field].get(int(value), empty)


def to_int(field: str, label):
    """Label -> integer (case-insensitive), None if unknown."""
    if label is None:
        return None
    wanted = str(label).strip().lower()
    for k, v in FIELD_MAPS[field].items():
        if v.lower() == wanted:
            return k
    return None


def level_badge(field: str, value) -> str:
    """CSS badge class for a tri-state / yes-no value (semantic colouring)."""
    if value is None:
        return "badge-muted"
    value = int(value)
    if field == "technical_gate_status":
        return {1: "badge-success", 0: "badge-warning", -1: "badge-danger"}[value]
    if field == "risk_of_losing_candidate":
        return {1: "badge-danger", 0: "badge-warning", -1: "badge-success"}[value]
    if field in ("client_urgency",):
        return {1: "badge-danger", 0: "badge-warning", -1: "badge-muted"}[value]
    if field in ("skill_scarcity",):
        return {1: "badge-primary", 0: "badge-info", -1: "badge-muted"}[value]
    return "badge-info" if value == 1 else "badge-muted"


def valid_values(field: str):
    return list(FIELD_MAPS[field].keys())
