"""Založení tabulek a drobné migrace schématu ve všech prostředích (live, uat, sit, prelive)."""
from sqlalchemy import inspect, text
from flask import current_app

from app import db

ENVS = ('live', 'uat', 'sit', 'prelive')

# (tabulka, sloupec, definice) — create_all nové sloupce do existujících tabulek nepřidá
NEW_COLUMNS = [
    ('audit_log', 'uzivatel', 'VARCHAR(100)'),
]


def _engine(env):
    try:
        return db.engines[env]
    except Exception:
        return db.get_engine(current_app, bind=env)


def _ensure_columns(engine):
    inspector = inspect(engine)
    for table, column, definition in NEW_COLUMNS:
        if not inspector.has_table(table):
            continue
        if column in {c['name'] for c in inspector.get_columns(table)}:
            continue
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {definition}'))
        current_app.logger.info('DB migrace: %s.%s přidán', table, column)


def init_databases(app, report=None):
    """Vytvoří chybějící tabulky a sloupce ve všech prostředích. Chyba jednoho prostředí ostatní nezastaví."""
    with app.app_context():
        # Modely mají __bind_key__ = 'live', takže jsou registrované v db.metadatas['live'];
        # stejné schéma chceme i v uat/sit/prelive.
        meta = db.metadatas.get('live') if hasattr(db, 'metadatas') else db.metadata
        for env in ENVS:
            try:
                engine = _engine(env)
                meta.create_all(bind=engine)
                _ensure_columns(engine)
                app.logger.info('DB init OK: %s', env)
                if report:
                    report(env, True, None)
            except Exception as e:
                app.logger.warning('DB init selhalo pro %s: %s', env, e)
                if report:
                    report(env, False, e)
