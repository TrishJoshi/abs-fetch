import os
import psycopg2
from flask import g
import logging

def get_db():
    if 'db' not in g:
        db_conn_str = os.getenv("DB_CONNECTION_STRING")
        if not db_conn_str:
            logging.error("DB_CONNECTION_STRING environment variable not set.")
            raise RuntimeError("DB_CONNECTION_STRING environment variable not set.")
        g.db = psycopg2.connect(db_conn_str)
    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)
