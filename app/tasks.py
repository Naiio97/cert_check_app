from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from app import db
from datetime import datetime, date, timedelta
import os
from sqlalchemy import text
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl
import calendar

from app.models import Settings, Certifikat
from app.email_utils import format_date, cz_month_name, build_rows_html, wrap_email_html

def _engine(env: str):
    # Flask-SQLAlchemy 3.2+: používejte db.engines[bind]
    try:
        return db.engines[env]
    except Exception:
        return db.get_engine(current_app, bind=env)


def _send_email(subject: str, text_body: str, html_body: str, recipients=None):
    """Odešle email. Konfigurace: DB Settings > .env Config."""
    cfg = current_app.config

    # Načtení konfigurace (Priorita: DB > ENV)
    db_server = Settings.get('mail_server')
    db_port = Settings.get('mail_port')
    db_tls = Settings.get('mail_use_tls')  # 'True'/'False'/None
    db_user = Settings.get('mail_username')
    db_pass = Settings.get('mail_password')
    db_sender = Settings.get('mail_sender_address')

    server_host = db_server if db_server else cfg.get("MAIL_SERVER", "localhost")
    try:
        server_port = int(db_port) if db_port else int(cfg.get("MAIL_PORT", 25))
    except ValueError:
        server_port = 25

    if db_tls is not None:
        use_tls = (db_tls == 'True')
    else:
        use_tls = cfg.get("MAIL_USE_TLS")
        if isinstance(use_tls, str):
            use_tls = use_tls.lower() == 'true'
        elif not isinstance(use_tls, bool):
            use_tls = False

    username = db_user if db_user else cfg.get("MAIL_USERNAME")
    password = db_pass if db_pass else cfg.get("MAIL_PASSWORD")
    sender_addr = db_sender if db_sender else cfg.get("MAIL_SENDER_ADDRESS") or "noreply@example.com"
    sender_name = cfg.get("MAIL_SENDER_NAME") # Sender name stays in env for now? Or derived?

    if not recipients:
        recipients_raw = cfg.get("MAIL_RECIPIENTS")
        if not recipients_raw:
            current_app.logger.warning("MAIL_RECIPIENTS není nastaveno; e-mail neodeslán")
            return
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if html_body:
        msg = MIMEMultipart('alternative')
        part_text = MIMEText(text_body, 'plain', _charset='utf-8')
        part_html = MIMEText(html_body, 'html', _charset='utf-8')
        msg.attach(part_text)
        msg.attach(part_html)
    else:
        msg = MIMEText(text_body, _charset="utf-8")

    subject_prefix = cfg.get("MAIL_SUBJECT_PREFIX", "")
    msg["Subject"] = f"{subject_prefix} {subject}".strip()
    msg["From"] = f"{sender_name} <{sender_addr}>" if sender_name else sender_addr
    msg["To"] = ", ".join(recipients)

    try:
        context = ssl.create_default_context()
        current_app.logger.info(
            "SMTP odesílám: server=%s:%d, from=%s, to=%s, tls=%s, auth=%s, subject='%s'",
            server_host, server_port, sender_addr, recipients, use_tls, bool(username and password), subject
        )
        with smtplib.SMTP(server_host, server_port) as server:
            # EHLO/HELO
            server.ehlo()
            if use_tls:
                server.starttls(context=context)
                server.ehlo()
            
            if username and password:
                server.login(username, password)
            
            result = server.sendmail(sender_addr, recipients, msg.as_string())
            if result:
                current_app.logger.warning("SMTP partial failure: %s", result)
        
        current_app.logger.info("E-mail úspěšně odeslán: %s → %s (Server: %s:%d)", subject, recipients, server_host, server_port)
    except Exception as e:
        current_app.logger.error("Chyba při odesílání e-mailu (%s:%d): %s", server_host, server_port, e)



