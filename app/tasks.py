from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from app import db
from datetime import datetime, date, timedelta
import os
from sqlalchemy import text
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
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
    """Odešle email. Konfigurace: DB Settings > .env Config. Vrací True při úspěchu."""
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
            return False
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
    # Chybějící Date a Message-ID jsou silné spam/phishing signály (Exchange
    # Online je vyhodnocuje v composite authentication) — smtplib je sám nedoplní.
    msg["Date"] = formatdate(localtime=True)
    sender_domain = sender_addr.split('@')[-1] if '@' in sender_addr else None
    msg["Message-ID"] = make_msgid(domain=sender_domain)
    msg["Reply-To"] = sender_addr
    # Deklarace automaticky generované zprávy (RFC 3834) — filtry pak mail
    # posuzují jako systémovou notifikaci, ne jako pokus o konverzaci.
    msg["Auto-Submitted"] = "auto-generated"
    msg["X-Auto-Response-Suppress"] = "All"

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
        return True
    except Exception as e:
        current_app.logger.error("Chyba při odesílání e-mailu (%s:%d): %s", server_host, server_port, e)
        return False



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
    """Odešle report: vypršelé + aktuální měsíc + následující měsíc."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    # Rozmezí aktuálního měsíce
    cur_start = date(today.year, today.month, 1)
    _, last_day_cur = calendar.monthrange(today.year, today.month)
    cur_end = date(today.year, today.month, last_day_cur)
    # Rozmezí následujícího měsíce
    next_year = today.year + 1 if today.month == 12 else today.year
    next_month = 1 if today.month == 12 else today.month + 1
    _, last_day_next = calendar.monthrange(next_year, next_month)
    next_start = date(next_year, next_month, 1)
    next_end = date(next_year, next_month, last_day_next)
    try:
        # 3 oddělené dotazy
        rows_expired = Certifikat.fetch_between(env, date(2000, 1, 1), yesterday)
        rows_cur = Certifikat.fetch_between(env, cur_start, cur_end)
        rows_next = Certifikat.fetch_between(env, next_start, next_end)

        no_empty = '<p style="font-family:Arial,Helvetica,sans-serif;color:#94a3b8;padding:10px">Žádné položky</p>'

        # Textová verze
        lines = [f"Report končících certifikátů ({env.upper()}):", ""]

        if rows_expired:
            lines.append(f"Vypršelé certifikáty ({len(rows_expired)}):")
            for r in rows_expired:
                exp = format_date(r["expirace"])
                left = (exp - today).days
                lines.append(f"! {r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
            lines.append("")

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
        
        if not rows_expired and not rows_cur and not rows_next:
            lines.append("")
            lines.append("Vše v pořádku, žádné certifikáty neexpirují.")

        text_body = "\n".join(lines)

        # HTML verze
        critical_days = int(Settings.get('alert_days_critical', '30'))
        sections = []
        if rows_expired:
            expired_table = build_rows_html(rows_expired, today, critical_days)
            sections.append((f"Vypršelé ({len(rows_expired)})", expired_table))
        cur_table = build_rows_html(rows_cur, today, critical_days) if rows_cur else no_empty
        next_table = build_rows_html(rows_next, today, critical_days) if rows_next else no_empty
        sections.append((cz_month_name(today), cur_table))
        sections.append((cz_month_name(date(next_year, next_month, 1)), next_table))
        
        env_upper = env.upper()
        title_color = '#dc2626' if env_upper == 'LIVE' else '#16a34a'
        total = len(rows_expired) + len(rows_cur) + len(rows_next)
        stats = {'critical': len(rows_expired), 'warning': len(rows_cur), 'total': total}
        
        html_body = wrap_email_html(
            f"[{env_upper}] Měsíční report končících certifikátů",
            sections,
            title_color=title_color,
            stats=stats
        )

        sent = _send_email(f"[{env.upper()}] Měsíční report certifikátů", text_body, html_body)
        if sent:
            current_app.logger.info(
                "Report odeslán pro %s (vypršelé: %d, aktuální: %d, další: %d)", env, len(rows_expired), len(rows_cur), len(rows_next)
            )
            # Uložíme datum odeslání — catch-up po restartu pak ví, že tento měsíc už report odešel
            Settings.set(f'monthly_report_last_sent_{env}', today.isoformat())
        else:
            current_app.logger.warning(
                "Report pro %s se nepodařilo odeslat — zůstává neoznačen, catch-up ho po restartu zopakuje", env
            )

    except Exception as e:
        current_app.logger.error("Chyba při generování měsíčního reportu (%s): %s", env, e)

_app_ref = None
_scheduler = None
_scheduler_started = False

ALL_REPORT_ENVS = ('live', 'uat', 'sit', 'prelive')
DEFAULT_REPORT_ENVS = ','.join(ALL_REPORT_ENVS)
# Více prostředí se odesílá s tímto rozestupem, aby nepřišly všechny maily naráz
REPORT_STAGGER_MINUTES = 5


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


def get_report_config(app):
    """Konfigurace měsíčních reportů. Priorita: DB Settings > .env > default.

    Vrací (envs, day, hour, minute). Vyžaduje application context.
    """
    def _setting(key, fallback):
        try:
            val = Settings.get(key)
        except Exception:
            val = None
        return val if val not in (None, '') else fallback

    raw_envs = _setting(
        'report_envs',
        app.config.get('REPORT_ENVS') or os.environ.get('REPORT_ENVS') or DEFAULT_REPORT_ENVS,
    )
    parsed = [e.strip().lower() for e in str(raw_envs).split(',') if e.strip()]
    # map aliases a odfiltruj neznámé hodnoty, zachovej pořadí a unikátnost
    _alias = {'uat': 'uat', 'test': 'uat', 'live': 'live', 'prod': 'live', 'production': 'live', 'sit': 'sit', 'prelive': 'prelive'}
    envs = []
    for e in parsed:
        m = _alias.get(e)
        if m and m not in envs:
            envs.append(m)
    if not envs:
        envs = ['live']

    def _int_setting(key, env_key, default, lo, hi):
        try:
            val = int(_setting(key, os.environ.get(env_key, default)))
        except (TypeError, ValueError):
            val = int(default)
        return max(lo, min(hi, val))

    # Den omezen na 1–28, aby plán platil i pro únor
    day = _int_setting('report_day', 'REPORT_DAY', '1', 1, 28)
    hour = _int_setting('report_hour', 'REPORT_HOUR', '9', 0, 23)
    minute = _int_setting('report_minute', 'REPORT_MINUTE', '0', 0, 59)
    return envs, day, hour, minute


def _stagger(hour: int, minute: int, idx: int):
    total = minute + idx * REPORT_STAGGER_MINUTES
    return (hour + total // 60) % 24, total % 60


def schedule_report_jobs(app, scheduler):
    """(Pře)naplánuje cron joby měsíčních reportů podle aktuální konfigurace."""
    with app.app_context():
        envs, day, hour, minute = get_report_config(app)

    for job in scheduler.get_jobs():
        if job.id.startswith('monthly_report_'):
            job.remove()

    for idx, env in enumerate(envs):
        adj_hour, adj_minute = _stagger(hour, minute, idx)
        scheduler.add_job(
            _run_monthly,
            'cron',
            id=f'monthly_report_{env}',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=6 * 3600,
            day=day,
            hour=adj_hour,
            minute=adj_minute,
            args=[env],
        )

    when_str = ', '.join(
        f"{env}:{day}. v {_stagger(hour, minute, idx)[0]:02d}:{_stagger(hour, minute, idx)[1]:02d}"
        for idx, env in enumerate(envs)
    )
    app.logger.info("Měsíční reporty naplánovány (%s)", when_str)
    return envs, day, hour, minute


def reschedule_reports(app):
    """Aplikuje změnu nastavení reportů bez restartu (volá settings UI)."""
    if _scheduler is None:
        return None
    return schedule_report_jobs(app, _scheduler)


def _catch_up_missed_reports(app, scheduler, envs, day, hour, minute):
    """Dodatečné odeslání reportů zmeškaných kvůli výpadku (typicky patching).

    Pokud už v tomto měsíci minul plánovaný termín a report pro dané prostředí
    v tomto měsíci neodešel, odešle se dodatečně. Funguje kterýkoli den
    v měsíci (ne jen v den reportu) a nikdy neposílá před plánovaným časem —
    restart ve 3:00 v den reportu tedy report předčasně nespustí.
    """
    now = datetime.now()
    scheduled = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
    if now < scheduled:
        return

    month_key = now.strftime('%Y-%m')
    with app.app_context():
        for idx, env in enumerate(envs):
            try:
                last_sent = Settings.get(f'monthly_report_last_sent_{env}')
            except Exception:
                last_sent = None
            if last_sent and str(last_sent)[:7] == month_key:
                continue
            delay_min = idx * REPORT_STAGGER_MINUTES
            app.logger.info(
                'Catch-up: report pro %s za %s nebyl odeslán (naposledy: %s) — odešlu za %d min',
                env, month_key, last_sent or 'nikdy', delay_min
            )
            scheduler.add_job(
                _run_monthly,
                'date',
                run_date=now + timedelta(minutes=delay_min),
                id=f'monthly_catchup_{env}',
                replace_existing=True,
                args=[env],
            )


def init_scheduler(app):
    """Inicializace plánovače úloh (idempotentní, bez duplicit)."""
    global _app_ref, _scheduler, _scheduler_started
    # Zabráníme spuštění v rodičovském procesu debug reloaderu
    if getattr(app, 'debug', False) and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        app.logger.info('Scheduler: přeskočeno v parent procesu (debug reloader)')
        return None
    if _scheduler_started:
        return None
    _scheduler_started = True
    _app_ref = app

    scheduler = BackgroundScheduler(daemon=True)
    _scheduler = scheduler

    envs, day, hour, minute = schedule_report_jobs(app, scheduler)
    scheduler.start()

    _catch_up_missed_reports(app, scheduler, envs, day, hour, minute)

    return scheduler
