"""Gunicorn configuration. Run: gunicorn -c gunicorn.conf.py wsgi:app"""
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 1
timeout = 60
keepalive = 5
accesslog = "logs/gunicorn-access.log"
errorlog = "logs/gunicorn-error.log"
loglevel = "info"
