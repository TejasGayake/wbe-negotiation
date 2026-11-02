"""Authentication: login, logout, change password."""
from urllib.parse import urljoin, urlparse

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from werkzeug.security import check_password_hash

from app.extensions import db
from app.forms.auth import ChangePasswordForm, LoginForm
from app.models import User
from app.utils.timeutil import now_ist

bp = Blueprint("auth", __name__)

# Used to keep timing similar when the email does not exist.
_DUMMY_HASH = "pbkdf2:sha256:600000$x$0000000000000000000000000000000000000000000000000000000000000000"


def is_safe_next(target: str | None) -> bool:
    """Only same-site relative URLs are allowed as a post-login redirect."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return False
    ref, test = urlparse(request.host_url), urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc and not test.netloc == ""


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            select(User).where(User.email == form.email.data)).scalar_one_or_none()
        valid = False
        if user is not None:
            valid = user.check_password(form.password.data)
        else:
            check_password_hash(_DUMMY_HASH, form.password.data)
        # Generic message for wrong email, wrong password and inactive users.
        if valid and user.is_active:
            login_user(user, remember=bool(form.remember.data))
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_next(nxt) else url_for("dashboard.index"))
        current_app.logger.warning("Failed login attempt for %s", form.email.data)
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            # Generic inline error; the password itself is never logged/flashed.
            form.current_password.errors = ["Current password is incorrect."]
        elif form.new_password.data == form.current_password.data:
            form.new_password.errors = ["New password must be different from the current password."]
        else:
            current_user.set_password(form.new_password.data)
            current_user.updated_at = now_ist()
            db.session.commit()
            flash("Your password has been changed.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html", form=form)
