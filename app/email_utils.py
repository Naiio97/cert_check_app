from datetime import date, datetime
from html import escape

_CZ_MONTHS = [
    "leden", "únor", "březen", "duben", "květen", "červen",
    "červenec", "srpen", "září", "říjen", "listopad", "prosinec"
]

def format_date(value) -> date:
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

def cz_month_name(dt: date) -> str:
    try:
        name = _CZ_MONTHS[dt.month - 1]
        # První písmeno velké
        return name[:1].upper() + name[1:]
    except Exception:
        return str(dt.month)

# Barvy hlaviček e-mailů podle prostředí — sladěno s barvami v UI (env-badge / env-btn v style.css)
ENV_TITLE_COLORS = {
    'LIVE': '#DC2626',
    'UAT': '#15803D',
    'SIT': '#CA8A04',
    'PRELIVE': '#DB2777',
}

def get_env_title_color(env: str) -> str:
    return ENV_TITLE_COLORS.get(str(env).upper(), '#111')


# ─── E-mailová šablona (tabulkové rozvržení + inline CSS kvůli e-mailovým klientům) ───

_FONT = "Arial,Helvetica,sans-serif"


def _esc(value) -> str:
    return escape(str(value if value is not None else ''))


def _days_text(days: int) -> str:
    """Zbývající dny česky: dnes / za 1 den / za 3 dny / za 12 dní / před 5 dny."""
    if days < 0:
        n = -days
        return f"před {n} dnem" if n == 1 else f"před {n} dny"
    if days == 0:
        return "dnes"
    if days == 1:
        return "za 1 den"
    if days < 5:
        return f"za {days} dny"
    return f"za {days} dní"


def _count_text(n: int) -> str:
    if n == 1:
        return "1 položka"
    if 2 <= n <= 4:
        return f"{n} položky"
    return f"{n} položek"


def _item_html(row, today: date, critical_days: int) -> str:
    exp = format_date(row["expirace"])
    days = (exp - today).days
    if days <= critical_days:
        pill_bg, pill_fg = '#FEE2E2', '#B91C1C'
    else:
        pill_bg, pill_fg = '#FEF3C7', '#B45309'
    where = ' · '.join(x for x in (_esc(row.get("server", "")), _esc(row.get("cesta", ""))) if x)
    return (
        '<tr>'
        '<td style="padding:12px 0;border-bottom:1px solid #F0F1F5">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%"><tr>'
        f'<td valign="middle" style="font-family:{_FONT}">'
        f'<div style="font-size:14px;font-weight:700;color:#111827">{_esc(row.get("nazev", ""))}</div>'
        f'<div style="font-size:12px;color:#6B7280;margin-top:3px;word-break:break-all">{where}</div>'
        '</td>'
        f'<td valign="middle" align="right" style="font-family:{_FONT};white-space:nowrap;padding-left:12px">'
        f'<div style="font-size:13px;font-weight:700;color:#111827">{exp.strftime("%d.%m.%Y")}</div>'
        f'<div style="margin-top:5px"><span style="display:inline-block;padding:3px 10px;border-radius:10px;'
        f'background:{pill_bg};color:{pill_fg};font-size:12px;font-weight:700">{_days_text(days)}</span></div>'
        '</td></tr></table>'
        '</td></tr>'
    )


def _section_html(title: str, rows: list, today: date, critical_days: int, empty_text: str) -> str:
    if rows:
        body = ''.join(_item_html(r, today, critical_days) for r in rows)
    else:
        body = (
            f'<tr><td style="padding:4px 0 8px;font-family:{_FONT};font-size:13px;color:#9CA3AF">'
            f'{_esc(empty_text)}</td></tr>'
        )
    return (
        '<tr><td style="padding:20px 28px 4px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%">'
        '<tr><td style="padding-bottom:8px;border-bottom:1px solid #E5E7EB">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%"><tr>'
        f'<td style="font-family:{_FONT};font-size:16px;font-weight:700;color:#111827">{_esc(title)}</td>'
        f'<td align="right" style="font-family:{_FONT};font-size:12px;color:#6B7280">{_count_text(len(rows))}</td>'
        '</tr></table></td></tr>'
        f'{body}'
        '</table></td></tr>'
    )


