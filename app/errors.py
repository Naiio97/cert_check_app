from flask import render_template, request
from app import db

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        # WARNING, ne ERROR — 404 generují hlavně scannery a překlepy v URL,
        # ERROR level má zůstat volný pro skutečné chyby aplikace.
        app.logger.warning('Stránka nenalezena: %s', request.url)
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error('Interní chyba serveru: %s', error, exc_info=True)
        db.session.rollback()
        return render_template('500.html'), 500

    @app.errorhandler(413)
    def too_large(error):
        app.logger.warning('Nahrávaný soubor je příliš velký')
        return 'Soubor je příliš velký', 413 