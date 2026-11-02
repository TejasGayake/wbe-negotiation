"""Small custom WTForms fields/validators shared by the forms.

They treat an empty submission as "no value" (None) instead of raising the
default 'Not a valid ...' error, so that "required" and "range" messages stay
clean and appear only once per field.
"""
import decimal

from wtforms import DecimalField, IntegerField, SelectField
from wtforms.validators import StopValidation, ValidationError


def strip_filter(value):
    return value.strip() if isinstance(value, str) else value


class FlexDecimalField(DecimalField):
    """Decimal that accepts '₹ 12,34,567.50' style input; '' -> None."""

    def __init__(self, label=None, validators=None, **kwargs):
        kwargs.setdefault("places", None)  # never round silently
        super().__init__(label, validators, **kwargs)

    def process_formdata(self, valuelist):
        if not valuelist:
            return
        raw = (valuelist[0] or "").replace("₹", "").replace(",", "").replace(" ", "").strip()
        if raw == "":
            self.data = None
            return
        try:
            value = decimal.Decimal(raw)
            if not value.is_finite():
                raise decimal.InvalidOperation
        except decimal.InvalidOperation as exc:
            self.data = None
            raise ValueError("Enter a valid number.") from exc
        self.data = value


class FlexIntegerField(IntegerField):
    """Integer where '' -> None (no built-in error)."""

    def process_formdata(self, valuelist):
        if not valuelist:
            return
        raw = (valuelist[0] or "").strip()
        if raw == "":
            self.data = None
            return
        try:
            self.data = int(raw)
        except ValueError as exc:
            self.data = None
            raise ValueError("Enter a whole number.") from exc


def _opt_int(value):
    if value in (None, "", "None"):
        return None
    return int(value)


def _opt_str(value):
    if value in (None, "", "None"):
        return None
    return str(value)


class OptionalChoiceField(SelectField):
    """Select that stores an int (or None). Choices come from mappings.py.

    Rendered by hand in templates; only the allowed integer values are accepted.
    """

    def __init__(self, label=None, validators=None, choices=None, **kwargs):
        kwargs.pop("coerce", None)
        kwargs["validate_choice"] = False
        super().__init__(label, validators, coerce=_opt_int, choices=choices or [], **kwargs)
        self._allowed = {c[0] for c in (choices or [])}

    def pre_validate(self, form):
        if self.data is not None and self.data not in self._allowed:
            raise ValidationError("Select a valid option.")


class OptionalTextChoiceField(SelectField):
    """Select that stores a validated string label (or None).

    Used by the questionnaire fields whose column is VARCHAR and whose allowed
    values are the sheet's own wording (see mappings.text_choices_for).
    """

    def __init__(self, label=None, validators=None, choices=None, **kwargs):
        kwargs.pop("coerce", None)
        kwargs["validate_choice"] = False
        super().__init__(label, validators, coerce=_opt_str, choices=choices or [], **kwargs)
        self._allowed = {c[0] for c in (choices or [])}

    def pre_validate(self, form):
        if self.data is not None and self.data not in self._allowed:
            raise ValidationError("Select a valid option.")


# ------------------------------------------------------------------ validators
class Required:
    """Fails for None / blank string with a friendly message, then stops."""

    def __init__(self, message="This field is required."):
        self.message = message

    def __call__(self, form, field):
        data = field.data
        if data is None or (isinstance(data, str) and not data.strip()):
            field.errors[:] = []
            raise StopValidation(self.message)


class Between:
    """Numeric range that ignores None (pair with Required when mandatory)."""

    def __init__(self, minimum=None, maximum=None, message=None):
        self.minimum, self.maximum, self.message = minimum, maximum, message

    def __call__(self, form, field):
        if field.data is None:
            return
        if self.minimum is not None and field.data < self.minimum:
            raise ValidationError(self.message or f"Must be at least {self.minimum}.")
        if self.maximum is not None and field.data > self.maximum:
            raise ValidationError(self.message or f"Must be at most {self.maximum}.")
