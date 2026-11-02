"""Flask extension instances (initialised in the app factory)."""
from flask_caching import Cache
from flask_compress import Compress
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
compress = Compress()
login_manager = LoginManager()
cache = Cache()
