from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from app.models import Settings
from app import db
import os
from app.models import Certifikat
from app.email_utils import format_date, cz_month_name, build_rows_html, wrap_email_html
from datetime import date
import calendar

bp = Blueprint('settings', __name__)


@bp.route('/nastaveni')
def index():
    # Load current settings
    settings_dict = {}
    try:
        all_settings = Settings.query.all()
        settings_dict = {s.key: s.value for s in all_settings}
    except Exception:
        pass

    report_day = os.environ.get('REPORT_DAY', '1')
    report_hour = os.environ.get('REPORT_HOUR', '9')
    report_minute = int(os.environ.get('REPORT_MINUTE', '0'))
    
    raw_envs = (current_app.config.get('REPORT_ENVS') or os.environ.get('REPORT_ENVS') or 'live,test')
    report_envs = [e.strip().lower() for e in raw_envs.split(',') if e.strip()]

    return render_template('settings.html',
                         settings=settings_dict,
                         config=current_app.config,
                         report_day=report_day,
                         report_hour=report_hour,
                         report_minute=report_minute,
                         report_envs=report_envs)


@bp.route('/nastaveni/ulozit', methods=['POST'])
def save():
    try:
        critical = request.form.get('alert_days_critical', '30')
        warning = request.form.get('alert_days_warning', '60')

        # Validate
        critical_int = max(1, min(365, int(critical)))
        warning_int = max(1, min(365, int(warning)))

        if critical_int >= warning_int:
            flash('Kritický práh musí být menší než varovný práh', 'error')
            return redirect(url_for('settings.index'))

        Settings.set('alert_days_critical', str(critical_int))
        Settings.set('alert_days_warning', str(warning_int))
        flash('Nastavení uloženo', 'success')
    except ValueError:
        flash('Neplatné hodnoty', 'error')
    except Exception as e:
        current_app.logger.error(f'Chyba při ukládání nastavení: {str(e)}')
        flash(f'Chyba: {str(e)}', 'error')

    return redirect(url_for('settings.index'))


@bp.route('/nastaveni/save-smtp', methods=['POST'])
def save_smtp():
    try:
        Settings.set('mail_server', request.form.get('mail_server', ''))
        Settings.set('mail_port', request.form.get('mail_port', ''))
        
        # Checkbox: if present 'on', else False. But request.form.get returns None if missing.
        use_tls = request.form.get('mail_use_tls') == 'on'
        Settings.set('mail_use_tls', str(use_tls))
        
        Settings.set('mail_username', request.form.get('mail_username', ''))
        Settings.set('mail_password', request.form.get('mail_password', ''))
        Settings.set('mail_sender_address', request.form.get('mail_sender_address', ''))
        
        db.session.commit()
        flash('SMTP konfigurace uložena.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Chyba při ukládání SMTP: {str(e)}')
        flash(f'Chyba při ukládání: {str(e)}', 'error')
    
    return redirect(url_for('settings.index'))
