from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from sqlalchemy import case

from app import db
from app.auth import role_required, ROLE_LABELS, current_username
from app.models import User

bp = Blueprint('uzivatele', __name__)

ASSIGNABLE_ROLES = ('viewer', 'editor', 'admin')


def _active_admins():
    return User.query.filter_by(role='admin', active=True).count()


def _would_remove_last_admin(user, new_role, new_active):
    """Nesmí se přijít o posledního aktivního admina (jinak by správa uživatelů zůstala bez ovládání)."""
    if user.role != 'admin' or not user.active:
        return False
    if new_role == 'admin' and new_active:
        return False
    return _active_admins() <= 1


@bp.route('/uzivatele')
@role_required('admin')
def index():
    users = User.query.order_by(
        case((User.role == 'pending', 0), else_=1), User.username
    ).all()
    return render_template('uzivatele.html', users=users, roles=ASSIGNABLE_ROLES)


@bp.route('/uzivatele/pridat', methods=['POST'])
@role_required('admin')
def pridat():
    login = (request.form.get('username') or '').strip()
    role = request.form.get('role', 'viewer')
    if not login or role not in ASSIGNABLE_ROLES:
        flash('Zadejte doménový účet (např. DOMENA\\jmeno) a roli.', 'error')
        return redirect(url_for('uzivatele.index'))
    key = login.lower()
    if User.query.filter_by(username=key).first():
        flash(f'Uživatel {login} už existuje.', 'error')
        return redirect(url_for('uzivatele.index'))
    db.session.add(User(username=key, display_name=login[:100], role=role, active=True))
    db.session.commit()
    current_app.logger.info('%s přidal uživatele %s (role: %s)', current_username(), login, role)
    flash(f'Uživatel {login} byl přidán.', 'success')
    return redirect(url_for('uzivatele.index'))


@bp.route('/uzivatele/<int:id>/ulozit', methods=['POST'])
@role_required('admin')
def ulozit(id):
    user = User.query.get_or_404(id)
    role = request.form.get('role', user.role)
    active = request.form.get('active') == 'on'
    if role not in User.ROLES or (role == 'pending' and user.role != 'pending'):
        flash('Neplatná role.', 'error')
        return redirect(url_for('uzivatele.index'))
    if _would_remove_last_admin(user, role, active):
        flash('Nelze odebrat práva ani zablokovat posledního administrátora.', 'error')
        return redirect(url_for('uzivatele.index'))
    user.role, user.active = role, active
    db.session.commit()
    current_app.logger.info('%s změnil uživatele %s: role=%s, aktivní=%s', current_username(), user.label, role, active)
    flash(f'Uživatel {user.label} uložen ({ROLE_LABELS.get(role, role)}{"" if active else ", zablokován"}).', 'success')
    return redirect(url_for('uzivatele.index'))


@bp.route('/uzivatele/<int:id>/smazat', methods=['POST'])
@role_required('admin')
def smazat(id):
    user = User.query.get_or_404(id)
    if _would_remove_last_admin(user, 'none', False):
        flash('Nelze smazat posledního administrátora.', 'error')
        return redirect(url_for('uzivatele.index'))
    label = user.label
    db.session.delete(user)
    db.session.commit()
    current_app.logger.info('%s smazal uživatele %s', current_username(), label)
    flash(f'Uživatel {label} byl smazán. Při dalším přihlášení bude znovu čekat na schválení.', 'success')
    return redirect(url_for('uzivatele.index'))
