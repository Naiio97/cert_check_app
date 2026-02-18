from app import db
from datetime import datetime, timezone

class Server(db.Model):
    __bind_key__ = None  # bude nastaveno za běhu
    id = db.Column(db.Integer, primary_key=True)
    nazev = db.Column(db.String(100), unique=True, nullable=False)
    popis = db.Column(db.Text)
    vytvoreno = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Certifikat(db.Model):
    __bind_key__ = None  # bude nastaveno za běhu
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(100), db.ForeignKey('server.nazev'), nullable=False)
    cesta = db.Column(db.String(200), nullable=False)
    nazev = db.Column(db.String(100), nullable=False)
    expirace = db.Column(db.Date, nullable=False)
    poznamka = db.Column(db.Text, nullable=True)
    vytvoreno = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc)) 