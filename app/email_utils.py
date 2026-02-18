from datetime import date, datetime

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

def build_rows_html(rows: list, today: date, critical_days: int = 30) -> str:
    # jednoduché inline CSS pro kompatibilitu v e-mailových klientech
    table_head = (
        '<table role="table" cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;font-family:Arial,Helvetica,sans-serif;font-size:14px">'
        '<thead><tr style="background:#f8fafc">'
        '<th align="left" style="padding:10px 12px;border-bottom:2px solid #e2e8f0;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b">Server</th>'
        '<th align="left" style="padding:10px 12px;border-bottom:2px solid #e2e8f0;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b">Cesta</th>'
        '<th align="left" style="padding:10px 12px;border-bottom:2px solid #e2e8f0;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b">Název</th>'
        '<th align="left" style="padding:10px 12px;border-bottom:2px solid #e2e8f0;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b">Expirace</th>'
        '<th align="right" style="padding:10px 12px;border-bottom:2px solid #e2e8f0;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#64748b">Zbývá dnů</th>'
        '</tr></thead><tbody>'
    )
    body_rows = []
    for r in rows:
        exp = format_date(r["expirace"]) if "expirace" in r else format_date(r.get("EXPIRACE"))
        left = (exp - today).days
        critical = left <= critical_days
        if left <= 0:
            row_bg = '#fef2f2'
            left_color = '#dc2626'
            left_label = f'<strong style="color:{left_color}">{left}</strong> ⚠️'
        elif critical:
            row_bg = '#fff7ed'
            left_color = '#ea580c'
            left_label = f'<strong style="color:{left_color}">{left}</strong>'
        else:
            row_bg = '#ffffff'
            left_color = '#64748b'
            left_label = f'<strong style="color:{left_color}">{left}</strong>'
        td_style = f'padding:8px 12px;border-bottom:1px solid #f1f5f9;vertical-align:top;'
        body_rows.append(
            '<tr style="background:%s">%s%s%s%s%s</tr>' % (
                row_bg,
                f'<td style="{td_style}">{r.get("server", "")}</td>',
                f'<td style="{td_style}">{r.get("cesta", "")}</td>',
                f'<td style="{td_style}"><strong>{r.get("nazev", "")}</strong></td>',
                f'<td style="{td_style}">{exp.strftime("%d.%m.%Y")}</td>',
                f'<td align="right" style="{td_style}">{left_label}</td>',
            )
        )
    table_tail = '</tbody></table>'
    return table_head + ''.join(body_rows) + table_tail


def wrap_email_html(title: str, sections: list[tuple[str, str]], title_color: str = '#111', stats: dict = None):
    # Modern HTML email template
    header_bg = title_color
    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:20px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">',
        '<div style="max-width:900px;margin:0 auto">',
        # Header
        f'<div style="background:{header_bg};border-radius:12px 12px 0 0;padding:20px 24px">'
        f'<h1 style="margin:0;font-size:18px;color:#ffffff;font-weight:600">{title}</h1>'
        '</div>',
        '<div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;overflow:hidden">',
    ]
    # Stats boxes
    if stats:
        # Table-based layout for Outlook compatibility
        parts.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;border-bottom:1px solid #f1f5f9"><tr>')
        stat_items = [
            ('Kritické', stats.get('critical', 0), '#dc2626', '#fef2f2'),
            ('Varování', stats.get('warning', 0), '#ea580c', '#fff7ed'),
            ('Celkem', stats.get('total', 0), '#3b82f6', '#eff6ff'),
        ]
        
        # Calculate width percentage (33% for 3 items)
        width_pct = int(100 / len(stat_items))
        
        for idx, (label, val, color, bg) in enumerate(stat_items):
            # Add padding logic: start, middle, end
            pad_style = 'padding:16px 8px 16px 24px' if idx == 0 else ('padding:16px 24px 16px 8px' if idx == len(stat_items)-1 else 'padding:16px 8px')
            
            parts.append(
                f'<td width="{width_pct}%" valign="top" style="{pad_style}">'
                f'<div style="background:{bg};border-radius:8px;padding:12px 16px;text-align:center">'
                # Fallback for border-radius in Outlook: it will be square, which is fine.
                f'<div style="font-size:24px;font-weight:700;color:{color};font-family:Arial,sans-serif">{val}</div>'
                f'<div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;font-family:Arial,sans-serif">{label}</div>'
                '</div></td>'
            )
        parts.append('</tr></table>')

    # Sections
    parts.append('<div style="padding:8px 24px 24px">')
    for headline, table_html in sections:
        parts.append(f'<h3 style="font-size:14px;color:#1e293b;margin:16px 0 8px;font-weight:600">{headline}</h3>')
        parts.append(table_html)
    parts.append('</div></div>')
    parts.append('<div style="text-align:center;color:#94a3b8;font-size:11px;margin-top:12px;font-family:Arial,Helvetica,sans-serif">Automatická zpráva – prosím neodpovídejte.</div>')
    parts.append('</div></body></html>')
    return ''.join(parts)
