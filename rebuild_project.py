"""
🔧 Rebuild Project - Reconstrói tudo do zero
"""

import os
import sys

print("=" * 70)
print("🔧 RECONSTRUINDO PROJECT")
print("=" * 70)
print()

# ============================================================
# CRIAR ESTRUTURA DE DIRETÓRIOS
# ============================================================

print("Criando estrutura de diretórios...")
print()

dirs = [
    'backend',
    'backend/analysts',
    'backend/database',
    'backend/cache',
    'backend/auth',
    'backend/middleware',
    'backend/config',
    'backend/ml',
    'backend/ml/models',
    'backend/ml/training',
    'backend/ml/features',
    'backend/ml/pipelines',
    'frontend',
    'logs',
    'models',
    'data',
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f"   ✅ {d}")

print()

# ============================================================
# CRIAR ARQUIVOS __init__.py
# ============================================================

print("Criando __init__.py files...")
print()

init_files = {
    'backend/__init__.py': '''"""Backend Module"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
''',

    'backend/analysts/__init__.py': '''"""Analysts Module"""

class BaseAnalyst:
    pass

class AbsorptionAnalyst(BaseAnalyst):
    pass

class LiquiditySweepAnalyst(BaseAnalyst):
    pass

class ImbalanceAnalyst(BaseAnalyst):
    pass

class VolumeProfileAnalyst(BaseAnalyst):
    pass

class ExecutionStyleAnalyst(BaseAnalyst):
    pass

class DeltaFlowAnalyst(BaseAnalyst):
    pass

class ClusterClosureAnalyst(BaseAnalyst):
    def __init__(self, config):
        self.config = config
    
    def feed_tick(self, tick):
        pass
    
    def on_cluster_close(self, **kwargs):
        class Result:
            classification = "NEUTRO"
            confidence = 0.5
            details = {
                "cluster_id": 1,
                "price_open": 0,
                "price_close": 0,
                "delta_final": 0,
            }
        return Result()
    
    def get_realtime_status(self):
        return {}
    
    def switch_symbol(self, symbol):
        pass
''',

    'backend/database/__init__.py': '',
    'backend/cache/__init__.py': '',
    'backend/auth/__init__.py': '',
    'backend/middleware/__init__.py': '',
    'backend/config/__init__.py': '',
    'backend/ml/__init__.py': '',
    'backend/ml/models/__init__.py': '',
    'backend/ml/training/__init__.py': '',
    'backend/ml/features/__init__.py': '',
    'backend/ml/pipelines/__init__.py': '',
}

for filepath, content in init_files.items():
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ {filepath}")

print()

# ============================================================
# CRIAR ARQUIVOS STUB
# ============================================================

print("Criando arquivos stub...")
print()

