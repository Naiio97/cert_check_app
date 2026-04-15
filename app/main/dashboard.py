from flask import Blueprint, render_template, flash, redirect, url_for, current_app
from app.models import Certifikat, Settings
from app import db
from datetime import date, timedelta
from sqlalchemy import func

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
def index():
    try:
        today = date.today()
        end_of_year = date(today.year, 12, 31)

        critical_days = int(Settings.get('alert_days_critical', '30'))
        warning_days = int(Settings.get('alert_days_warning', '60'))
        critical_threshold = today + timedelta(days=critical_days)
        warning_threshold = today + timedelta(days=warning_days)

        base_q = Certifikat.query.filter(Certifikat.expirace <= end_of_year)

        stats = {
            'expired':   base_q.filter(Certifikat.expirace < today).count(),
            'critical':  base_q.filter(Certifikat.expirace >= today,
                                       Certifikat.expirace <= critical_threshold).count(),
            'warning':   base_q.filter(Certifikat.expirace > critical_threshold,
                                       Certifikat.expirace <= warning_threshold).count(),
            'this_year': base_q.count(),
        }

        server_stats = (
            db.session.query(Certifikat.server, func.count(Certifikat.id).label('count'))
            .filter(Certifikat.expirace <= end_of_year)
            .group_by(Certifikat.server)
            .order_by(func.count(Certifikat.id).desc())
            .all()
        )

        ending_certs = base_q.order_by(Certifikat.expirace).all()

        return render_template('dashboard.html',
                             stats=stats,
                             ending_certs=ending_certs,
                             server_stats=server_stats,
                             today=today)
    except Exception as e:
        current_app.logger.error('Chyba při načítání dashboardu: %s', e)
        flash('Chyba při načítání dashboardu', 'error')
        return redirect(url_for('main.index'))
