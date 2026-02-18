@echo off
chcp 65001 >nul
echo ============================================
echo   Balení aplikace pro přenos
echo ============================================
echo.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM Aktualizace offline závislostí
echo [INFO] Stahuji závislosti do dependencies/...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m pip download -r requirements.txt -d dependencies
) else (
    python -m pip download -r requirements.txt -d dependencies
)
echo [OK] Závislosti aktualizovány

REM Vytvoření ZIP balíčku (PowerShell)
set "ZIPNAME=certifikaty_deploy_%date:~6,4%%date:~3,2%%date:~0,2%.zip"
echo [INFO] Vytvářím %ZIPNAME%...

powershell -Command "Compress-Archive -Force -Path 'app','static','dependencies','uploads','*.py','*.txt','*.config','*.bat','*.example','.gitignore' -DestinationPath '%ZIPNAME%'"

if exist "%ZIPNAME%" (
    echo [OK] Balíček vytvořen: %ZIPNAME%
    echo.
    echo Na cílovém stroji:
    echo   1. Rozbalte ZIP
    echo   2. Spusťte deploy.bat
) else (
    echo [CHYBA] Nepodařilo se vytvořit ZIP!
)

echo.
pause