stub_files = {
    'backend/analyst_orchestrator.py': '''"""Analyst Orchestrator"""

class AnalystOrchestrator:
    def __init__(self, config, symbol):
        self.config = config
        self.symbol = symbol
        self.analysts = {}
    
    def feed_tick(self, tick):
        pass
    
    def get_realtime_status(self):
        return {"analysts": {}}
    
    def reset(self):
        pass
''',

    'backend/mt5_feed.py': '''"""MT5 Feed"""

SYM_CFG = {
    "XAUUSD": {"step": 0.01, "delta_th": 100},
}

class MT5Feed:
    def __init__(self, symbol="XAUUSD", weight_mode="price_weighted"):
        self.symbol = symbol
        self.weight_mode = weight_mode
        self.connected = False
    
    def initialize(self):
        return False
    
    async def stream(self):
        import asyncio
        while True:
            await asyncio.sleep(1)
            yield {}
''',

    'backend/ai_synthesizer.py': '''"""AI Synthesizer"""

class AISynthesizer:
    def __init__(self):
        self.available = False
''',

    'backend/liquidity_break_ml.py': '''"""Liquidity Break ML"""

import json
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class LiquidityBreakDataset:
    def __init__(self, dataset_path: str = "liquidity_breaks_dataset.json"):
        self.dataset_path = dataset_path
        self.data: List[Dict] = []
        self.load()
    
    def load(self):
        if Path(self.dataset_path).exists():
            try:
                with open(self.dataset_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"OK: Dataset carregado: {len(self.data)} quebras")
            except Exception as e:
                logger.error(f"ERROR ao carregar dataset: {e}")
                self.data = []
        else:
            self.data = []
    
    def save(self):
        try:
            with open(self.dataset_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, default=str)
            logger.info(f"OK: Dataset salvo: {len(self.data)} quebras")
        except Exception as e:
            logger.error(f"ERROR ao salvar dataset: {e}")
    
    def add_liquidity_break(self, break_info: Dict) -> bool:
        try:
            break_record = {
                'id': len(self.data) + 1,
                'timestamp': datetime.now().isoformat(),
                **break_info
            }
            self.data.append(break_record)
            self.save()
            logger.info(f"OK: Quebra adicionada: ID #{break_record['id']}")
            return True
        except Exception as e:
            logger.error(f"ERROR ao adicionar quebra: {e}")
            return False
    
    def get_breaks_by_symbol(self, symbol: str) -> List[Dict]:
        return [b for b in self.data if b.get('symbol') == symbol]
    
    def export_for_ml(self) -> Tuple[np.ndarray, np.ndarray]:
        X = []
        y = []
        
        for break_data in self.data:
            if break_data.get('type') not in ['SELLERS_REPRICED_HIGHER', 'BUYERS_REPRICED_LOWER']:
                continue
            
            features = [
                float(break_data.get('delta', 0)),
                float(break_data.get('volume', 0)),
                float(break_data.get('wick_top', 0)),
                float(break_data.get('wick_bot', 0)),
                float(break_data.get('confidence_manual', 0.5)),
                int(break_data.get('is_structural', False)),
            ]
            
            label = 1 if break_data.get('type') == 'SELLERS_REPRICED_HIGHER' else 0
            
            X.append(features)
            y.append(label)
        
        return np.array(X), np.array(y)
    
    def update_break(self, break_id: int, updates: Dict) -> bool:
        try:
            for item in self.data:
                if item.get('id') == break_id:
                    item.update(updates)
                    self.save()
                    logger.info(f"OK: Quebra #{break_id} atualizada")
                    return True
            return False
        except Exception as e:
            logger.error(f"ERROR ao atualizar: {e}")
            return False
    
    def get_stats(self) -> Dict:
        sellers_higher = sum(1 for b in self.data if b.get('type') == 'SELLERS_REPRICED_HIGHER')
        buyers_lower = sum(1 for b in self.data if b.get('type') == 'BUYERS_REPRICED_LOWER')
        structural = sum(1 for b in self.data if b.get('is_structural'))
        
        return {
            'total': len(self.data),
            'sellers_repriced_higher': sellers_higher,
            'buyers_repriced_lower': buyers_lower,
            'structural_breaks': structural,
        }

class LiquidityBreakML:
    def __init__(self, model_path: str = "liquidity_break_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.is_trained = False
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            
            if len(X) < 5:
                logger.error("ERROR: Dados insuficientes (mínimo 5)")
                return False
            
            logger.info(f"OK: Treinando com {len(X)} amostras...")
            
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            self.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            self.model.fit(X_scaled, y)
            
            self.is_trained = True
            self.save()
            
            logger.info("OK: Modelo treinado com sucesso")
            return True
        
        except Exception as e:
            logger.error(f"ERROR ao treinar: {e}")
            return False
    
    def predict(self, delta: float, volume: float, wick_top: float, wick_bot: float, confidence: float = 0.5) -> Tuple[str, float]:
        if not self.is_trained or self.model is None:
            logger.warning("WARNING: Modelo não treinado")
            return None, 0.5
        
        try:
            features = np.array([[delta, volume, wick_top, wick_bot, confidence, 0]])
            X_scaled = self.scaler.transform(features)
            
            pred = self.model.predict(X_scaled)[0]
            probs = self.model.predict_proba(X_scaled)[0]
            prob_confidence = float(np.max(probs))
            
            break_type = 'SELLERS_REPRICED_HIGHER' if pred == 1 else 'BUYERS_REPRICED_LOWER'
            
            return break_type, prob_confidence
        
        except Exception as e:
            logger.error(f"ERROR na predição: {e}")
            return None, 0.5
    
    def save(self):
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({'model': self.model, 'scaler': self.scaler}, f)
            logger.info(f"OK: Modelo salvo: {self.model_path}")
        except Exception as e:
            logger.error(f"ERROR ao salvar: {e}")
    
    def load(self) -> bool:
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.scaler = data['scaler']
                self.is_trained = True
            logger.info(f"OK: Modelo carregado: {self.model_path}")
            return True
        except Exception as e:
            logger.debug(f"INFO: Modelo não encontrado: {e}")
            return False
''',

    'backend/websocket_server.py': '''"""WebSocket Server - Liquidity Break ML"""

import asyncio
import json
import os
import sys
import logging

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/backend.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    logger.error("ERROR: pip install websockets")
    sys.exit(1)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

logger.info("=" * 60)
logger.info("MARKET ANALYST PRO - WebSocket Server")
logger.info("Modo: Liquidity Break ML Only")
logger.info("=" * 60)
logger.info("")

try:
    from liquidity_break_ml import LiquidityBreakDataset, LiquidityBreakML
    logger.info("OK: Liquidity Break ML loaded")
    
    dataset = LiquidityBreakDataset()
    ml_model = LiquidityBreakML()
    ml_model.load()
except Exception as e:
    logger.error(f"ERROR: Liquidity Break ML: {e}")
    sys.exit(1)

logger.info("")

WS_PORT = int(os.environ.get("WS_PORT", 8766))
SYMBOL = os.environ.get("SYMBOL", "XAUUSD")

logger.info(f"WebSocket Port: {WS_PORT}")
logger.info(f"Symbol: {SYMBOL}")
logger.info(f"Liquidity Break Dataset: {len(dataset.data)} quebras")
logger.info("")

clients = set()

async def _safe_send(websocket, payload: str) -> bool:
    try:
        await asyncio.wait_for(websocket.send(payload), timeout=2.0)
        return True
    except Exception as e:
        clients.discard(websocket)
        return False

async def handle_liquidity_break_command(websocket, data):
    command = data.get('command')
    
    try:
        if command == 'add_liquidity_break':
            break_info = {
                'timestamp': data.get('timestamp'),
                'symbol': data.get('symbol', 'XAUUSD'),
                'price_broken': data.get('price_broken'),
                'type': data.get('type'),
                'delta': data.get('delta'),
                'volume': data.get('volume'),
                'wick_top': data.get('wick_top'),
                'wick_bot': data.get('wick_bot'),
                'confidence_manual': data.get('confidence_manual', 0.7),
                'notes': data.get('notes', ''),
                'is_structural': data.get('is_structural', False),
            }
            
            success = dataset.add_liquidity_break(break_info)
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_break_added',
                'success': success,
                'break_id': len(dataset.data) if success else None,
            }))
        
        elif command == 'get_liquidity_breaks':
            symbol = data.get('symbol', 'XAUUSD')
            breaks = dataset.get_breaks_by_symbol(symbol)
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_breaks_list',
                'data': breaks,
                'count': len(breaks),
            }, default=str))
        
        elif command == 'train_liquidity_ml':
            import numpy as np
            X, y = dataset.export_for_ml()
            
            if len(X) < 5:
                await _safe_send(websocket, json.dumps({
                    'type': 'error',
                    'message': f'Dados insuficientes: {len(X)}/5',
                }))
                return
            
            success = ml_model.train(X, y)
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_ml_trained',
                'success': success,
                'samples': len(X),
            }))
        
        elif command == 'get_liquidity_ml_status':
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_ml_status',
                'is_trained': ml_model.is_trained,
                'dataset_size': len(dataset.data),
                'stats': dataset.get_stats(),
            }))
    
    except Exception as e:
        logger.error(f"ERROR in liquidity command: {e}")
        await _safe_send(websocket, json.dumps({
            'type': 'error',
            'message': str(e),
        }))

async def handle_client(websocket, path=None):
    clients.add(websocket)
    client_id = id(websocket) % 1000
    logger.info(f"CLIENT [{client_id}] connected ({len(clients)} total)")

    try:
        await _safe_send(websocket, json.dumps({
            "type": "connected",
            "data": {
                "symbol": SYMBOL,
                "liquidity_break_ml": True,
            }
        }))

        async for message in websocket:
            try:
                data = json.loads(message)
                t = data.get("type", "")
                
                if t == "liquidity_break_command":
                    await handle_liquidity_break_command(websocket, data)
                
                elif t == "ping":
                    await _safe_send(websocket, json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.debug(f"Handler error: {str(e)[:50]}")

    except Exception as e:
        logger.debug(f"Client error: {str(e)[:50]}")
    finally:
        clients.discard(websocket)
        logger.info(f"CLIENT [{client_id}] disconnected")

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", WS_PORT):
        logger.info(f"OK: WebSocket running on ws://0.0.0.0:{WS_PORT}")
        logger.info("")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
''',
}

