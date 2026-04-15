from flask import Blueprint, render_template, request, current_app
from app.models import AuditLog

bp = Blueprint('historie', __name__)


@bp.route('/historie')
def index():
    page = request.args.get('page', 1, type=int)
    try:
        pagination = AuditLog.query.order_by(AuditLog.cas.desc()).paginate(
            page=page, per_page=30, error_out=False
        )
        return render_template('historie.html',
                             logs=pagination.items,
                             pagination=pagination)
    except Exception as e:
        current_app.logger.error('Chyba při načítání historie: %s', e)
        return render_template('historie.html', logs=[], pagination=None)
