"""
🔧 Fix - Corrige erro de porta em uso
"""

import os
import sys
import subprocess

print("=" * 70)
print("🔧 CORRIGINDO ERRO DE PORTA")
print("=" * 70)
print()

# ============================================================
# ENCONTRAR PROCESSO NA PORTA
# ============================================================

print("Procurando processo na porta 8766...")

# Windows
result = subprocess.run(
    ["netstat", "-ano"],
    capture_output=True,
    text=True
)

lines = result.stdout.split('\n')
found_process = False

for line in lines:
    if '8766' in line:
        print(f"Encontrado: {line}")
        parts = line.split()
        if len(parts) > 0:
            try:
                pid = parts[-1]
                if pid.isdigit():
                    print(f"PID: {pid}")
                    print()
                    print("Encerrando processo...")
                    os.system(f"taskkill /PID {pid} /F")
                    found_process = True
                    print("✅ Processo encerrado")
            except:
                pass

if not found_process:
    print("Nenhum processo encontrado na porta 8766")

print()

# ============================================================
# CORRIGIR WEBSOCKET_SERVER.PY
# ============================================================

print("Corrigindo websocket_server.py...")

# Remover arquivo duplicado se existir
if os.path.exists("backend/backend/websocket_server.py"):
    os.remove("backend/backend/websocket_server.py")
    print("   ✅ Removido: backend/backend/websocket_server.py (duplicado)")

# Corrigir caminho
if not os.path.exists("backend/websocket_server.py"):
    print("   ❌ backend/websocket_server.py não encontrado!")
else:
    print("   ✅ backend/websocket_server.py OK")

print()

# ============================================================
# CRIAR START.BAT CORRIGIDO
# ============================================================

print("Criando start.bat corrigido...")

start_bat = '''@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Market Analyst Pro - Windows Setup
echo ========================================
echo.

REM Kill any process on port 8766
echo Liberando porta 8766...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8766') do (
    taskkill /PID %%a /F 2>nul
)

timeout /t 2 /nobreak

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

call venv\\Scripts\\activate.bat
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

cd /d %~dp0
python backend/websocket_server.py

pause
'''

with open("start.bat", "w", encoding='utf-8') as f:
    f.write(start_bat)
print("   ✅ start.bat atualizado")

print()

# ============================================================
# CRIAR INIT FILE CORRETO
# ============================================================

print("Criando backend/__init__.py...")

init_py = '''"""Backend Module"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
'''

with open("backend/__init__.py", "w", encoding='utf-8') as f:
    f.write(init_py)
print("   ✅ backend/__init__.py criado")

print()

print("=" * 70)
print("✅ CORRECAO COMPLETA!")
print("=" * 70)
print()
print("Agora execute: .\\start.bat")
print()