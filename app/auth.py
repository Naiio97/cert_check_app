"""Autentizace a role.

Identitu uživatele dodává IIS (Windows autentizace) v hlavičce AUTH_REMOTE_USER_HEADER;
hlavičce se věří jen z AUTH_TRUSTED_PROXIES. Role (viewer / editor / admin) přiděluje admin
v aplikaci. Pro případ nedostupnosti SSO existuje lokální záložní admin (heslo v .env jako hash).
"""
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import (Blueprint, request, g, session, redirect, url_for, render_template,
                   current_app, jsonify, has_request_context)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash

from app import db
from app.models import User

ROLE_ORDER = {'pending': 0, 'viewer': 1, 'editor': 2, 'admin': 3}
ROLE_LABELS = {
    'pending': 'Čeká na schválení',
    'viewer': 'Prohlížení',
    'editor': 'Úpravy',
    'admin': 'Administrátor',
}

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
OPEN_ENDPOINTS = ('auth.login', 'auth.logout')
LOCAL_ADDRESSES = ('127.0.0.1', '::1')

# Ochrana před hádáním hesla lokálního admina: max. pokusů za okno, per IP (v paměti procesu).
LOGIN_MAX_FAILS = 5
LOGIN_WINDOW_SECONDS = 600
_login_fails = {}

bp = Blueprint('auth', __name__)


class AuthUser:
    """Přihlášený uživatel pro aktuální požadavek."""

    def __init__(self, username, label, role, active=True, is_local=False):
        self.username = username
        self.label = label
        self.role = role
        self.active = active
        self.is_local = is_local

    @property
    def short_name(self):
        """Jméno bez domény (PMB\\jnovak → jnovak)."""
        return self.label.split('\\')[-1]

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    def can(self, min_role):
        return self.active and ROLE_ORDER.get(self.role, 0) >= ROLE_ORDER[min_role]


def role_required(min_role):
    """Označí endpoint minimální rolí. Vynucuje ji globální kontrola enforce_auth()
    (endpointy bez označení vyžadují alespoň roli viewer)."""
    def decorator(func):
        func._min_role = min_role
        return func
    return decorator


def current_username():
    """Kdo provádí změnu — pro záznam v historii. Mimo požadavek (scheduler) 'systém'."""
    user = getattr(g, 'user', None) if has_request_context() else None
    return (user.label if user else 'systém')[:100]


# ─── Zjištění identity ───

def _remote_login():
    """Doménový účet z hlavičky od důvěryhodné proxy (nebo vývojový účet z localhostu)."""
    cfg = current_app.config
    addr = request.remote_addr
    if addr in cfg['AUTH_TRUSTED_PROXIES']:
        value = (request.headers.get(cfg['AUTH_REMOTE_USER_HEADER']) or '').strip()
        if value and value.upper() != 'NT AUTHORITY\\ANONYMOUS LOGON':
            return value
    if cfg['AUTH_DEV_USER'] and addr in LOCAL_ADDRESSES:
        return cfg['AUTH_DEV_USER']
    return None


def _user_from_login(login):
    cfg = current_app.config
    key = login.lower()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_env_admin = key in cfg['ADMIN_USERS']

    user = User.query.filter_by(username=key).first()
    if user is None:
        user = User(username=key, display_name=login[:100],
                    role='admin' if is_env_admin else 'pending', active=True,
                    posledni_aktivita=now)
        db.session.add(user)
        try:
            db.session.commit()
            current_app.logger.info('Nový uživatel %s (role: %s)', login, user.role)
        except IntegrityError:
            db.session.rollback()  # souběžný první požadavek stejného uživatele
            user = User.query.filter_by(username=key).first()
    else:
        changed = False
        if is_env_admin and (user.role != 'admin' or not user.active):
            user.role, user.active, changed = 'admin', True, True
        if user.display_name != login[:100]:
            user.display_name, changed = login[:100], True
        if user.posledni_aktivita is None or now - user.posledni_aktivita > timedelta(minutes=5):
            user.posledni_aktivita, changed = now, True
        if changed:
            db.session.commit()
    return AuthUser(user.username, user.label, user.role, active=user.active)


def _identify():
    cfg = current_app.config
    if not cfg['AUTH_ENABLED']:
        return AuthUser('anonymous', 'Bez přihlášení', 'admin', is_local=True)
    if session.get('local_admin') and cfg['LOCAL_ADMIN_PASSWORD_HASH']:
        name = cfg['LOCAL_ADMIN_USER']
        return AuthUser(name.lower(), f'{name} (lokální)', 'admin', is_local=True)
    login = _remote_login()
    return _user_from_login(login) if login else None


