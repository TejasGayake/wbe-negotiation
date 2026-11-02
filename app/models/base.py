"""Shared model helpers: table options, TINYINT type, timestamp mixin."""
from sqlalchemy import DateTime, SmallInteger
from sqlalchemy.dialects.mysql import TINYINT

from app.extensions import db
from app.utils.timeutil import now_ist

# All tables: utf8mb4 / utf8mb4_unicode_ci, InnoDB (ignored by non-MySQL dialects).
TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}

# Signed MySQL TINYINT (needed for -1 values); SmallInteger elsewhere (SQLite tests).
TinyInt = SmallInteger().with_variant(TINYINT(), "mysql")


class TimestampMixin:
    """created_at / updated_at maintained from the IST helper (never func.now())."""
    created_at = db.Column(DateTime, default=now_ist, nullable=False)
    updated_at = db.Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)
