"""Login and change-password forms."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(message="Enter your email.")],
                        filters=[lambda v: v.strip().lower() if isinstance(v, str) else v])
    password = PasswordField("Password", validators=[DataRequired(message="Enter your password.")])
    remember = BooleanField("Remember me for 30 days")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password",
                                     validators=[DataRequired(message="Enter your current password.")])
    new_password = PasswordField("New password", validators=[
        DataRequired(message="Enter a new password."),
        Length(min=8, max=128, message="New password must be at least 8 characters.")])
    confirm_password = PasswordField("Confirm new password", validators=[
        DataRequired(message="Confirm your new password."),
        EqualTo("new_password", message="Passwords do not match.")])
