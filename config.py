"""Application configuration classes (Development / Production)."""
import os
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _build_db_uri() -> str:
    """Build the SQLAlchemy URI from DB_* env vars (or DATABASE_URL override)."""
    override = os.environ.get("DATABASE_URL")
    if override:
        return override
    user = quote_plus(os.environ.get("DB_USER", "root"))
    password = quote_plus(os.environ.get("DB_PASSWORD", ""))
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "WARS")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


def _engine_options() -> dict:
    """Pool settings (section 11) plus optional SSL."""
    opts = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": False,
        "pool_recycle": 280,
        "connect_args": {
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        },
    }
    uri = _build_db_uri()
    if uri.startswith("mysql"):
        ssl_ca = os.environ.get("DB_SSL_CA")
        if ssl_ca:
            opts["connect_args"]["ssl"] = {"ca": ssl_ca}
    else:
        # SQLite (tests only) does not accept pool_size / max_overflow.
        opts = {"pool_pre_ping": True}
    return opts


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key")
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Margin target used for the 'Healthy / Below target / Deficit' tiers (percent)
    TARGET_MARGIN = Decimal(os.environ.get("TARGET_MARGIN", "22"))

    # n8n script generation: the workflow's webhook and the Drive folder the
    # two PDFs are uploaded into. Both are required before a script can be
    # requested; an empty URL raises instead of silently doing nothing.
    N8N_SCRIPT_WEBHOOK_URL = os.environ.get("N8N_SCRIPT_WEBHOOK_URL", "")
    N8N_DRIVE_FOLDER_ID = os.environ.get("N8N_DRIVE_FOLDER_ID", "")
    N8N_WEBHOOK_TIMEOUT = int(os.environ.get("N8N_WEBHOOK_TIMEOUT", "15"))

    # Static caching (1 year; use ?v= query for busting)
    SEND_FILE_MAX_AGE_DEFAULT = 31536000

    # Compression
    COMPRESS_MIMETYPES = [
        "text/html", "text/css", "text/plain", "application/json",
        "application/javascript", "text/javascript", "image/svg+xml",
    ]
    COMPRESS_MIN_SIZE = 500

    # Flask-Caching: simple in-memory cache for dev, Redis for prod
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL", "redis://localhost:6379/0")

    WTF_CSRF_TIME_LIMIT = 7200
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    PAGE_SIZES = (10, 20, 50)
    DEFAULT_PAGE_SIZE = 20


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


def get_config():
    env = os.environ.get("FLASK_ENV", "Development").strip().lower()
    return ProductionConfig if env == "production" else DevelopmentConfig
