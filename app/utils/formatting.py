"""Display formatting helpers: Indian number grouping, IST dates, profit colours."""
import colorsys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


def _to_decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def indian_group(int_part: str) -> str:
    """Group digits Indian style: 1234567 -> 12,34,567."""
    if len(int_part) <= 3:
        return int_part
    head, tail = int_part[:-3], int_part[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_number(value, decimals: int = 2, empty: str = "—") -> str:
    """Indian-grouped number with fixed decimals (no currency symbol)."""
    d = _to_decimal(value)
    if d is None:
        return empty
    q = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    d = d.quantize(q, rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    text = f"{abs(d):.{decimals}f}"
    int_part, _, frac = text.partition(".")
    out = indian_group(int_part)
    if decimals:
        out += "." + frac
    return sign + out


def format_inr(value, decimals: int = 2, empty: str = "—") -> str:
    """₹12,34,567.00 style currency."""
    d = _to_decimal(value)
    if d is None:
        return empty
    text = format_number(d, decimals)
    if text.startswith("-"):
        return "-₹" + text[1:]
    return "₹" + text


def format_percent(value, empty: str = "N/A") -> str:
    d = _to_decimal(value)
    if d is None:
        return empty
    return format_number(d, 2) + "%"


def profit_class(value) -> str:
    """CSS class for profitability colouring."""
    d = _to_decimal(value)
    if d is None:
        return "profit-na"
    if d > 0:
        return "profit-pos"
    if d < 0:
        return "profit-neg"
    return "profit-zero"


# ---- profitability colour ramp: red at/below 10%, green at/above 30% ----
MARGIN_RED_AT = 10
MARGIN_GREEN_AT = 30
MARGIN_GREEN_HUE = 140.0


def margin_hue(value) -> float:
    """Hue for a profitability percentage: 0 = red (poor) .. 140 = green (healthy)."""
    d = _to_decimal(value)
    if d is None:
        return 0.0
    v = float(d)
    if v <= MARGIN_RED_AT:
        return 0.0
    if v >= MARGIN_GREEN_AT:
        return MARGIN_GREEN_HUE
    return MARGIN_GREEN_HUE * (v - MARGIN_RED_AT) / (MARGIN_GREEN_AT - MARGIN_RED_AT)


def _hsl_hex(hue: float, saturation: float, lightness: float) -> str:
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness, saturation)
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


def margin_color(value, empty: str = "") -> str:
    """Solid hero colour for a profitability percentage ('' when unknown)."""
    if _to_decimal(value) is None:
        return empty
    return _hsl_hex(margin_hue(value), 0.62, 0.34)


def margin_gradient(value, empty: str = "") -> str:
    """Diagonal hero gradient for a profitability percentage ('' when unknown)."""
    if _to_decimal(value) is None:
        return empty
    hue = margin_hue(value)
    return "linear-gradient(135deg, {} 0%, {} 100%)".format(
        _hsl_hex(hue, 0.68, 0.22), _hsl_hex(hue, 0.58, 0.34)
    )


def _hsl(hue: float, saturation: float, lightness: float, alpha=None) -> str:
    if alpha is None:
        return "hsl({:.0f}, {:.0f}%, {:.0f}%)".format(hue, saturation * 100, lightness * 100)
    return "hsla({:.0f}, {:.0f}%, {:.0f}%, {})".format(hue, saturation * 100, lightness * 100, alpha)


def margin_hero(value, empty: str = "") -> str:
    """Layered hero background keyed to the profitability percentage.

    A deep->rich hue sweep (so the signal always carries colour) lifted by a
    bright sheen top-right and a soft glow bottom-left, so the surface reads
    dimensional rather than a flat single tone. '' when the value is unknown.
    """
    if _to_decimal(value) is None:
        return empty
    h = margin_hue(value)
    return (
        "radial-gradient(120% 145% at 90% -16%, {sheen} 0%, {sheen0} 55%), "
        "radial-gradient(95% 130% at -4% 112%, {glow} 0%, {glow0} 58%), "
        "linear-gradient(138deg, {deep} 0%, {mid} 50%, {rich} 100%)"
    ).format(
        sheen=_hsl(h, .88, .70), sheen0=_hsl(h, .88, .70, 0),
        glow=_hsl(h, .82, .48), glow0=_hsl(h, .82, .48, 0),
        deep=_hsl(h, .74, .16), mid=_hsl(h, .67, .27), rich=_hsl(h, .62, .37),
    )


def margin_tint(value, empty: str = "") -> str:
    """Soft chip background for a profitability percentage ('' when unknown).

    The hue follows the ramp so the whole 10-30% band drifts smoothly from red
    to green instead of snapping to one fixed mid colour. Saturation and
    lightness are held constant, which keeps every tint an equally light pastel.
    """
    if _to_decimal(value) is None:
        return empty
    return _hsl_hex(margin_hue(value), 0.72, 0.945)


def margin_ink(value, empty: str = "") -> str:
    """Deep, legible chip text colour for a profitability percentage ('' when unknown)."""
    if _to_decimal(value) is None:
        return empty
    return _hsl_hex(margin_hue(value), 0.52, 0.28)


def format_ist(value, empty: str = "—") -> str:
    """DD-MMM-YYYY hh:mm AM/PM (value is already naive IST)."""
    if not value:
        return empty
    if isinstance(value, datetime):
        return value.strftime("%d-%b-%Y %I:%M %p")
    return str(value)


def initials(name, count: int = 2) -> str:
    """'Asha Rao' -> 'AR' (avatar text)."""
    parts = [w for w in str(name or "").split() if w]
    if not parts:
        return "?"
    return "".join(w[0] for w in parts[:count]).upper()


def lakh(value, empty: str = "—") -> str:
    """Compact Indian unit: 3850000 -> '₹38.50 L', 18.4e7 -> '₹18.40 Cr'."""
    d = _to_decimal(value)
    if d is None:
        return empty
    sign = "-" if d < 0 else ""
    d = abs(d)
    if d >= Decimal(10_000_000):
        return f"{sign}₹{(d / Decimal(10_000_000)):.2f} Cr"
    if d >= Decimal(100_000):
        return f"{sign}₹{(d / Decimal(100_000)):.2f} L"
    return f"{sign}₹{format_number(d, 0)}"
