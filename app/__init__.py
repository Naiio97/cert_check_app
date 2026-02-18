from flask import Flask, g, request, current_app
from flask_sqlalchemy import SQLAlchemy
from config import Config
from logging.handlers import RotatingFileHandler
import logging
import os
from datetime import datetime
from app.utils import get_expiry_class
from app.filters import days_until_expiry
from flask_sqlalchemy.session import Session as _FsaSession

class RoutingSession(_FsaSession):
    """Směruje ORM operace na bind podle cookie env (live/test)."""
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        env = getattr(g, 'db_bind', None)
        if env in ('live', 'test'):
            return db.get_engine(current_app, bind=env)
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)

db = SQLAlchemy(session_options={"class_": RoutingSession})

def create_app(config_class=Config):
    # Auto-detekce složky pro statická aktiva: podporujeme "static" i "statics"
    # a zarovnáme URL pod APPLICATION_ROOT (např. /evidence_certifikatu/static)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    url_prefix = getattr(config_class, 'APPLICATION_ROOT', '') or ''
    if url_prefix.endswith('/') and len(url_prefix) > 1:
        url_prefix = url_prefix[:-1]

    statics_candidate = os.path.join(base_dir, 'statics')
    if os.path.isdir(statics_candidate):
        static_url_path = f"{url_prefix}/statics" if url_prefix else '/statics'
        static_folder = '../statics'
    else:
        static_url_path = f"{url_prefix}/static" if url_prefix else '/static'
        static_folder = '../static'

    app = Flask(__name__,
                static_url_path=static_url_path,
                static_folder=static_folder)
    app.config.from_object(config_class)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Vypnout automatické přidávání lomítka
    app.url_map.strict_slashes = False
    
    # Inicializace databáze
    db.init_app(app)
    
    # Registrace filteru
    app.jinja_env.filters['get_expiry_class'] = get_expiry_class
    app.jinja_env.filters['days_until_expiry'] = days_until_expiry
    
    # Registrace blueprintů
    from app.main.routes import bp as main_bp
    app.register_blueprint(main_bp, url_prefix='/evidence_certifikatu')
    
    from app.certificates.routes import bp as certificates_bp
    app.register_blueprint(certificates_bp, url_prefix='/evidence_certifikatu')
    
    from app.servers.routes import bp as servers_bp
    app.register_blueprint(servers_bp, url_prefix='/evidence_certifikatu')
    
    from app.main.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/evidence_certifikatu')

    from app.main.historie import bp as historie_bp
    app.register_blueprint(historie_bp, url_prefix='/evidence_certifikatu')

    from app.main.settings import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/evidence_certifikatu')

    @app.context_processor
    def inject_env():
        env = getattr(g, 'db_bind', 'live')
        return {
            'current_env': env,
            'is_live': env == 'live',
            'is_test': env == 'test'
        }

    @app.before_request
    def select_db_bind():
        # Zvolené prostředí z cookie (live/test), výchozí live
        env = request.cookies.get('env') or 'live'
        if env not in ('live', 'test'):
            env = 'live'
        g.db_bind = env
        # Nastavíme bind pro ORM modely podle zvoleného prostředí
        try:
            from app.models import Server, Certifikat, AuditLog, Settings
            Server.__bind_key__ = env
            Certifikat.__bind_key__ = env
            AuditLog.__bind_key__ = env
            Settings.__bind_key__ = env
        except Exception:
            pass
    

    # Spustíme plánovač úloh (lazy import kvůli cyklickým závislostem)
    try:
        from app.tasks import init_scheduler
        init_scheduler(app)
    except Exception:
        app.logger.warning('Nepodařilo se inicializovat plánovač úloh')
    
    # Nastavení pokročilého logování
    from app.logging_config import setup_ultimate_logging
    setup_ultimate_logging(app)
    
    return app
