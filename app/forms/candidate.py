"""CandidateForm: one form object for the 8-step wizard (Add + Edit).

Steps mirror the Salary_Negotiation_Assessment questionnaire:
  1 A   candidate information          (ng_2)
  2     client details                 (ng_3, not part of the questionnaire)
  3 B+C current compensation + proposed role
  4 D+E capability + market position
  5 F+G relocation + career transition
  6 H   motivation ranking
  7 I+J negotiation position + hiring risk
  8 K+L classification + HR recommendation + review

All fields of all steps are validated together on the final submit; the view
then jumps back to the first step that contains an error (STEP_FIELDS).
"""
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField
from wtforms.validators import Length, Optional

from app import mappings
from app.forms.fields import (
    Between, FlexDecimalField, FlexIntegerField, OptionalChoiceField,
    OptionalTextChoiceField, Required, strip_filter,
)

MIN_MONEY = Decimal("10000")
MAX_MONEY = Decimal("9999999999.99")   # DECIMAL(12,2)
MAX_YEARS = Decimal("99.9")
MAX_TEXT = 5000

# ng_7_assessment columns the wizard writes (derived values are never stored).
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

STEP_FIELDS = {
    1: ["full_name", "position_applied_for", "department", "total_years_experience",
        "relevant_years_experience", "current_company", "current_designation",
        "notice_period", "notice_negotiable", "current_location", "proposed_work_location",
        "relocation_required", "primary_motivation"],
    2: ["client_name", "client_budget", "client_timeline_days", "client_urgency",
        "client_flexibility", "skill_required", "skill_scarcity",
        "availability_of_talent", "position_for_client", "client_location",
        "replacement_hiring", "notes_from_client"],
    # B: current compensation / C: proposed role
    3: ["current_ctc", "current_fixed_ctc", "current_variable_bonus", "other_benefits",
        "expected_ctc", "has_another_offer", "competing_offer_ctc",
        "other_offers_discussion", "proposed_designation", "proposed_role_level",
        "key_additional_responsibilities", "expected_business_impact",
        "significant_career_growth"],
    # D: capability & potential / E: market position
    4: ["technical_skills_rating", "domain_knowledge_rating", "communication_rating",
        "overall_candidate_potential", "key_strengths", "key_concerns",
        "estimated_market_ctc", "company_band_min", "company_band_target",
        "company_band_max", "expected_vs_market"],
    # F: relocation / G: career transition
    5: ["relocation_influence_compensation", "can_offer_relocation_support",
        "current_org_type", "proposed_org_type", "significant_career_transition",
        "major_career_benefits"],
    # H: motivation ranking (primary_motivation is captured in step 1)
    6: ["motivation_salary_rank", "motivation_career_growth_rank",
        "motivation_designation_rank", "motivation_role_responsibility_rank",
        "motivation_company_brand_rank", "motivation_oem_exposure_rank",
        "motivation_location_rank", "motivation_work_environment_rank",
        "motivation_technology_learning_rank",
        "motivation_international_exposure_rank", "motivation_other_rank"],
    # I: negotiation position / J: hiring risk
    7: ["recommended_offer", "maximum_approved_offer",
        "minimum_acceptable_offer_candidate", "hr_estimated_fair_compensation",
        "candidate_negotiation_power", "company_negotiation_power",
        "risk_compensation_expectation", "risk_counter_offer", "risk_relocation",
        "risk_retention", "risk_skill_capability", "risk_cultural_fit",
        "risk_notice_period", "risk_early_attrition", "overall_hiring_risk"],
    # K: classification / L: recommendation / operational flags / review
    8: ["candidate_classification", "recommended_action",
        "key_reason_recommended_compensation", "alternatives_to_ctc",
        "is_on_bench", "bench_months", "is_client_selected_candidate",
        "want_to_switch_domain", "technical_gate_status", "company_upgradation",
        "position_upgradation", "risk_of_losing_candidate", "notes"],
}


def _text(label, maxlen, required=False, req_msg=None):
    validators = []
    if required:
        validators.append(Required(req_msg or f"{label} is required."))
    else:
        validators.append(Optional(strip_whitespace=True))
    validators.append(Length(max=maxlen, message=f"Maximum {maxlen} characters allowed."))
    return StringField(label, validators=validators, filters=[strip_filter])


def _area(label, maxlen=MAX_TEXT):
    return TextAreaField(label, validators=[
        Optional(strip_whitespace=True),
        Length(max=maxlen, message=f"Maximum {maxlen} characters allowed.")],
        filters=[strip_filter])


def _choice(field_name, label):
    return OptionalChoiceField(label, choices=mappings.choices_for(field_name))


def _text_choice(field_name, label):
    return OptionalTextChoiceField(label, choices=mappings.text_choices_for(field_name))


def _money(label, required=False, minimum=Decimal("0")):
    validators = []
    if required:
        validators.append(Required(f"{label} is required."))
    validators.append(Between(
        minimum, MAX_MONEY,
        f"{label} must be between ₹{int(minimum):,} and ₹99,99,99,999.99."
        if minimum else f"{label} must be a positive amount (max ₹99,99,99,999.99)."))
    return FlexDecimalField(label, validators=validators)


