@echo off
chcp 65001 >nul
echo ============================================
echo   Deploy - Evidence Certifikatu
echo ============================================
echo.
echo Tento skript provede PRVNÍ instalaci aplikace.
echo Pro aktualizaci existující instalace použij update.bat
echo.

REM Zjistíme cestu ke složce kde leží tento skript
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM ── [1/4] Kontrola Pythonu ───────────────────────────────────────────────────
echo [1/4] Kontroluji Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [CHYBA] Python nebyl nalezen! Nainstalujte Python 3.12+ a přidejte ho do PATH.
    pause
    exit /b 1
)
for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo [OK] %%V

REM ── [2/4] Virtuální prostředí ────────────────────────────────────────────────
echo [2/4] Připravuji virtuální prostředí...
if not exist "venv" (
    echo [INFO] Vytvářím virtuální prostředí...
    python -m venv venv
    if errorlevel 1 (
        echo [CHYBA] Nepodařilo se vytvořit venv!
        pause
        exit /b 1
    )
    echo [OK] Virtuální prostředí vytvořeno
) else (
    echo [OK] Virtuální prostředí již existuje
)

REM ── [3/4] Offline instalace závislostí ──────────────────────────────────────
echo [3/4] Instaluji závislosti offline z dependencies/...
venv\Scripts\python.exe -m pip install --no-index --find-links=dependencies -r requirements.txt
if errorlevel 1 (
    echo [CHYBA] Instalace závislostí selhala!
    pause
    exit /b 1
)
echo [OK] Závislosti nainstalovány

REM ── Vytvoření potřebných složek ──────────────────────────────────────────────
if not exist "logs"     mkdir logs
if not exist "uploads"  mkdir uploads
if not exist "instance" mkdir instance
echo [OK] Složky vytvořeny (logs, uploads, instance)

REM ── [4/4] Inicializace databází ──────────────────────────────────────────────
echo [4/4] Inicializuji databáze (live, uat, sit, prelive)...
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('[OK] DB: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
if errorlevel 1 (
    echo [VAROVÁNÍ] DB init selhal - tabulky budou vytvořeny při prvním spuštění aplikace.
) else (
    echo [OK] Databáze inicializovány
)

echo.
echo ============================================
echo   Základní instalace dokončena!
echo ============================================
echo.
echo ── Další kroky ───────────────────────────────────────────────────────────
echo.
echo  1. Vytvoř konfigurační soubor .env:
echo        copy .env.example .env
echo        notepad .env
echo     Vyplň minimálně SECRET_KEY (vygeneruj: venv\Scripts\python.exe -c
echo     "import secrets; print(secrets.token_hex(32))")
echo.
echo  2. Ověř funkčnost aplikace (zastav pomocí Ctrl+C):
echo        venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8080 app:app
echo        Otevři: http://localhost:8080/evidence_certifikatu
echo.
echo  3. Nakonfiguruj IIS jako reverse proxy (viz DEPLOY.md sekce 5):
echo     - Vytvoř Application Pool "CertifikátyPool" (.NET CLR: No Managed Code)
echo     - Přidej web/aplikaci směřující do: %APP_DIR%
echo     - Nainstaluj URL Rewrite + ARR a vytvoř web.config s proxy pravidlem
echo.
echo  4. Nastav Waitress jako Windows službu přes NSSM (viz DEPLOY.md sekce 5.4):
echo        nssm install CertifikátyApp
echo        nssm set CertifikátyApp Application "%APP_DIR%venv\Scripts\python.exe"
echo        nssm set CertifikátyApp AppParameters "-m waitress --host=127.0.0.1 --port=8080 app:app"
echo        nssm set CertifikátyApp AppDirectory "%APP_DIR%"
echo        nssm start CertifikátyApp
echo.
echo ──────────────────────────────────────────────────────────────────────────
echo.
pause