def _stats_html(stats: dict) -> str:
    items = [
        ('Kritické', stats.get('critical', 0), '#DC2626'),
        ('Varování', stats.get('warning', 0), '#EA580C'),
        ('Celkem', stats.get('total', 0), '#4F46E5'),
    ]
    cells = []
    for idx, (label, value, color) in enumerate(items):
        shown = color if value else '#9CA3AF'
        gap = '' if idx == len(items) - 1 else '<td width="12" style="width:12px;font-size:0">&nbsp;</td>'
        cells.append(
            '<td width="32%" valign="top" align="center" style="width:32%;background:#F9FAFB;'
            'border:1px solid #F0F1F5;border-radius:10px;padding:16px 12px">'
            f'<div style="font-family:{_FONT};font-size:34px;font-weight:700;line-height:1.1;color:{shown}">{value}</div>'
            f'<div style="font-family:{_FONT};font-size:11px;font-weight:700;letter-spacing:1px;color:#6B7280;'
            f'margin-top:4px;text-transform:uppercase">{label}</div></td>' + gap
        )
    return (
        '<tr><td style="padding:24px 28px 8px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%"><tr>'
        + ''.join(cells) + '</tr></table></td></tr>'
    )


def _shell(env: str, title: str, subtitle: str, inner_rows: str, cta_url: str = '') -> str:
    env_upper = str(env).upper()
    color = get_env_title_color(env_upper)
    banner = ''
    if env_upper != 'LIVE':
        banner = (
            f'<tr><td align="center" style="background:#FEF3C7;padding:10px 28px;font-family:{_FONT};'
            'font-size:11px;font-weight:700;letter-spacing:1px;color:#92400E">'
            'ZPRÁVA Z TESTOVACÍHO PROSTŘEDÍ</td></tr>'
        )
    cta = ''
    if cta_url:
        cta = (
            '<tr><td style="padding:24px 28px 28px">'
            f'<a href="{_esc(cta_url)}" style="display:inline-block;padding:12px 22px;background:#4F46E5;'
            f'color:#FFFFFF;font-family:{_FONT};font-size:14px;font-weight:700;text-decoration:none;'
            'border-radius:8px">Otevřít evidenci certifikátů</a></td></tr>'
        )
    else:
        cta = '<tr><td style="font-size:0;line-height:0;padding-bottom:20px">&nbsp;</td></tr>'
    return (
        '<!DOCTYPE html><html lang="cs"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{_esc(title)}</title></head>'
        f'<body style="margin:0;padding:0;background:#F3F4F6;font-family:{_FONT}">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;background:#F3F4F6">'
        '<tr><td align="center" style="padding:32px 12px">'
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
        'style="width:100%;max-width:640px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px">'
        f'{banner}'
        f'<tr><td style="background:{color};padding:28px;border-radius:0">'
        f'<span style="display:inline-block;padding:4px 12px;border-radius:12px;background:#FFFFFF;color:{color};'
        f'font-family:{_FONT};font-size:12px;font-weight:700;letter-spacing:1px">{_esc(env_upper)}</span>'
        f'<div style="font-family:{_FONT};font-size:24px;font-weight:700;line-height:1.25;color:#FFFFFF;'
        f'margin-top:10px">{_esc(title)}</div>'
        f'<div style="font-family:{_FONT};font-size:14px;color:#FFFFFF;opacity:0.9;margin-top:10px">{_esc(subtitle)}</div>'
        '</td></tr>'
        f'{inner_rows}{cta}'
        '</table>'
        f'<div style="font-family:{_FONT};font-size:12px;color:#9CA3AF;margin-top:20px">'
        'Automatická zpráva – prosím neodpovídejte.</div>'
        '</td></tr></table></body></html>'
    )


def render_report_email(env: str, title: str, subtitle: str, stats: dict, sections: list,
                        today: date, critical_days: int = 30, cta_url: str = '',
                        empty_text: str = 'Žádné položky') -> str:
    """Report s přehledem certifikátů. sections: [(nadpis, [řádky])] — prázdná sekce ukáže 'Žádné položky'."""
    inner = _stats_html(stats) + ''.join(
        _section_html(t, rows, today, critical_days, empty_text) for t, rows in sections
    )
    return _shell(env, title, subtitle, inner, cta_url)


def render_notice_email(env: str, title: str, subtitle: str, message: str, cta_url: str = '') -> str:
    """Jednoduchá zpráva ve stejném vzhledu (např. test SMTP)."""
    inner = (
        f'<tr><td style="padding:24px 28px 4px;font-family:{_FONT};font-size:14px;color:#111827">'
        f'{_esc(message)}</td></tr>'
    )
    return _shell(env, title, subtitle, inner, cta_url)
