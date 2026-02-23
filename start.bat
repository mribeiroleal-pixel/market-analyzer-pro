@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Market Analyst Pro - Windows Setup
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)
echo OK: Python found

if not exist "venv" (
    python -m venv venv
    echo OK: Virtual environment created
) else (
    echo OK: Virtual environment exists
)

call venv\Scripts\activate.bat
echo OK: Virtual environment activated

python -m pip install --upgrade pip --quiet

echo.
echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo OK: Dependencies installed

if not exist ".env" (
    copy .env.example .env >nul
    echo OK: .env created
)

echo.
echo ========================================
echo   OK: Setup Complete!
echo ========================================
echo.
echo Starting server...
echo WebSocket: ws://localhost:8766
echo.

python backend/websocket_server.py

pause