for filepath, content in stub_files.items():
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ {filepath}")

print()

# ============================================================
# CRIAR REQUIREMENTS.TXT
# ============================================================

print("Criando requirements.txt...")
print()

requirements = '''websockets>=12.0
python-dotenv>=1.0.0
MetaTrader5>=5.0.5572
sqlalchemy>=2.0.23
PyJWT>=2.8.1
pytest>=7.4.3
pytest-asyncio>=0.21.1
xgboost>=2.0.3
scikit-learn>=1.3.2
numpy>=1.24.3
pandas>=2.1.3
'''

with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write(requirements)
print("   ✅ requirements.txt")

print()

# ============================================================
# CRIAR .ENV.EXAMPLE
# ============================================================

print("Criando .env.example...")
print()

env_example = '''DATABASE_URL=sqlite:///market_analyst.db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key
WS_PORT=8766
WS_HOST=0.0.0.0
MT5_ACCOUNT=12345678
MT5_PASSWORD=password
MT5_SERVER=ExnessMT5Real
SYMBOL=XAUUSD
WEIGHT_MODE=price_weighted
GROQ_API_KEY=your-api-key
LOG_LEVEL=INFO
LOG_DIR=logs
ENABLE_DB=True
ENABLE_ML=False
ENABLE_CACHE=False
'''

with open('.env.example', 'w', encoding='utf-8') as f:
    f.write(env_example)
print("   ✅ .env.example")

print()

# ============================================================
# CRIAR START.BAT
# ============================================================

print("Criando start.bat...")
print()

start_bat = '''@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Market Analyst Pro - Windows Setup
echo ========================================
echo.

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

python backend/websocket_server.py

pause
'''

with open('start.bat', 'w', encoding='utf-8') as f:
    f.write(start_bat)
print("   ✅ start.bat")

print()

print("=" * 70)
print("✅ PROJECT RECONSTRUIDO COM SUCESSO!")
print("=" * 70)
print()

print("Estrutura criada:")
print()
for root, dirs, files in os.walk("backend"):
    level = root.replace("backend", "").count(os.sep)
    indent = "   " * level
    print(f"{indent}{os.path.basename(root)}/")
    
    subindent = "   " * (level + 1)
    for file in files[:3]:
        print(f"{subindent}{file}")
    
    if len(files) > 3:
        print(f"{subindent}... +{len(files) - 3} files")

print()
print("Próximos passos:")
print("   1. python create_initial_model.py")
print("   2. .\\start.bat")
print()