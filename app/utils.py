from datetime import datetime, timedelta
import pandas as pd

def allowed_file(filename, allowed_extensions={'xlsx', 'xls'}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def is_valid_date(value):
    if pd.isna(value):
        return False
    try:
        if isinstance(value, str):
            datetime.strptime(value, '%d.%m.%Y')
        elif isinstance(value, datetime):
            return True
        else:
            return False
        return True
    except ValueError:
        return False

def get_expiry_class(cert):
    """Vrací CSS třídu podle data expirace certifikátu"""
    if not cert.expirace:
        return ''
        
    today = datetime.now().date()
    expiry = cert.expirace.date() if isinstance(cert.expirace, datetime) else cert.expirace

    # Sjednocení s logikou dashboardu: <=30 dní kritické (červená),
    # 31–60 dní varování (oranžová), zbytek letošního roku modrá
    days_left = (expiry - today).days

    if days_left <= 30:
        return 'cert-expired'  # Červená
    elif 30 < days_left <= 60:
        return 'cert-warning'  # Oranžová
    elif expiry.year == today.year and days_left > 60:
        return 'cert-ending-year'  # Modrá

    return ''