@echo off
chcp 65001 >nul
echo ============================================
echo   Balení aplikace pro přenos
echo ============================================
echo.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM ── Vygenerování VERSION.txt ───────────────────────────────────────────────
echo [INFO] Generuji VERSION.txt...
for /f %%G in ('git rev-parse --short HEAD 2^>nul') do set "GIT_HASH=%%G"
if "%GIT_HASH%"=="" set "GIT_HASH=unknown"
for /f %%D in ('git log -1 --format^=%%ci 2^>nul') do set "GIT_DATE=%%D"
set "BUILD_DATE=%date% %time:~0,5%"
(
    echo Verze:      %GIT_HASH%
    echo Commit:     %GIT_DATE%
    echo Zabaleno:   %BUILD_DATE%
) > VERSION.txt
echo [OK] VERSION.txt vytvořen ^(%GIT_HASH%^)

REM ── Aktualizace offline závislostí ────────────────────────────────────────
echo [INFO] Stahuji závislosti do dependencies/...
if not exist "dependencies" mkdir dependencies
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m pip download -r requirements.txt -d dependencies --quiet
) else (
    python -m pip download -r requirements.txt -d dependencies --quiet
)
echo [OK] Závislosti aktualizovány

REM ── Vytvoření ZIP balíčku ──────────────────────────────────────────────────
set "ZIPNAME=certifikaty_deploy_%date:~6,4%%date:~3,2%%date:~0,2%_%GIT_HASH%.zip"
echo [INFO] Vytvářím %ZIPNAME%...

REM Smazat starý ZIP se stejným názvem (pokud existuje)
if exist "%ZIPNAME%" del "%ZIPNAME%"

powershell -NoProfile -Command ^
    "Compress-Archive -Force -Path 'app','static','dependencies','*.py','*.txt','*.bat','*.example' -DestinationPath '%ZIPNAME%'"

if exist "%ZIPNAME%" (
    for %%A in ("%ZIPNAME%") do set "ZIP_SIZE=%%~zA"
    set /a "ZIP_MB=%ZIP_SIZE% / 1048576"
    echo [OK] Balíček vytvořen: %ZIPNAME%
    echo.
    echo ── Obsah balíčku ─────────────────────────────────────────
    echo   Kód aplikace:  app\, static\, *.py
    echo   Závislosti:    dependencies\  ^(offline pip install^)
    echo   Skripty:       deploy.bat, update.bat
    echo   Verze:         VERSION.txt ^(%GIT_HASH%^)
    echo.
    echo   NEZAHRNUTO:    instance\  ^(databáze^)
    echo                  logs\      ^(logy^)
    echo                  uploads\   ^(nahrané soubory^)
    echo                  .env       ^(konfigurace^)
    echo ──────────────────────────────────────────────────────────
    echo.
    echo Na cílovém serveru:
    echo   1. Zkopíruj %ZIPNAME% do složky aplikace
    echo   2. Spusť jako Administrator:
    echo      update.bat [NazevAppPoolu] %ZIPNAME%
    echo.
    echo Příklad:
    echo   update.bat CertifikátyPool %ZIPNAME%
) else (
    echo [CHYBA] Nepodařilo se vytvořit ZIP!
)

echo.
pause