def send_daily_certificate_alert(env: str):
    """Odešle denní upozornění o certifikátech – thresholds z DB."""
    try:
        critical_days = int(Settings.get('alert_days_critical', '30'))
        warning_days = int(Settings.get('alert_days_warning', '60'))

        rows = Certifikat.fetch_expiring(env, days=warning_days)
        if not rows:
            current_app.logger.info("[%s] Žádné končící certifikáty do %d dnů", env, warning_days)
            return
        today = date.today()
        critical = [r for r in rows if (format_date(r["expirace"]) - today).days <= critical_days]
        warning = [r for r in rows if critical_days < (format_date(r["expirace"]) - today).days <= warning_days]
        # Plain text
        lines = [f"Seznam certifikátů končících do {warning_days} dnů ({env.upper()}):", ""]
        for r in rows:
            exp = format_date(r["expirace"])
            left = (exp - today).days
            mark = "! " if left <= critical_days else ""
            lines.append(f"{mark}{r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
        text_body = "\n".join(lines)

        # HTML
        table_html = build_rows_html(rows, today, critical_days)
        stats = {'critical': len(critical), 'warning': len(warning), 'total': len(rows)}
        env_upper = env.upper()
        title_color = '#dc2626' if env_upper == 'LIVE' else '#16a34a'
        html = wrap_email_html(
            title=f"[{env_upper}] Končící certifikáty do {warning_days} dnů",
            sections=[(f"Certifikáty ({len(rows)})", table_html)],
            title_color=title_color,
            stats=stats
        )
        subject = f"[{env_upper}] Končící certifikáty do {warning_days} dnů (kritické: {len(critical)})"
        _send_email(subject, text_body, html)
    except Exception as e:
        current_app.logger.error("Chyba alertu pro %s: %s", env, e)

def send_test_email(to_email: str):
    """Odešle testovací email na zadanou adresu."""
    subject = "Test nastavení emailu"
    text_body = "Toto je testovací zpráva pro ověření funkčnosti SMTP serveru."
    html_body = wrap_email_html(
        title="Test nastavení emailu",
        sections=[("Výsledek", "<p style='color: #16a34a; font-weight: bold;'>SMTP spojení je funkční.</p>")],
        title_color="#3b82f6",
        stats={'total': 1, 'critical': 0, 'warning': 0}
    )
    _send_email(subject, text_body, html_body, recipients=[to_email])

def send_monthly_certificate_report(env: str):
    """Odešle report pro aktuální i následující měsíc."""
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
    try:
        rows_cur = Certifikat.fetch_between(env, cur_start, cur_end)
        rows_next = Certifikat.fetch_between(env, next_start, next_end)

        # Vždy odeslat report (i prázdný)
        # Textová verze
        lines = [f"Report končících certifikátů ({env.upper()}):", ""]
        lines.append(f"Aktuální měsíc ({today.month}.{today.year}):")
        if rows_cur:
            for r in rows_cur:
                exp = format_date(r["expirace"]) 
                left = (exp - today).days
                lines.append(f"- {r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
        else:
            lines.append("- žádné položky")
        lines.append("")
        lines.append(f"Následující měsíc ({next_month}.{next_year}):")
        if rows_next:
            for r in rows_next:
                exp = format_date(r["expirace"]) 
                left = (exp - today).days
                lines.append(f"- {r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
        else:
            lines.append("- žádné položky")
        
        # Pokud je vše prázdné, přidáme pozitivní zprávu
        if not rows_cur and not rows_next:
            lines.append("")
            lines.append("Vše v pořádku, žádné certifikáty neexpirují.")

        text_body = "\n".join(lines)

        # HTML verze – dvě tabulky
        critical_days = int(Settings.get('alert_days_critical', '30'))
        sections = []
        cur_table = build_rows_html(rows_cur, today, critical_days) if rows_cur else '<p style="font-family:Arial,Helvetica,sans-serif;color:#94a3b8;padding:10px">Žádné položky</p>'
        next_table = build_rows_html(rows_next, today, critical_days) if rows_next else '<p style="font-family:Arial,Helvetica,sans-serif;color:#94a3b8;padding:10px">Žádné položky</p>'
        sections.append((cz_month_name(today), cur_table))
        sections.append((cz_month_name(date(next_year, next_month, 1)), next_table))
        
        env_upper = env.upper()
        # Barvy hlavičky podle prostředí: LIVE = červená, TEST/UAT = zelená
        title_color = '#dc2626' if env_upper == 'LIVE' else '#16a34a'
        stats = {'critical': len(rows_cur), 'warning': len(rows_next), 'total': len(rows_cur) + len(rows_next)}
        
        html_body = wrap_email_html(
            f"[{env_upper}] Měsíční report končících certifikátů",
            sections,
            title_color=title_color,
            stats=stats
        )

        _send_email(f"[{env.upper()}] Měsíční report (aktuální + další měsíc)", text_body, html_body)
        current_app.logger.info(
            "Report odeslán pro %s (aktuální: %d, další: %d)", env, len(rows_cur), len(rows_next)
        )

    except Exception as e:
        current_app.logger.error("Chyba při generování měsíčního reportu (%s): %s", env, e)

_app_ref = None
_scheduler_started = False


def _run_daily(env: str):
    """Wrapper pro job: zajistí application context."""
    if _app_ref is None:
        raise RuntimeError('Aplikace není inicializovaná (_app_ref is None)')
    with _app_ref.app_context():
        send_daily_certificate_alert(env)


def _run_monthly(env: str):
    """Wrapper pro job: zajistí application context."""
    if _app_ref is None:
        raise RuntimeError('Aplikace není inicializovaná (_app_ref is None)')
    with _app_ref.app_context():
        current_app.logger.info("Spouštím měsíční report pro env=%s", env)
        send_monthly_certificate_report(env)


def init_scheduler(app):
    """Inicializace plánovače úloh (idempotentní, bez duplicit)."""
    global _app_ref, _scheduler_started
    # Zabráníme spuštění v rodičovském procesu debug reloaderu
    if getattr(app, 'debug', False) and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        app.logger.info('Scheduler: přeskočeno v parent procesu (debug reloader)')
        return None
    if _scheduler_started:
        return None
    _scheduler_started = True
    _app_ref = app

    scheduler = BackgroundScheduler(daemon=True)

    # Z jakých prostředí posílat reporty: REPORT_ENVS="live" (default) nebo např. "test" či "live,test"
    raw_envs = (app.config.get('REPORT_ENVS') or os.environ.get('REPORT_ENVS') or 'live,test')
    envs = [e.strip().lower() for e in raw_envs.split(',') if e.strip()]
    # map aliases a odfiltruj neznámé hodnoty, zachovej pořadí a unikátnost
    mapped = [('test' if e in ('uat', 'test') else 'live' if e in ('live', 'prod', 'production') else None) for e in envs]
    envs = []
    for m in mapped:
        if m and m not in envs:
            envs.append(m)
    # Časy pro měsíční report (lze přepsat env proměnnami)
    month_day = int(os.environ.get('REPORT_DAY', '1'))
    month_hour = int(os.environ.get('REPORT_HOUR', '9'))
    month_minute = int(os.environ.get('REPORT_MINUTE', '0'))

    for idx, env in enumerate(envs):
        job_id = f'monthly_report_{env}'
        # Pokud je více prostředí, pošleme každé s posunem +5 min, aby nepřišly 2 e-maily současně
        adj_minute_total = month_minute + idx * 5
        adj_hour = (month_hour + (adj_minute_total // 60)) % 24
        adj_minute = adj_minute_total % 60
        scheduler.add_job(
            _run_monthly,
            'cron',
            id=job_id,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
            day=month_day,
            hour=adj_hour,
            minute=adj_minute,
            args=[env],
        )

    scheduler.start()
    when_str = ', '.join([
        f"{env}:{month_day}.{((month_hour + ((month_minute + idx*5)//60))%24):02d}:{((month_minute + idx*5)%60):02d}"
        for idx, env in enumerate(envs)
    ])
    app.logger.info("Plánovač úloh inicializován (envs=%s | %s)", ','.join(envs), when_str)
    return scheduler