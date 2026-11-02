"""ng_1_users"""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager
from app.models.base import TABLE_ARGS, TimestampMixin, TinyInt


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "ng_1_users"
    __table_args__ = (TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="HR", server_default="HR")
    # 1 = Active, 0 = Inactive (overrides UserMixin.is_active property)
    is_active = db.Column(TinyInt, nullable=False, default=1, server_default="1")

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self) -> bool:
        return self.role == "Admin"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id: str):
    try:
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
    # A deactivated user is treated as signed out on their next request.
    return user if user is not None and user.is_active else None
