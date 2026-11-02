"""WSGI entry point.

Gunicorn:  gunicorn -c gunicorn.conf.py wsgi:app
Flask CLI: flask --app wsgi run          (port from FLASK_RUN_PORT, default 5001)
Direct:    python wsgi.py                (same FLASK_RUN_PORT)
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(port=int(os.getenv("FLASK_RUN_PORT", "5001")))
