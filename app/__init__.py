"""Application factory for N8N Hiring - Negotiation (Wissen Baum Engineering Solutions)."""
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import get_config
from app.extensions import cache, compress, csrf, db, login_manager, migrate


def create_app(config_class=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    _init_extensions(app)
    _register_mysql_timezone(app)
    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_handlers(app)
    _configure_logging(app)

    from app.cli import register_cli
    register_cli(app)

    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    compress.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"

    # Import models so Flask-Migrate / metadata can see them.
    from app import models  # noqa: F401


def _register_mysql_timezone(app: Flask) -> None:
    """Set MySQL session time_zone = '+05:30' on every new connection."""
    @event.listens_for(Engine, "connect")
    def _set_tz(dbapi_conn, _record):
        # Only for MySQL / PyMySQL connections.
        if dbapi_conn.__class__.__module__.startswith("pymysql"):
            cur = dbapi_conn.cursor()
            cur.execute("SET time_zone = '+05:30'")
            cur.close()


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.candidates import bp as candidates_bp
    from app.blueprints.export import bp as export_bp
    from app.blueprints.insights import bp as insights_bp
    from app.blueprints.negotiations import bp as negotiations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(candidates_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(negotiations_bp)


def _register_template_helpers(app: Flask) -> None:
    from app import mappings
    from app.utils.timeutil import now_ist
    from app import services
    from app.utils.formatting import (
        MARGIN_GREEN_AT, MARGIN_RED_AT, format_inr, format_ist, format_number,
        format_percent, initials, lakh, margin_color, margin_gradient, margin_hero,
        margin_ink, margin_tint, profit_class,
    )

    app.jinja_env.filters["inr"] = format_inr
    app.jinja_env.filters["ist"] = format_ist
    app.jinja_env.filters["num"] = format_number
    app.jinja_env.filters["pct"] = format_percent
    app.jinja_env.filters["profit_class"] = profit_class
    app.jinja_env.filters["initials"] = initials
    app.jinja_env.filters["lakh"] = lakh
    app.jinja_env.filters["margin_color"] = margin_color
    app.jinja_env.filters["margin_gradient"] = margin_gradient
    app.jinja_env.filters["margin_hero"] = margin_hero
    app.jinja_env.filters["margin_tint"] = margin_tint
    app.jinja_env.filters["margin_ink"] = margin_ink

    @app.context_processor
    def _inject():
        return {
            "COMPANY_NAME": "Wissen Baum Engineering Solutions",
            "PROJECT_NAME": "N8N Hiring - Negotiation",
            "maps": mappings,
            "STATUSES": mappings.STATUS_CHOICES,
            "now_year": lambda: now_ist().year,
            "TARGET_MARGIN": app.config["TARGET_MARGIN"],
            "MARGIN_RED_AT": MARGIN_RED_AT,
            "MARGIN_GREEN_AT": MARGIN_GREEN_AT,
            "margin_tier": services.margin_tier,
            "hike_pct": services.hike_pct,
        }


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/error.html", code=400, title="Bad request",
                               message=getattr(e, "description", None) or
                               "The request could not be processed."), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, title="Access denied",
                               message="You do not have permission to do that."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, title="Page not found",
                               message="The page you are looking for does not exist."), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        return render_template("errors/error.html", code=500, title="Something went wrong",
                               message="An unexpected error occurred. Please try again."), 500


def _configure_logging(app: Flask) -> None:
    if app.testing:
        return
    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(log_dir, "app.log"),
                                  maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
