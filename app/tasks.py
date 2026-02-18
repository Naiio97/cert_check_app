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

def _engine(env: str):
    # Flask-SQLAlchemy 3.2+: používejte db.engines[bind]
    try:
        return db.engines[env]
    except Exception:
        return db.get_engine(current_app, bind=env)


def _fetch_expiring(env: str, days: int = 60):
    """Vrátí list záznamů z tabulky certifikat pro dané prostředí do N dnů."""
    today = date.today()
    with _engine(env).begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT server, cesta, nazev, expirace
                FROM certifikat
                WHERE date(expirace) <= date(:today, :plus)
                ORDER BY expirace ASC
                """
            ),
            {"today": today.isoformat(), "plus": f"+{days} day"},
        ).mappings().all()
    return rows


def _send_email(subject: str, text_body: str, html_body: str | None = None):
    cfg = current_app.config
    username = cfg.get("MAIL_USERNAME") or None
    password = cfg.get("MAIL_PASSWORD") or None
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
    sender_addr = cfg.get("MAIL_SENDER_ADDRESS") or username or "noreply@example.com"
    sender_name = cfg.get("MAIL_SENDER_NAME")
    msg["From"] = f"{sender_name} <{sender_addr}>" if sender_name else sender_addr
    msg["To"] = ", ".join(recipients)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg.get("MAIL_SERVER", "localhost"), cfg.get("MAIL_PORT", 25)) as server:
            if cfg.get("MAIL_USE_TLS", False):
                server.starttls(context=context)
            if cfg.get("MAIL_SMTP_AUTH", False) and username and password:
                server.login(username, password)
            server.sendmail(sender_addr, recipients, msg.as_string())
        current_app.logger.info("E-mail odeslán: %s", subject)
    except Exception as e:
        current_app.logger.error("Chyba při odesílání e-mailu: %s", e)


def _format_date(value) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception:
        # fallback: try parse common formats
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except Exception:
            return date.today()


_CZ_MONTHS = [
    "leden", "únor", "březen", "duben", "květen", "červen",
    "červenec", "srpen", "září", "říjen", "listopad", "prosinec"
]


def _cz_month_name(dt: date) -> str:
    try:
        name = _CZ_MONTHS[dt.month - 1]
        # První písmeno velké
        return name[:1].upper() + name[1:]
    except Exception:
        return str(dt.month)


def _build_rows_html(rows: list[dict], today: date) -> str:
    # jednoduché inline CSS pro kompatibilitu v e-mailových klientech
    table_head = (
        '<table role="table" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-family:Arial,Helvetica,sans-serif;font-size:14px">'
        '<thead><tr style="background:#f4f6f8;color:#111;">'
        '<th align="left" style="border-bottom:1px solid #ddd">Server</th>'
        '<th align="left" style="border-bottom:1px solid #ddd">Cesta</th>'
        '<th align="left" style="border-bottom:1px solid #ddd">Název</th>'
        '<th align="left" style="border-bottom:1px solid #ddd">Expirace</th>'
        '<th align="right" style="border-bottom:1px solid #ddd">Zbývá dnů</th>'
        '</tr></thead><tbody>'
    )
    body_rows = []
    for r in rows:
        exp = _format_date(r["expirace"]) if "expirace" in r else _format_date(r.get("EXPIRACE"))
        left = (exp - today).days
        critical = left <= 30
        row_bg = '#fff6f6' if critical else '#ffffff'
        row_style = f'background:{row_bg};'
        td_style = 'border-bottom:1px solid #eee;vertical-align:top;'
        body_rows.append(
            '<tr style="%s">%s%s%s%s%s</tr>' % (
                row_style,
                f'<td style="{td_style}">{r.get("server", "")}</td>',
                f'<td style="{td_style}">{r.get("cesta", "")}</td>',
                f'<td style="{td_style}">{r.get("nazev", "")}</td>',
                f'<td style="{td_style}">{exp.strftime("%d.%m.%Y")}</td>',
                f'<td align="right" style="{td_style}"><strong>{left}</strong></td>',
            )
        )
    table_tail = '</tbody></table>'
    return table_head + ''.join(body_rows) + table_tail


def _wrap_email_html(title: str, sections: list[tuple[str, str]], title_color: str = '#111'):
    # sections: list of (headline, html_table)
    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:16px;background:#fafbfc">',
        f'<div style="max-width:900px;margin:0 auto;background:#ffffff;border:1px solid #e6e8eb;border-radius:8px;overflow:hidden">',
        f'<div style="padding:16px 20px;background:#ffffff;border-bottom:1px solid #e6e8eb;font-family:Arial,Helvetica,sans-serif">'
        f'<h2 style="margin:0;font-size:18px;color:{title_color}">{title}</h2></div>',
        '<div style="padding:16px 20px">'
    ]
    for headline, table_html in sections:
        parts.append(f'<h3 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#111;margin:16px 0 8px">{headline}</h3>')
        parts.append(table_html)
    parts.append('</div></div>')
    parts.append('<div style="text-align:center;color:#888;font-size:12px;font-family:Arial,Helvetica,sans-serif;margin-top:8px">Automatická zpráva – prosím neodpovídejte.</div>')
    parts.append('</body></html>')
    return ''.join(parts)


def send_daily_certificate_alert(env: str):
    """Odešle denní upozornění o certifikátech končících do 60 dnů pro dané prostředí."""
    try:
        rows = _fetch_expiring(env, days=60)
        if not rows:
            current_app.logger.info("[%s] Žádné končící certifikáty do 60 dnů", env)
            return
        today = date.today()
        critical = [r for r in rows if (_format_date(r["expirace"]) - today).days <= 30]
        # Plain text
        lines = [f"Seznam certifikátů končících do 60 dnů ({env.upper()}):", ""]
        for r in rows:
            exp = _format_date(r["expirace"]) 
            left = (exp - today).days
            mark = "! " if left <= 30 else ""
            lines.append(f"{mark}{r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
        text_body = "\n".join(lines)

        # HTML
        table_html = _build_rows_html(rows, today)
        html = _wrap_email_html(
            title=f"[{env.upper()}] Končící certifikáty do 60 dnů",
            sections=[(f"Kritické: {len(critical)}", table_html)]
        )
        subject = f"[{env.upper()}] Končící certifikáty do 60 dnů (kritické: {len(critical)})"
        _send_email(subject, text_body, html)
    except Exception as e:
        current_app.logger.error("Chyba alertu pro %s: %s", env, e)

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
        with _engine(env).begin() as conn:
            rows_cur = conn.execute(
                    text(
                        """
                        SELECT server, cesta, nazev, expirace
                        FROM certifikat
                        WHERE date(expirace) BETWEEN date(:start) AND date(:end)
                        ORDER BY expirace
                        """
                    ),
                    {"start": cur_start.isoformat(), "end": cur_end.isoformat()},
            ).mappings().all()
            rows_next = conn.execute(
                    text(
                        """
                        SELECT server, cesta, nazev, expirace
                        FROM certifikat
                        WHERE date(expirace) BETWEEN date(:start) AND date(:end)
                        ORDER BY expirace
                        """
                    ),
                    {"start": next_start.isoformat(), "end": next_end.isoformat()},
            ).mappings().all()
        if rows_cur or rows_next:
                # Textová verze
                lines = [f"Report končících certifikátů ({env.upper()}):", ""]
                lines.append(f"Aktuální měsíc ({today.month}.{today.year}):")
                if rows_cur:
                    for r in rows_cur:
                        exp = _format_date(r["expirace"]) 
                        left = (exp - today).days
                        lines.append(f"- {r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
                else:
                    lines.append("- žádné položky")
                lines.append("")
                lines.append(f"Následující měsíc ({next_month}.{next_year}):")
                if rows_next:
                    for r in rows_next:
                        exp = _format_date(r["expirace"]) 
                        left = (exp - today).days
                        lines.append(f"- {r['server']} | {r['cesta']} | {r['nazev']} | {exp.strftime('%d.%m.%Y')} | {left} dní")
                else:
                    lines.append("- žádné položky")
                text_body = "\n".join(lines)

                # HTML verze – dvě tabulky
                sections = []
                cur_table = _build_rows_html(rows_cur, today) if rows_cur else '<p style="font-family:Arial,Helvetica,sans-serif">Žádné položky</p>'
                next_table = _build_rows_html(rows_next, today) if rows_next else '<p style="font-family:Arial,Helvetica,sans-serif">Žádné položky</p>'
                sections.append((_cz_month_name(today), cur_table))
                sections.append((_cz_month_name(date(next_year, next_month, 1)), next_table))
                env_upper = env.upper()
                # Barvy hlavičky podle prostředí: LIVE = červená, TEST/UAT = zelená
                title_color = '#d92d20' if env_upper == 'LIVE' else '#147d14'
                html_body = _wrap_email_html(f"[{env_upper}] Měsíční report končících certifikátů", sections, title_color=title_color)

                _send_email(f"[{env.upper()}] Měsíční report (aktuální + další měsíc)", text_body, html_body)
                current_app.logger.info(
                    "Report odeslán pro %s (aktuální: %d, další: %d)", env, len(rows_cur), len(rows_next)
                )
        else:
            current_app.logger.info("Měsíční report: žádné certifikáty (%s)", env)
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