from app import create_app, db
from app.models import Certifikat, Server
from flask import redirect

app = create_app()

# Vytvoření databáze
with app.app_context():
    # Vytvoříme tabulky pro obě databáze (live/test) přímo přes metadata
    for env in ('live', 'test'):
        try:
            engine = db.get_engine(app, bind=env)
            db.metadata.create_all(bind=engine)
        except Exception:
            pass

@app.route('/', endpoint='root')
def root_redirect():
    return redirect('/evidence_certifikatu')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)