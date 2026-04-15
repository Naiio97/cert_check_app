from flask import Blueprint, render_template, current_app, jsonify, request, g
from app.models import Certifikat, Server
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/send-report', methods=['POST'])
def send_report():
    """Ručně odešle měsíční report (stejný jako automatický)."""
    try:
        from app.tasks import send_monthly_certificate_report
        env = getattr(g, 'db_bind', 'live')
        send_monthly_certificate_report(env)
        return jsonify({'message': f'Report pro {env.upper()} odeslán'})
    except Exception as e:
        current_app.logger.error('Chyba při odesílání reportu: %s', e)
        return jsonify({'message': f'Chyba: {e}'}), 500

@bp.before_request
def log_request():
    current_app.logger.info('Request: %s %s (referrer: %s)', request.method, request.path, request.referrer)

@bp.route('/')
def index():
    try:
        # Načteme všechny servery
        servery = Server.query.all()
        servery_nazvy = [server.nazev for server in servery]
        
        # Načteme aktivní server z prvního serveru v seznamu
        aktivni_server = servery_nazvy[0] if servery_nazvy else None
        
        page = request.args.get('page', 1, type=int)

        # Načteme certifikáty pro aktivní server
        if aktivni_server:
            pagination = Certifikat.query.filter_by(server=aktivni_server)\
                .order_by(Certifikat.expirace, Certifikat.cesta)\
                .paginate(page=page, per_page=25, error_out=False)
            certifikaty = pagination.items
        else:
            pagination = None
            certifikaty = []
        
        return render_template('index.html',
                             certifikaty=certifikaty,
                             servery=servery_nazvy,
                             aktivni_server=aktivni_server,
                             pagination=pagination)
                             
    except Exception as e:
        current_app.logger.error('Chyba při načítání hlavní stránky: %s', e)
        return f"Došlo k chybě: {str(e)}", 500 

@bp.route('/detail/<int:id>')
def detail(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        today = datetime.now().date()  # Přidáme dnešní datum
        return render_template('detail_modal.html', 
                              certifikat=certifikat,
                              today=today)  # Předáme today do šablony
    except Exception as e:
        current_app.logger.error('Chyba při načítání detailu: %s', e)
        return jsonify({'error': str(e)}), 500