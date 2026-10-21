from app import create_app, db
from flask import redirect

app = create_app()

# Tabulky a drobné migrace schématu ve všech prostředích (live, uat, sit, prelive)
from app.db_init import init_databases
init_databases(app)

@app.route('/', endpoint='root')
def root_redirect():
    return redirect('/evidence_certifikatu')

if __name__ == '__main__':
    # debug řídí Config.DEBUG (FLASK_DEBUG v .env) — natvrdo debug=True by
    # v produkci vystavilo werkzeug debugger (vzdálené spuštění kódu).
    app.run(host='0.0.0.0', port=8080)