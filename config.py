import os
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

class Config:
    APPLICATION_ROOT = '/evidence_certifikatu'
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-zmenit-v-produkci'
    # Databáze: výchozí live + bindy pro live/test
    SQLALCHEMY_BINDS = {
        'live':    'sqlite:///certifikaty.db',
        'uat':     'sqlite:///certifikaty_uat.db',
        'sit':     'sqlite:///certifikaty_sit.db',
        'prelive': 'sqlite:///certifikaty_prelive.db',
    }
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_BINDS['live']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Konfigurace pro upload souborů
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    
    # Email konfigurace (lze přepsat env proměnnými)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'tsmtp03.test.cz')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '25'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_SMTP_AUTH = os.environ.get('MAIL_SMTP_AUTH', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_SENDER_ADDRESS = os.environ.get('MAIL_SENDER_ADDRESS', 'test@test.cz')
    MAIL_SENDER_NAME = os.environ.get('MAIL_SENDER_NAME', 'TEST a.s.')
    MAIL_SUBJECT_PREFIX = os.environ.get('MAIL_SUBJECT_PREFIX', 'Test a.s.')
    MAIL_RECIPIENTS = os.environ.get('MAIL_RECIPIENTS', 'test@test.cz')
    # Adresa aplikace pro tlačítko "Otevřít evidenci certifikátů" v e-mailech (prázdné = bez tlačítka)
    APP_URL = os.environ.get('APP_URL', '')

    # ── Autentizace ──
    # Zapnuto vždy, vypnout lze jen vědomě (AUTH_ENABLED=false) — pak je každý návštěvník admin.
    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'true').lower() != 'false'
    # Hlavičku s doménovým účtem nastavuje IIS (Windows autentizace) a důvěřujeme jí
    # jen z adres v AUTH_TRUSTED_PROXIES (výchozí: reverzní proxy na stejném serveru).
    AUTH_REMOTE_USER_HEADER = os.environ.get('AUTH_REMOTE_USER_HEADER', 'X-Remote-User')
    AUTH_TRUSTED_PROXIES = [a.strip() for a in os.environ.get('AUTH_TRUSTED_PROXIES', '127.0.0.1,::1').split(',') if a.strip()]
    # Účty, které jsou vždy admin (čárkou oddělené, např. PMB\\jnovak,PMB\\ibadmin) — pro první nastavení.
    ADMIN_USERS = [a.strip().lower() for a in os.environ.get('ADMIN_USERS', '').split(',') if a.strip()]
    # Lokální záložní admin pro případ, že SSO nefunguje (hash: viz DEPLOY.md). Bez hashe je vypnutý.
    LOCAL_ADMIN_USER = os.environ.get('LOCAL_ADMIN_USER', 'admin')
    LOCAL_ADMIN_PASSWORD_HASH = os.environ.get('LOCAL_ADMIN_PASSWORD_HASH', '')
    # Pouze pro vývoj bez IIS: simulovaný doménový účet pro požadavky z localhostu.
    AUTH_DEV_USER = os.environ.get('AUTH_DEV_USER', '')
    
    # Vytvoření potřebných složek
    @staticmethod
    def init_app(app):
        # Vytvoříme složku pro uploady
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER']) 
        # Volitelné: načtení SMTP z XML (compat s jinou aplikací)
        # Očekávaná struktura:
        # <configuration><mail><host>...</host><port>25</port><username/><password/>
        # <smtpAuth>false</smtpAuth><startTlsEnabled>false</startTlsEnabled>
        # <startTlsRequired>false</startTlsRequired><senderAddress>...</senderAddress>
        # <senderName>...</senderName><subject>...</subject></mail></configuration>
        xml_path = os.environ.get('MAIL_CONFIG_XML')
        if not xml_path:
            # pokusíme se najít v instance/config.xml
            candidate = os.path.join(os.getcwd(), 'instance', 'config.xml')
            if os.path.exists(candidate):
                xml_path = candidate
            else:
                candidate = os.path.join(os.getcwd(), 'config.xml')
                if os.path.exists(candidate):
                    xml_path = candidate
        if xml_path and os.path.exists(xml_path):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                mail = root.find('.//mail')
                if mail is not None:
                    def g(tag, default=''):
                        el = mail.find(tag)
                        return (el.text or '').strip() if el is not None and el.text is not None else default
                    app.config['MAIL_SERVER'] = g('host', app.config.get('MAIL_SERVER'))
                    port = g('port', str(app.config.get('MAIL_PORT', 25)))
                    try:
                        app.config['MAIL_PORT'] = int(port)
                    except ValueError:
                        pass
                    app.config['MAIL_USERNAME'] = g('username', app.config.get('MAIL_USERNAME', ''))
                    app.config['MAIL_PASSWORD'] = g('password', app.config.get('MAIL_PASSWORD', ''))
                    smtp_auth = g('smtpAuth', 'false').lower() == 'true'
                    app.config['MAIL_SMTP_AUTH'] = smtp_auth
                    starttls_enabled = g('startTlsEnabled', 'false').lower() == 'true'
                    starttls_required = g('startTlsRequired', 'false').lower() == 'true'
                    app.config['MAIL_USE_TLS'] = starttls_enabled or starttls_required
                    app.config['MAIL_SENDER_ADDRESS'] = g('senderAddress', app.config.get('MAIL_SENDER_ADDRESS', ''))
                    app.config['MAIL_SENDER_NAME'] = g('senderName', app.config.get('MAIL_SENDER_NAME', ''))
                    app.config['MAIL_SUBJECT_PREFIX'] = g('subject', app.config.get('MAIL_SUBJECT_PREFIX', ''))
            except Exception:
                # Ignorujeme chyby načtení a ponecháme defaulty
                pass