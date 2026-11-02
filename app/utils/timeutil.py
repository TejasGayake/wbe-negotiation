"""Single IST time helper. All timestamps in the app come from here."""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Current time in IST as a NAIVE datetime (stored as-is in MySQL DATETIME).

    Used for every model default/onupdate (instead of func.now()), for the
    candidate_code year and for the Excel filename.
    """
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)
