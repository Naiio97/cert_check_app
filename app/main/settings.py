from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from app.models import Settings
from app import db
import os
from app.tasks import send_test_email
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


@bp.route('/nastaveni/test-email', methods=['POST'])
def test_email():
    try:
        email = request.form.get('test_email_recipient')
        if not email:
            flash('Nebyla zadána emailová adresa', 'error')
            return redirect(url_for('settings.index'))

        send_test_email(email)
        flash(f'Testovací email odeslán na {email}', 'success')
    except Exception as e:
        current_app.logger.error(f'Chyba test emailu: {str(e)}')
        flash(f'Chyba při odesílání: {str(e)}', 'error')

    return redirect(url_for('settings.index'))


@bp.route('/nastaveni/preview/alert/<env>')
def preview_alert(env):
    try:
        critical_days = int(Settings.get('alert_days_critical', '30'))
        warning_days = int(Settings.get('alert_days_warning', '60'))

        rows = Certifikat.fetch_expiring(env, days=warning_days)
        today = date.today()
        
        # If no rows, show dummy data or empty message? 
        # Better to show empty message as real preview.
        
        critical = [r for r in rows if (format_date(r["expirace"]) - today).days <= critical_days]
        warning = [r for r in rows if critical_days < (format_date(r["expirace"]) - today).days <= warning_days]
        
        table_html = build_rows_html(rows, today, critical_days) if rows else '<p style="padding:20px;text-align:center;color:#64748b">Žádné certifikáty k upozornění.</p>'
        stats = {'critical': len(critical), 'warning': len(warning), 'total': len(rows)}
        env_upper = env.upper()
        title_color = '#dc2626' if env_upper == 'LIVE' else '#16a34a'
        
        html = wrap_email_html(
            title=f"[{env_upper}] Končící certifikáty do {warning_days} dnů",
            sections=[(f"Certifikáty ({len(rows)})", table_html)],
            title_color=title_color,
            stats=stats
        )
        return html
    except Exception as e:
        return f"Chyba při generování náhledu: {str(e)}", 500


@bp.route('/nastaveni/preview/report/<env>')
def preview_report(env):
    try:
        today = date.today()
        # Rozmezí aktuálního měsíce
        _, last_day_cur = calendar.monthrange(today.year, today.month)
        cur_start = date(today.year, today.month, 1)
        cur_end = date(today.year, today.month, last_day_cur)
        # Rozmezí následujícího měsíce
        next_year = today.year + 1 if today.month == 12 else today.year
        next_month = 1 if today.month == 12 else today.month + 1
        _, last_day_next = calendar.monthrange(next_year, next_month)
        next_start = date(next_year, next_month, 1)
        next_end = date(next_year, next_month, last_day_next)

        # Reuse fetch_expiring?? No, fetch_expiring uses <= logic. Report uses BETWEEN.
        # We can reuse the engine logic from model but need custom query.
        # Ideally, we should add `fetch_between` to Certifikat model.
        # For now, I'll duplicate query logic here or add it to Certifikat model.
        # Let's add fetch_between to Certifikat model to avoid duplication.
        
        # STOP! I should not duplicate logic if I can avoid it.
        # But I'm in middle of editing settings.py.
        # I'll rely on Certifikat.fetch_between(env, start, end) which I WILL create in next step.
        
        rows_cur = Certifikat.fetch_between(env, cur_start, cur_end)
        rows_next = Certifikat.fetch_between(env, next_start, next_end)
        
        critical_days = int(Settings.get('alert_days_critical', '30'))
        sections = []
        cur_table = build_rows_html(rows_cur, today, critical_days) if rows_cur else '<p style="font-family:Arial,Helvetica,sans-serif;color:#94a3b8">Žádné položky</p>'
        next_table = build_rows_html(rows_next, today, critical_days) if rows_next else '<p style="font-family:Arial,Helvetica,sans-serif;color:#94a3b8">Žádné položky</p>'
        sections.append((cz_month_name(today), cur_table))
        sections.append((cz_month_name(date(next_year, next_month, 1)), next_table))
        
        env_upper = env.upper()
        title_color = '#dc2626' if env_upper == 'LIVE' else '#16a34a'
        stats = {'critical': len(rows_cur), 'warning': len(rows_next), 'total': len(rows_cur) + len(rows_next)}
        
        html = wrap_email_html(
            f"[{env_upper}] Měsíční report končících certifikátů",
            sections,
            title_color=title_color,
            stats=stats
        )
        return html
    except Exception as e:
        return f"Chyba při generování náhledu: {str(e)}", 500