# ─── Globální kontrola přístupu ───

def _wants_html():
    return request.method == 'GET' and request.accept_mimetypes.accept_html


def _deny(status, message, user=None):
    if _wants_html():
        return render_template('access_denied.html', message=message, status=status,
                               user=user), status
    return jsonify({'success': False, 'message': message, 'error': message}), status


def enforce_auth():
    endpoint = request.endpoint
    if endpoint is None or endpoint == 'static':
        return None
    g.user = None

    # Windows přihlášení posílá prohlížeč automaticky — cizí stránka by mohla vyvolat změnu.
    # Moderní prohlížeče proto u cross-site požadavků označí Sec-Fetch-Site, takové změny odmítneme.
    if request.method not in SAFE_METHODS:
        site = request.headers.get('Sec-Fetch-Site')
        if site and site not in ('same-origin', 'none'):
            current_app.logger.warning('Zamítnut cross-site požadavek: %s %s (%s)', request.method, request.path, site)
            return _deny(403, 'Požadavek z cizí stránky byl zamítnut.')

    user = _identify()
    g.user = user
    if endpoint in OPEN_ENDPOINTS:
        return None

    if user is None:
        if _wants_html():
            return redirect(url_for('auth.login', next=request.full_path.rstrip('?')))
        return _deny(401, 'Nejste přihlášen.')

    if not user.active:
        return _deny(403, 'Váš účet byl zablokován. Obraťte se na administrátora.', user)
    if user.role == 'pending':
        return _deny(403, 'Přístup zatím nebyl schválen. Požádejte administrátora o přidělení role.', user)

    need = getattr(current_app.view_functions.get(endpoint), '_min_role', 'viewer')
    if not user.can(need):
        current_app.logger.warning('Odepřen přístup: %s (%s) → %s %s (vyžaduje %s)',
                                   user.label, user.role, request.method, request.path, need)
        return _deny(403, 'K této akci nemáte oprávnění.', user)
    return None


@bp.app_context_processor
def inject_user():
    user = getattr(g, 'user', None)
    return {
        'current_user': user,
        'can': (lambda role: bool(user and user.can(role))),
        'role_labels': ROLE_LABELS,
        'local_admin_enabled': bool(current_app.config['LOCAL_ADMIN_PASSWORD_HASH']),
    }


# ─── Přihlášení lokálním adminem ───

def _is_throttled(ip):
    now = time.time()
    recent = [t for t in _login_fails.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    _login_fails[ip] = recent
    return len(recent) >= LOGIN_MAX_FAILS


def _safe_next(target):
    """Přesměrování jen na relativní adresu v rámci aplikace."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith('/'):
        return None
    return target


@bp.route('/login', methods=['GET', 'POST'])
def login():
    cfg = current_app.config
    # Uživatel přihlášený přes SSO se na formulář dostane jen výslovně (?local=1 z menu) —
    # přihlášením lokálním adminem se pak přepne na admin účet, odhlášením zpět na SSO.
    signed_in = g.user is not None and g.user.active and g.user.role != 'pending'
    wants_local = bool(request.args.get('local')) and not (g.user is not None and g.user.is_local)
    if signed_in and request.method == 'GET' and not wants_local:
        return redirect(_safe_next(request.args.get('next')) or url_for('main.index'))

    local_enabled = bool(cfg['LOCAL_ADMIN_PASSWORD_HASH'])
    error = None
    if request.method == 'POST' and local_enabled:
        ip = request.remote_addr
        if _is_throttled(ip):
            error = 'Příliš mnoho neúspěšných pokusů. Zkuste to za několik minut.'
        else:
            name = (request.form.get('username') or '').strip()
            password = request.form.get('password') or ''
            if (name.lower() == cfg['LOCAL_ADMIN_USER'].lower()
                    and check_password_hash(cfg['LOCAL_ADMIN_PASSWORD_HASH'], password)):
                session.clear()
                session['local_admin'] = True
                current_app.logger.info('Přihlášen lokální admin z %s', ip)
                return redirect(_safe_next(request.form.get('next')) or url_for('main.index'))
            _login_fails.setdefault(ip, []).append(time.time())
            current_app.logger.warning('Neúspěšné přihlášení lokálního admina z %s', ip)
            time.sleep(1)
            error = 'Neplatné jméno nebo heslo.'
    sso_user = g.user.label if (g.user is not None and not g.user.is_local) else None
    return render_template('login.html', local_enabled=local_enabled, error=error,
                           next=_safe_next(request.args.get('next')) or '', sso_user=sso_user)


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
