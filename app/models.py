from app import db
from datetime import datetime, timezone, date
from sqlalchemy import text
from flask import current_app


class Server(db.Model):
    __bind_key__ = 'live'
    id = db.Column(db.Integer, primary_key=True)
    nazev = db.Column(db.String(100), unique=True, nullable=False)
    popis = db.Column(db.Text)
    vytvoreno = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Certifikat(db.Model):
    __bind_key__ = 'live'
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(100), db.ForeignKey('server.nazev'), nullable=False)
    cesta = db.Column(db.String(200), nullable=False)
    nazev = db.Column(db.String(100), nullable=False)
    expirace = db.Column(db.Date, nullable=False)
    poznamka = db.Column(db.Text, nullable=True)
    vytvoreno = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def fetch_expiring(env: str, days: int = 60):
        """Vrátí list záznamů z tabulky certifikat pro dané prostředí do N dnů."""
        # Flask-SQLAlchemy 3.2+: používejte db.engines[bind]
        try:
            engine = db.engines[env]
        except Exception:
            engine = db.get_engine(current_app, bind=env)

        today = date.today()
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT server, cesta, nazev, expirace
                    FROM certifikat
                    WHERE date(expirace) <= date(:today, :plus)
                    ORDER BY expirace ASC
                    """
                ),
                {"today": today.isoformat(), "plus": f"+{days} day"},
            ).mappings().all()
        return rows

    @staticmethod
    def fetch_between(env: str, start_date: date, end_date: date):
        """Vrátí list záznamů expirujících v daném rozmezí."""
        try:
            engine = db.engines[env]
        except Exception:
            engine = db.get_engine(current_app, bind=env)

        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT server, cesta, nazev, expirace
                    FROM certifikat
                    WHERE date(expirace) BETWEEN date(:start) AND date(:end)
                    ORDER BY expirace ASC
                    """
                ),
                {"start": start_date.isoformat(), "end": end_date.isoformat()},
            ).mappings().all()
        return rows


class AuditLog(db.Model):
    __bind_key__ = 'live'
    id = db.Column(db.Integer, primary_key=True)
    akce = db.Column(db.String(20), nullable=False)       # pridano / upraveno / smazano
    certifikat_nazev = db.Column(db.String(100))
    server = db.Column(db.String(100))
    detail = db.Column(db.Text)                           # JSON or free text
    uzivatel = db.Column(db.String(100))                  # kdo změnu provedl (doménový účet / lokální admin)
    cas = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Settings(db.Model):
    __bind_key__ = 'live'
    # Konfigurace je společná pro všechna prostředí — RoutingSession ji vždy
    # směruje do live DB, i když má uživatel v UI přepnuté jiné prostředí.
    __global_table__ = True
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=False)

    @staticmethod
    def get(key, default=None):
        """Get a setting value by key, with optional default."""
        s = Settings.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key, value):
        """Set a setting value (insert or update)."""
        s = Settings.query.filter_by(key=key).first()
        if s:
            s.value = str(value)
        else:
            s = Settings(key=key, value=str(value))
            db.session.add(s)
        db.session.commit() 

class User(db.Model):
    """Uživatel aplikace. Identita přichází z Windows autentizace (IIS), role přiděluje admin."""
    __bind_key__ = 'live'
    # Uživatelé jsou společní pro všechna prostředí — RoutingSession je vždy směruje do live DB.
    __global_table__ = True

    __tablename__ = 'app_user'

    ROLES = ('pending', 'viewer', 'editor', 'admin')

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)   # normalizovaně malými písmeny
    display_name = db.Column(db.String(100))                            # jak se účet přihlásil (DOMENA\\jmeno)
    role = db.Column(db.String(20), nullable=False, default='pending')
    active = db.Column(db.Boolean, nullable=False, default=True)
    vytvoreno = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    posledni_aktivita = db.Column(db.DateTime)

    @property
    def label(self):
        return self.display_name or self.username
