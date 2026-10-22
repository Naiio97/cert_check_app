from flask import Flask, g, request, current_app
from flask_sqlalchemy import SQLAlchemy
from config import Config
import logging
import os
from datetime import datetime
from app.utils import get_expiry_class
from app.filters import days_until_expiry
from flask_sqlalchemy.session import Session as _FsaSession

class RoutingSession(_FsaSession):
    """Směruje ORM operace na bind podle cookie env (live/test)."""
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        # Globální tabulky (Settings) jdou vždy do live DB bez ohledu na cookie —
        # scheduler a joby čtou mimo request context, takže by konfiguraci
        # uloženou v jiném prostředí nikdy neviděly.
        cls = getattr(mapper, 'class_', None) if mapper is not None else None
        if cls is not None and getattr(cls, '__global_table__', False):
            return db.get_engine(current_app, bind='live')
        env = getattr(g, 'db_bind', None)
        if env in ('live', 'uat', 'sit', 'prelive'):
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
    if app.debug:
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

    from app.main.uzivatele import bp as uzivatele_bp
    app.register_blueprint(uzivatele_bp, url_prefix='/evidence_certifikatu')

    from app.auth import bp as auth_bp, enforce_auth
    app.register_blueprint(auth_bp, url_prefix='/evidence_certifikatu')

    def _expiring_count(env):
        # Počet certifikátů, které už vypršely nebo vyprší do 'alert_days_warning' dnů —
        # číslo ve štítku u položky "Končící certifikáty" v horní liště.
        try:
            from app.models import Certifikat, Settings
            warning_days = int(Settings.get('alert_days_warning', '60'))
            return len(Certifikat.fetch_expiring(env, days=warning_days))
        except Exception:
            return 0

    @app.context_processor
    def inject_env():
        env = getattr(g, 'db_bind', 'live')
        return {
            'current_env': env,
            'is_live':    env == 'live',
            'is_uat':     env == 'uat',
            'is_sit':     env == 'sit',
            'is_prelive': env == 'prelive',
            'expiring_count': _expiring_count(env),
        }

    @app.before_request
    def select_db_bind():
        # Zvolené prostředí z cookie (live/test), výchozí live
        # RoutingSession.get_bind() čte g.db_bind per-request — thread-safe
        env = request.cookies.get('env') or 'live'
        if env not in ('live', 'uat', 'sit', 'prelive'):
            env = 'live'
        g.db_bind = env

    # Kontrola přihlášení a rolí běží až po výběru prostředí
    app.before_request(enforce_auth)

    @app.after_request
    def no_store(response):
        # Stránky a JSON z aplikace se nikdy necachují — po smazání nebo změně (tlačítko Zpět,
        # přepnutí stránky) tak prohlížeč vždy načte aktuální data, ne starou kopii. Statické soubory se cachují.
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    if app.config['AUTH_ENABLED'] and app.config['SECRET_KEY'] == 'fallback-zmenit-v-produkci' and not app.debug:
        app.logger.warning('SECRET_KEY není nastaven v .env — přihlášení lokálního admina používá výchozí klíč!')
    if not app.config['AUTH_ENABLED']:
        app.logger.warning('AUTH_ENABLED=false — aplikace běží BEZ přihlášení, každý návštěvník je admin!')

    

    # Nastavení pokročilého logování (musí být před schedulerem, aby se logy zachytily)
    from app.logging_config import setup_ultimate_logging
    setup_ultimate_logging(app)

    # Registrace error handlerů
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # Spustíme plánovač úloh
    try:
        from app.tasks import init_scheduler
        init_scheduler(app)
    except Exception:
        # exc_info nutné — bez tracebacku nejde poznat, PROČ scheduler
        # nenastartoval (a reporty pak tiše nechodí)
        app.logger.error('Nepodařilo se inicializovat plánovač úloh', exc_info=True)

    return app
