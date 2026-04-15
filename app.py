from app import create_app, db
from app.models import Certifikat, Server
from flask import redirect

app = create_app()

# Vytvoření databáze — zajistíme tabulky ve všech bindech.
# Modely mají __bind_key__ = 'live', takže jsou registrované v db.metadatas['live'].
# Stejné schéma chceme vytvořit i v test/sit/prelive enginech.
with app.app_context():
    from flask import current_app
    # Flask-SQLAlchemy 3.x: tabulky jsou v metadatě příslušného bind_key
    live_meta = db.metadatas.get('live') if hasattr(db, 'metadatas') else db.metadata
    for env in ('live', 'test', 'sit', 'prelive'):
        try:
            try:
                engine = db.engines[env]
            except Exception:
                engine = db.get_engine(current_app, bind=env)
            live_meta.create_all(bind=engine)
            app.logger.info('DB init OK: %s', env)
        except Exception as e:
            app.logger.warning('DB init selhalo pro %s: %s', env, e)

@app.route('/', endpoint='root')
def root_redirect():
    return redirect('/evidence_certifikatu')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)