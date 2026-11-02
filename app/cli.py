"""CLI commands: flask seed-admin"""
import os

import click
from sqlalchemy import select

from app.extensions import db
from app.models import User


def register_cli(app):
    @app.cli.command("seed-admin")
    @click.option("--force", is_flag=True,
                  help="Create another Admin even if one already exists.")
    def seed_admin(force):
        """Create an Admin user from .env (ADMIN_NAME/EMAIL/PASSWORD) or prompts."""
        existing = db.session.execute(
            select(User).where(User.role == "Admin").limit(1)).scalar_one_or_none()
        if existing and not force:
            click.echo(f"An Admin already exists ({existing.email}). Use --force to add another.")
            raise SystemExit(1)

        name = os.environ.get("ADMIN_NAME") or click.prompt("Admin name")
        email = (os.environ.get("ADMIN_EMAIL") or click.prompt("Admin email")).strip().lower()
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            password = click.prompt("Admin password (min 8 chars)", hide_input=True,
                                    confirmation_prompt=True)
        if len(password) < 8:
            click.echo("Password must be at least 8 characters.")
            raise SystemExit(1)
        if db.session.execute(select(User).where(User.email == email)).scalar_one_or_none():
            click.echo(f"A user with email {email} already exists.")
            raise SystemExit(1)

        user = User(name=name, email=email, role="Admin", is_active=1)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin created: {email}")
