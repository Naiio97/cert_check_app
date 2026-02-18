"""
Migrace: přidání tabulek audit_log a settings.
Spustí se automaticky při startu aplikace díky create_all().
Pro manuální spuštění: python migrate_phase3.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models import AuditLog, Settings

app = create_app()

with app.app_context():
    # Create tables in both live and test databases
    for bind in ('live', 'test'):
        try:
            engine = db.get_engine(app, bind=bind)
            # Create only new tables (won't affect existing ones)
            AuditLog.__table__.create(engine, checkfirst=True)
            Settings.__table__.create(engine, checkfirst=True)
            print(f"[{bind}] Tabulky audit_log a settings vytvořeny (nebo již existují).")
        except Exception as e:
            print(f"[{bind}] Chyba: {e}")

    # Insert default settings if not exist
    for bind in ('live', 'test'):
        from flask import g
        g.db_bind = bind
        AuditLog.__bind_key__ = bind
        Settings.__bind_key__ = bind
        try:
            defaults = {
                'alert_days_critical': '30',
                'alert_days_warning': '60',
            }
            for key, value in defaults.items():
                existing = Settings.query.filter_by(key=key).first()
                if not existing:
                    db.session.add(Settings(key=key, value=value))
            db.session.commit()
            print(f"[{bind}] Výchozí nastavení vložena.")
        except Exception as e:
            db.session.rollback()
            print(f"[{bind}] Chyba při vkládání nastavení: {e}")

print("Migrace dokončena.")