def _years(label):
    return FlexDecimalField(label, validators=[
        Between(Decimal("0"), MAX_YEARS, f"{label} must be between 0 and 99.9.")])


def _rating(label):
    return FlexIntegerField(label, validators=[
        Required(f"{label} is required."),
        Between(1, 5, f"{label} must be between 1 and 5.")])


def _optional_rating(label):
    """1-5 like _rating, but blank is allowed (legacy rows have NULLs)."""
    return FlexIntegerField(label, validators=[
        Between(1, 5, f"{label} must be between 1 and 5.")])


def _rank(label):
    return FlexIntegerField(label, validators=[
        Between(1, 5, f"{label} must be between 1 and 5.")])


class CandidateForm(FlaskForm):
    # ---- Step 1 (A): Candidate information
    full_name = _text("Full Name", 150, required=True)
    position_applied_for = _text("Position Applied For", 150, required=True)
    department = _text("Department", 100, required=True)
    total_years_experience = _years("Total Years of Experience")
    relevant_years_experience = _years("Relevant Years of Experience")
    current_company = _text("Current Company", 150)
    current_designation = _text("Current Designation", 150)
    notice_period = _text("Notice Period", 50)
    notice_negotiable = _choice("notice_negotiable", "Notice Negotiable")
    current_location = _text("Current Location", 100)
    proposed_work_location = _text("Proposed Work Location", 100)
    relocation_required = _choice("relocation_required", "Relocation Required")
    primary_motivation = _text("Primary Motivation", 100)

    # ---- Step 2: Client details
    client_name = _text("Client Name", 150, required=True)
    client_budget = _money("Client Budget (Annual, INR)", required=True, minimum=MIN_MONEY)
    client_timeline_days = FlexIntegerField("Client Timeline (days)", validators=[
        Between(0, 3650, "Timeline must be between 0 and 3650 days.")])
    client_urgency = _choice("client_urgency", "Client Urgency")
    client_flexibility = _choice("client_flexibility", "Client Flexibility")
    skill_required = _text("Skill Required", 150)
    skill_scarcity = _choice("skill_scarcity", "Skill Scarcity")
    availability_of_talent = _choice("availability_of_talent", "Availability of Talent")
    position_for_client = _text("Position for Client", 150)
    client_location = _text("Client Location", 100)
    replacement_hiring = _choice("replacement_hiring", "Replacement Hiring")
    notes_from_client = _area("Notes from Client")

    # ---- Step 3 (B): Current compensation
    current_ctc = _money("Current CTC")
    current_fixed_ctc = _money("Current Fixed CTC")
    current_variable_bonus = _money("Current Variable Bonus")
    other_benefits = _area("Other Benefits / Allowances")
    expected_ctc = _money("Expected CTC", required=True, minimum=MIN_MONEY)
    has_another_offer = _choice("has_another_offer", "Has Another Offer")
    competing_offer_ctc = _money("Competing Offer CTC")
    other_offers_discussion = _area("Other Offers Discussion")

    # ---- Step 3 (C): Proposed role
    proposed_designation = _text("Proposed Designation", 150)
    proposed_role_level = _text_choice("proposed_role_level", "Proposed Role Level")
    key_additional_responsibilities = _area("Key Additional Responsibilities")
    expected_business_impact = _text_choice("expected_business_impact",
                                           "Expected Business Impact")
    significant_career_growth = _text_choice("significant_career_growth",
                                             "Significant Career Growth")

    # ---- Step 4 (D): Capability & potential
    technical_skills_rating = _rating("Technical Skills Rating")
    domain_knowledge_rating = _rating("Domain Knowledge Rating")
    communication_rating = _rating("Communication Rating")
    overall_candidate_potential = _text_choice("overall_candidate_potential",
                                               "Overall Candidate Potential")
    key_strengths = _area("Key Strengths")
    key_concerns = _area("Key Concerns")

    # ---- Step 4 (E): Market position
    estimated_market_ctc = _money("Estimated Market CTC")
    company_band_min = _money("Company Band Minimum")
    company_band_target = _money("Company Band Target")
    company_band_max = _money("Company Band Maximum")
    expected_vs_market = _text_choice("expected_vs_market", "Expected vs Market")

    # ---- Step 5 (F): Relocation & location
    relocation_influence_compensation = _text_choice(
        "relocation_influence_compensation", "Relocation Influence on Compensation")
    can_offer_relocation_support = _text_choice(
        "can_offer_relocation_support", "Can Offer Relocation Support")

    # ---- Step 5 (G): Career transition
    current_org_type = _text_choice("current_org_type", "Current Organisation Type")
    proposed_org_type = _text_choice("proposed_org_type", "Proposed Organisation Type")
    significant_career_transition = _text_choice(
        "significant_career_transition", "Significant Career Transition")
    major_career_benefits = _area("Major Career Benefits")

    # ---- Step 6 (H): Motivation ranking, 1 = most important, blank = n/a
    motivation_salary_rank = _rank("Salary")
    motivation_career_growth_rank = _rank("Career Growth")
    motivation_designation_rank = _rank("Designation")
    motivation_role_responsibility_rank = _rank("Role / Responsibility")
    motivation_company_brand_rank = _rank("Company Brand")
    motivation_oem_exposure_rank = _rank("OEM Exposure")
    motivation_location_rank = _rank("Location")
    motivation_work_environment_rank = _rank("Work Environment")
    motivation_technology_learning_rank = _rank("Technology Learning")
    motivation_international_exposure_rank = _rank("International Exposure")
    motivation_other_rank = _rank("Other")

    # ---- Step 7 (I): Negotiation position
    recommended_offer = _money("Recommended Offer")
    maximum_approved_offer = _money("Maximum Approved Offer")
    minimum_acceptable_offer_candidate = _money("Minimum Acceptable Offer (Candidate)")
    hr_estimated_fair_compensation = _money("HR Estimated Fair Compensation")
    candidate_negotiation_power = _text_choice("candidate_negotiation_power",
                                               "Candidate Negotiation Power")
    company_negotiation_power = _text_choice("company_negotiation_power",
                                             "Company Negotiation Power")

    # ---- Step 7 (J): Hiring risk assessment (1 = low risk, 5 = high risk)
    risk_compensation_expectation = _optional_rating("Compensation Expectation Risk")
    risk_counter_offer = _optional_rating("Counter Offer Risk")
    risk_relocation = _optional_rating("Relocation Risk")
    risk_retention = _optional_rating("Retention Risk")
    risk_skill_capability = _optional_rating("Skill Capability Risk")
    risk_cultural_fit = _optional_rating("Cultural Fit Risk")
    risk_notice_period = _optional_rating("Notice Period Risk")
    risk_early_attrition = _optional_rating("Early Attrition Risk")
    overall_hiring_risk = _text_choice("overall_hiring_risk", "Overall Hiring Risk")

    # ---- Step 8 (K): Final candidate classification
    candidate_classification = _text_choice("candidate_classification",
                                            "Candidate Classification")

    # ---- Step 8 (L): HR recommendation
    recommended_action = _text_choice("recommended_action", "Recommended Action")
    key_reason_recommended_compensation = _area("Key Reason for Recommended Compensation")
    alternatives_to_ctc = _area("Alternatives to CTC")

    # ---- Step 8: operational flags
    is_on_bench = _choice("is_on_bench", "Is On Bench")
    bench_months = FlexDecimalField("Bench Months", validators=[
        Between(Decimal("0"), Decimal("999.9"), "Bench months must be between 0 and 999.9.")])
    is_client_selected_candidate = _choice("is_client_selected_candidate", "Client Selected Candidate")
    want_to_switch_domain = _choice("want_to_switch_domain", "Wants to Switch Domain")
    technical_gate_status = _choice("technical_gate_status", "Technical Gate Status")
    company_upgradation = _choice("company_upgradation", "Company Upgradation")
    position_upgradation = _choice("position_upgradation", "Position Upgradation")
    risk_of_losing_candidate = _choice("risk_of_losing_candidate", "Risk of Losing Candidate")
    notes = _area("Notes")

    # No status field: the status is driven by the workflow buttons
    # (Generate script -> InProcess -> Generated -> Close -> Closed), never
    # picked by hand. See app/services.py for the transitions.

    # ------------------------------------------------------------ cross-field
    @staticmethod
    def _add_error(field, message):
        field.errors = list(field.errors) + [message]

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        extra_ok = True

        total, relevant = self.total_years_experience.data, self.relevant_years_experience.data
        if total is not None and relevant is not None and relevant > total:
            self._add_error(self.relevant_years_experience,
                            "Relevant experience cannot exceed total experience.")
            extra_ok = False

        if self.has_another_offer.data == 1 and self.competing_offer_ctc.data is None \
                and not self.competing_offer_ctc.errors:
            self._add_error(self.competing_offer_ctc,
                            "Competing offer CTC is required when the candidate has another offer.")
            extra_ok = False

        if self.is_on_bench.data == 1 and self.bench_months.data is None \
                and not self.bench_months.errors:
            self._add_error(self.bench_months, "Bench months is required when the candidate is on bench.")
            extra_ok = False

        rec, mx = self.recommended_offer.data, self.maximum_approved_offer.data
        if rec is not None and mx is not None and rec > mx:
            self._add_error(self.recommended_offer,
                            "Recommended offer cannot exceed the maximum approved offer.")
            extra_ok = False

        band_min, band_max = self.company_band_min.data, self.company_band_max.data
        if band_min is not None and band_max is not None and band_min > band_max:
            self._add_error(self.company_band_max,
                            "Band maximum cannot be lower than the band minimum.")
            extra_ok = False

        return ok and extra_ok

    def first_error_step(self) -> int:
        """Lowest step number that contains a field error (default 8)."""
        for step, names in STEP_FIELDS.items():
            if any(self[n].errors for n in names):
                return step
        return 8
