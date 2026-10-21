@echo off
chcp 65001 >nul

REM Skript se pri aktualizaci prepise sam (rozbalenim balicku). cmd cte batch soubor postupne
REM po bajtech, takze zmena souboru za behu rozbije dalsi radky ("... is not recognized").
REM Proto se skutecna aktualizace pousti z docasne kopie.
if not defined UPDATE_FROM_TEMP (
    set "UPDATE_APP_DIR=%~dp0"
    set "UPDATE_FROM_TEMP=1"
    copy /y "%~f0" "%TEMP%\cert_update_run.bat" >nul
    call "%TEMP%\cert_update_run.bat" %* & exit /b
)
echo ============================================
echo   Update - Evidence Certifikatu
echo ============================================
echo.
echo Data (databaze, logy, .env) zustanou zachovany.
echo.
echo Pouziti: update.bat [NazevNSSMSluzby] [balicek.zip]
echo Priklad: update.bat CertifikatyApp certifikaty_deploy_20260415.zip
echo.

set "APP_DIR=%UPDATE_APP_DIR%"
if not defined APP_DIR set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

set "NSSM_SERVICE=%~1"
set "ZIP_PATH=%~2"

if "%NSSM_SERVICE%"=="" (
    set /p NSSM_SERVICE="Nazev NSSM sluzby (Windows Services): "
)
if "%NSSM_SERVICE%"=="" (
    echo [CHYBA] Nazev sluzby je povinny!
    pause
    exit /b 1
)

if "%ZIP_PATH%"=="" (
    echo Hledam nejnovejsi balicek...
    for /f "delims=" %%F in ('dir /b /o-d certifikaty_deploy_*.zip 2^>nul') do (
        set "ZIP_PATH=%%F"
        goto :found_zip
    )
    echo [CHYBA] Zadny balicek certifikaty_deploy_*.zip nenalezen.
    pause
    exit /b 1
    :found_zip
    echo [INFO] Nalezen balicek: %ZIP_PATH%
)

if not exist "%ZIP_PATH%" (
    echo [CHYBA] Soubor '%ZIP_PATH%' nenalezen!
    pause
    exit /b 1
)

echo.
echo Konfigurace:
echo   NSSM Sluzba : %NSSM_SERVICE%
echo   Balicek     : %ZIP_PATH%
echo.

echo [1/6] Zastavuji sluzbu '%NSSM_SERVICE%' ...
nssm stop "%NSSM_SERVICE%" confirm
if errorlevel 1 (
    echo [CHYBA] Sluzbu se nepodarilo zastavit!
    echo         Over nazev: nssm status %NSSM_SERVICE%
    pause
    exit /b 1
)
echo [OK] Sluzba zastavena

echo [2/6] Extrahuji %ZIP_PATH% ...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%APP_DIR%' -Force"
if errorlevel 1 (
    echo [CHYBA] Extrakce selhala!
    nssm start "%NSSM_SERVICE%"
    pause
    exit /b 1
)
echo [OK] Soubory aktualizovany

echo [3/6] Instaluji zavislosti ...
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtualni prostredi nenalezeno, vytvarim...
    python -m venv venv
)
venv\Scripts\python.exe -m pip install --no-index --find-links=dependencies -r requirements.txt --quiet
if errorlevel 1 (
    echo [VAROVANI] Instalace zavislosti selhala. Pokracuji...
) else (
    echo [OK] Zavislosti aktualizovany
)

echo [4/6] Migrace databazi (live, uat, sit, prelive) ...
venv\Scripts\python.exe -c "from app import create_app; from app.db_init import init_databases; app=create_app(); init_databases(app, lambda env, ok, err: print('[OK] DB: ' + env if ok else '[CHYBA] DB: ' + env + ' ' + str(err)))"
if errorlevel 1 (
    echo [VAROVANI] DB migrace selhala - tabulky budou overeny pri startu.
) else (
    echo [OK] Databaze migrovany
)

echo [5/6] Nastavuji sluzbu na waitress ...
REM AppDirectory bez koncoveho zpetneho lomitka (jinak by escapovalo uvozovku)
REM Sluzba drive poustela "python app.py" (werkzeug dev server) - waitress je
REM produkcni server: bez debuggeru, jeden proces, funkcni rotace logu.
nssm set "%NSSM_SERVICE%" Application "%APP_DIR%venv\Scripts\python.exe"
nssm set "%NSSM_SERVICE%" AppParameters "-m waitress --host=0.0.0.0 --port=8080 wsgi:app"
nssm set "%NSSM_SERVICE%" AppDirectory "%APP_DIR:~0,-1%"
if errorlevel 1 (
    echo [VAROVANI] Prenastaveni sluzby selhalo - pojede se stavajici konfiguraci.
) else (
    echo [OK] Sluzba nastavena: waitress, port 8080
)

echo [6/6] Spoustim sluzbu '%NSSM_SERVICE%' ...
nssm start "%NSSM_SERVICE%"
if errorlevel 1 (
    echo [CHYBA] Sluzbu se nepodarilo spustit!
    pause
    exit /b 1
)
echo [OK] Sluzba spustena

echo.
if exist "VERSION.txt" (
    echo Nasazena verze:
    type VERSION.txt
)

echo.
echo ============================================
echo   Update dokoncen!
echo ============================================
echo.
pause