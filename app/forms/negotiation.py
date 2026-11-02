"""The HR negotiation form: what we offered, what the candidate confirmed.

Saved into ng_6_negotiations. The script side of the negotiation is written by
the n8n workflow into ng_5 and is not edited here.
"""
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import TextAreaField
from wtforms.validators import Length, Optional

from app.forms.fields import Between, FlexDecimalField, strip_filter

MAX_MONEY = Decimal("9999999999.99")   # DECIMAL(12,2)
MAX_TEXT = 5000


class NegotiationForm(FlaskForm):
    offered_amount = FlexDecimalField("Amount Offered", validators=[
        Between(Decimal("0"), MAX_MONEY,
                "Amount offered must be between ₹0 and ₹99,99,99,999.99.")])
    confirmed_ctc = FlexDecimalField("Salary Confirmed by Candidate", validators=[
        Between(Decimal("0"), MAX_MONEY,
                "Confirmed salary must be between ₹0 and ₹99,99,99,999.99.")])
    negotiation_notes = TextAreaField("Remarks", validators=[
        Optional(strip_whitespace=True),
        Length(max=MAX_TEXT, message=f"Maximum {MAX_TEXT} characters allowed.")],
        filters=[strip_filter])

    def require_amounts(self) -> bool:
        """Both amounts must be there before a negotiation can be closed."""
        ok = True
        for field, message in (
            (self.offered_amount, "Enter the amount you offered."),
            (self.confirmed_ctc, "Enter the salary the candidate confirmed."),
        ):
            if field.data is None:
                field.errors = list(field.errors) + [message]
                ok = False
        return ok
