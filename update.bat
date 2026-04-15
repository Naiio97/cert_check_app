@echo off
chcp 65001 >nul
echo ============================================
echo   Update - Evidence Certifikatu
echo ============================================
echo.
echo Tento skript aktualizuje existující instalaci.
echo Data (databáze, logy, .env) zůstanou zachovány.
echo.
echo Použití: update.bat [NazevAppPoolu] [cesta\k\balicku.zip] [NazevNSSMSluzby]
echo Příklad: update.bat CertifikátyPool certifikaty_deploy_20260415.zip CertifikátyApp
echo.
echo Pokud název ZIP vynecháš, skript najde nejnovější balíček automaticky.
echo Pokud název NSSM služby vynecháš, bude použita výchozí hodnota CertifikátyApp.
echo.

REM ── Parametry ──────────────────────────────────────────────────────────────
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

set "POOL_NAME=%~1"
set "ZIP_PATH=%~2"
set "NSSM_SERVICE=%~3"

if "%POOL_NAME%"=="" (
    set /p POOL_NAME="Název IIS Application Poolu: "
)
if "%POOL_NAME%"=="" (
    echo [CHYBA] Název app poolu je povinný!
    pause
    exit /b 1
)

if "%ZIP_PATH%"=="" (
    echo Hledám nejnovější balíček...
    for /f "delims=" %%F in ('dir /b /o-d certifikaty_deploy_*.zip 2^>nul') do (
        set "ZIP_PATH=%%F"
        goto :found_zip
    )
    echo [CHYBA] Žádný balíček certifikaty_deploy_*.zip nenalezen.
    echo Zkopíruj ZIP soubor do: %APP_DIR%
    pause
    exit /b 1
    :found_zip
    echo [INFO] Nalezen balíček: %ZIP_PATH%
)

if "%NSSM_SERVICE%"=="" (
    set "NSSM_SERVICE=CertifikátyApp"
)

if not exist "%ZIP_PATH%" (
    echo [CHYBA] Soubor '%ZIP_PATH%' nenalezen!
    pause
    exit /b 1
)

REM ── Kontrola oprávnění (appcmd vyžaduje administrátora) ────────────────────
set "APPCMD=%SystemRoot%\system32\inetsrv\appcmd.exe"
if not exist "%APPCMD%" (
    echo [CHYBA] appcmd.exe nenalezen.
    echo Spusť skript jako Administrator a ověř, že je nainstalováno IIS.
    pause
    exit /b 1
)

echo.
echo Konfigurace:
echo   IIS App Pool:   %POOL_NAME%
echo   NSSM Služba:    %NSSM_SERVICE%
echo   Balíček:        %ZIP_PATH%
echo.

REM ── [1/6] Zastavit IIS Application Pool ───────────────────────────────────
echo [1/6] Zastavuji IIS app pool '%POOL_NAME%'...
"%APPCMD%" stop apppool /apppool.name:"%POOL_NAME%" >nul 2>&1
echo [OK] IIS app pool zastaven (nebo již stál)

REM ── [2/6] Zastavit NSSM / Waitress službu ─────────────────────────────────
echo [2/6] Zastavuji Waitress službu '%NSSM_SERVICE%'...
nssm status "%NSSM_SERVICE%" >nul 2>&1
if errorlevel 1 (
    echo [INFO] NSSM služba '%NSSM_SERVICE%' nenalezena, přeskakuji.
    set "NSSM_FOUND=0"
) else (
    nssm stop "%NSSM_SERVICE%" confirm >nul 2>&1
    echo [OK] Waitress služba zastavena
    set "NSSM_FOUND=1"
)

REM ── [3/6] Extrakce balíčku přes stávající instalaci ───────────────────────
echo [3/6] Extrahuji %ZIP_PATH%...
powershell -NoProfile -Command ^
    "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%APP_DIR%' -Force"
if errorlevel 1 (
    echo [CHYBA] Extrakce selhala!
    if "%NSSM_FOUND%"=="1" nssm start "%NSSM_SERVICE%" >nul 2>&1
    "%APPCMD%" start apppool /apppool.name:"%POOL_NAME%" >nul 2>&1
    pause
    exit /b 1
)
echo [OK] Soubory aktualizovány

REM ── [4/6] Instalace závislostí ─────────────────────────────────────────────
echo [4/6] Instaluji závislosti...
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtuální prostředí nenalezeno, vytvářím...
    python -m venv venv
)
venv\Scripts\python.exe -m pip install --no-index --find-links=dependencies -r requirements.txt --quiet
if errorlevel 1 (
    echo [VAROVÁNÍ] Instalace závislostí selhala. Pokračuji...
) else (
    echo [OK] Závislosti aktualizovány
)

REM ── [5/6] Migrace databází (vytvoří nové tabulky, zachová existující data) ─
echo [5/6] Migrace databází (live, uat, sit, prelive)...
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('[OK] DB: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
if errorlevel 1 (
    echo [VAROVÁNÍ] DB migrace selhala - tabulky budou ověřeny při startu aplikace.
) else (
    echo [OK] Databáze migrovány
)

REM ── [6/6] Spustit NSSM / Waitress a IIS pool ──────────────────────────────
echo [6/6] Spouštím aplikaci...
if "%NSSM_FOUND%"=="1" (
    nssm start "%NSSM_SERVICE%" >nul 2>&1
    if errorlevel 1 (
        echo [CHYBA] Waitress službu '%NSSM_SERVICE%' se nepodařilo spustit!
        echo         Zkontroluj: nssm status %NSSM_SERVICE%
        "%APPCMD%" start apppool /apppool.name:"%POOL_NAME%" >nul 2>&1
        pause
        exit /b 1
    )
    echo [OK] Waitress služba spuštěna
    REM Krátká pauza aby Waitress stačil naslouchat dříve než IIS pool přijme requesty
    timeout /t 3 /nobreak >nul
) else (
    echo [INFO] NSSM služba nebyla nalezena.
    echo [INFO] Spusť Waitress ručně nebo zkontroluj DEPLOY.md (sekce 5.4).
)
"%APPCMD%" start apppool /apppool.name:"%POOL_NAME%"
if errorlevel 1 (
    echo [CHYBA] IIS app pool se nepodařilo spustit! Zkontroluj IIS Manager.
    pause
    exit /b 1
)
echo [OK] IIS app pool spuštěn

REM ── Verze ───────────────────────────────────────────────────────────────────
echo.
if exist "VERSION.txt" (
    echo Nasazená verze:
    type VERSION.txt
)

echo.
echo ============================================
echo   Update dokončen!
echo ============================================
echo.
pause
