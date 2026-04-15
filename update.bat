@echo off
chcp 65001 >nul
echo ============================================
echo   Update - Evidence Certifikatu
echo ============================================
echo.
echo Tento skript aktualizuje existující instalaci.
echo Data (databáze, logy, .env) zůstanou zachovány.
echo.
echo Použití: update.bat [NazevAppPoolu] [cesta\k\balicku.zip]
echo Příklad: update.bat CertifikátyPool certifikaty_deploy_20260415.zip
echo.

REM ── Parametry ──────────────────────────────────────────────────────────────
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

set "POOL_NAME=%~1"
set "ZIP_PATH=%~2"

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
echo [1/4] Zastavuji app pool '%POOL_NAME%'...
"%APPCMD%" stop apppool /apppool.name:"%POOL_NAME%" >nul 2>&1
echo [OK] App pool zastaven (nebo již stál)

REM ── Extrakce balíčku přes stávající instalaci ──────────────────────────────
echo [2/4] Extrahuji %ZIP_PATH%...
powershell -NoProfile -Command ^
    "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%APP_DIR%' -Force"
if errorlevel 1 (
    echo [CHYBA] Extrakce selhala!
    "%APPCMD%" start apppool /apppool.name:"%POOL_NAME%" >nul 2>&1
    pause
    exit /b 1
)
echo [OK] Soubory aktualizovány

REM ── Instalace závislostí ────────────────────────────────────────────────────
echo [3/4] Instaluji závislosti...
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

REM ── Spuštění app poolu ──────────────────────────────────────────────────────
echo [4/4] Spouštím app pool '%POOL_NAME%'...
"%APPCMD%" start apppool /apppool.name:"%POOL_NAME%"
if errorlevel 1 (
    echo [CHYBA] App pool se nepodařilo spustit! Zkontroluj IIS Manager.
    pause
    exit /b 1
)
echo [OK] Aplikace běží

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
