@echo off
chcp 65001 >nul
echo ============================================
echo   Deploy - Evidence Certifikatu
echo ============================================
echo.

REM Zjistíme cestu ke složce kde leží tento skript
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM Kontrola Pythonu
python --version >nul 2>&1
if errorlevel 1 (
    echo [CHYBA] Python nebyl nalezen! Nainstalujte Python 3.12+ a přidejte ho do PATH.
    pause
    exit /b 1
)
echo [OK] Python nalezen

REM Vytvoření virtuálního prostředí
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

REM Offline instalace závislostí z dependencies/
echo [INFO] Instaluji závislosti offline z dependencies/...
venv\Scripts\python.exe -m pip install --no-index --find-links=dependencies -r requirements.txt
if errorlevel 1 (
    echo [CHYBA] Instalace závislostí selhala!
    pause
    exit /b 1
)
echo [OK] Závislosti nainstalovány

REM Vytvoření potřebných složek
if not exist "logs" mkdir logs
if not exist "uploads" mkdir uploads
if not exist "instance" mkdir instance
echo [OK] Složky vytvořeny

echo.
echo ============================================
echo   Deploy dokončen!
echo ============================================
echo.
echo Pro spuštění aplikace:
echo   venv\Scripts\python.exe app.py
echo.
echo Nebo přes waitress (produkce):
echo   venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=8080 app:app
echo.
echo IIS by měl směrovat na http://localhost:8080
echo.
pause
