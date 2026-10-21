@echo off
chcp 65001 >nul
echo ============================================
echo   Deploy - Evidence Certifikatu
echo ============================================
echo.
echo Tento skript provede PRVNI instalaci aplikace.
echo Pro aktualizaci existujici instalace pouzij update.bat
echo.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

echo [1/4] Kontroluji Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [CHYBA] Python nebyl nalezen! Nainstalujte Python 3.12+ a pridejte ho do PATH.
    pause
    exit /b 1
)
for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo [OK] %%V

echo [2/4] Pripravuji virtualni prostredi...
if not exist "venv" (
    echo [INFO] Vytvarim virtualni prostredi...
    python -m venv venv
    if errorlevel 1 (
        echo [CHYBA] Nepodarilo se vytvorit venv!
        pause
        exit /b 1
    )
    echo [OK] Virtualni prostredi vytvoreno
) else (
    echo [OK] Virtualni prostredi jiz existuje
)

echo [3/4] Instaluji zavislosti offline z dependencies/ ...
venv\Scripts\python.exe -m pip install --no-index --find-links=dependencies -r requirements.txt
if errorlevel 1 (
    echo [CHYBA] Instalace zavislosti selhala!
    pause
    exit /b 1
)
echo [OK] Zavislosti nainstalovany

if not exist "logs"     mkdir logs
if not exist "uploads"  mkdir uploads
if not exist "instance" mkdir instance
echo [OK] Slozky vytvoreny (logs, uploads, instance)

echo [4/4] Inicializuji databaze (live, uat, sit, prelive) ...
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('[OK] DB: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
if errorlevel 1 (
    echo [VAROVANI] DB init selhal - tabulky budou vytvoreny pri prvnim spusteni aplikace.
) else (
    echo [OK] Databaze inicializovany
)

echo.
echo ============================================
echo   Zakladni instalace dokoncena!
echo ============================================
echo.
echo Dalsi kroky:
echo.
echo  1. Vytvor konfiguraci .env:
echo        copy .env.example .env
echo        notepad .env
echo.
echo  2. Over funkcnost aplikace:
echo        venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=8080 wsgi:app
echo        Otevri: http://localhost:8080/evidence_certifikatu
echo        Zastav: Ctrl+C
echo.
echo  3. Konfiguruj IIS (viz DEPLOY.md sekce 5) - Application Pool + web.config
echo.
echo  4. Nastav NSSM sluzbu (viz DEPLOY.md sekce 5.4):
echo        nssm install CertifikatyApp
echo        nssm set CertifikatyApp Application "%APP_DIR%venv\Scripts\python.exe"
echo        nssm set CertifikatyApp AppParameters "-m waitress --host=0.0.0.0 --port=8080 wsgi:app"
echo        nssm set CertifikatyApp AppDirectory "%APP_DIR:~0,-1%"
echo        nssm start CertifikatyApp
echo.
pause