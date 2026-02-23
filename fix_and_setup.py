"""
🔧 Complete Market Analyst Setup
Cria toda a estrutura necessária
"""

import os
import sys
import shutil
from pathlib import Path

print("=" * 70)
print("🔧 MARKET ANALYST PRO - COMPLETE SETUP")
print("=" * 70)
print()

# ============================================================
# CRIAR ESTRUTURA DE DIRETÓRIOS
# ============================================================

DIRS_TO_CREATE = [
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

print("Creating directory structure...")
for dir_path in DIRS_TO_CREATE:
    os.makedirs(dir_path, exist_ok=True)
    print(f"   OK: {dir_path}")
print()

# ============================================================
# CRIAR __init__.py FILES
# ============================================================

INIT_FILES = [
    'backend/__init__.py',
    'backend/analysts/__init__.py',
    'backend/database/__init__.py',
    'backend/cache/__init__.py',
    'backend/auth/__init__.py',
    'backend/middleware/__init__.py',
    'backend/config/__init__.py',
    'backend/ml/__init__.py',
    'backend/ml/models/__init__.py',
    'backend/ml/training/__init__.py',
    'backend/ml/features/__init__.py',
    'backend/ml/pipelines/__init__.py',
]

print("Creating __init__.py files...")
for file_path in INIT_FILES:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('')
    print(f"   OK: {file_path}")
print()

# ============================================================
# STUB FILES - Para quando você adicionar seus arquivos
# ============================================================

STUB_FILES = {
    'backend/analyst_orchestrator.py': '''"""
Analyst Orchestrator
Placeholder - adicione seu código aqui
"""

class AnalystOrchestrator:
    def __init__(self, config, symbol):
        self.config = config
        self.symbol = symbol
        self.analysts = {}
    
    def feed_tick(self, tick):
        pass
    
    def analyze_marker(self, **kwargs):
        return {}
    
    def get_realtime_status(self):
        return {"analysts": {}}
    
    def reset(self):
        pass
    
    def reset_cluster_deltas(self):
        pass
''',

    'backend/mt5_feed.py': '''"""
MT5 Feed
Placeholder - adicione seu código aqui
"""

SYM_CFG = {
    "XAUUSD": {"step": 0.01, "delta_th": 100},
    "BTCUSD": {"step": 1.0, "delta_th": 50},
}

class MT5Feed:
    def __init__(self, symbol="XAUUSD", weight_mode="price_weighted"):
        self.symbol = symbol
        self.weight_mode = weight_mode
        self.connected = False
    
    def initialize(self):
        return False
    
    def switch_symbol(self, symbol):
        self.symbol = symbol
    
    def set_weight_mode(self, mode):
        self.weight_mode = mode
    
    async def stream(self):
        # Simular ticks
        import asyncio
        import random
        while True:
            await asyncio.sleep(1)
            yield {
                "price": 2650 + random.random(),
                "timestamp": __import__("time").time(),
                "side": random.choice(["buy", "sell"]),
                "volume_synthetic": random.uniform(0.5, 2.0),
                "bid": 2650,
                "ask": 2651,
            }
    
    def shutdown(self):
        pass
''',

    'backend/ai_synthesizer.py': '''"""
AI Synthesizer
Placeholder - adicione seu código aqui
"""

class AISynthesizer:
    def __init__(self):
        self.available = False
    
    def set_api_key(self, key):
        pass
    
    def is_available(self):
        return False
    
    def synthesize(self, **kwargs):
        return None
    
    def get_stats(self):
        return {"available": False}
''',

    'backend/analysts/__init__.py': '''"""Analysts module"""

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
        self.cluster_counter = 0
    
    def feed_tick(self, tick):
        pass
    
    def on_cluster_close(self, **kwargs):
        class Result:
            classification = "NEUTRO"
            confidence = 0.5
            description = "Test cluster"
            details = {
                "cluster_id": 1,
                "price_open": 0,
                "price_close": 0,
                "price_high": 0,
                "price_low": 0,
                "delta_final": 0,
                "delta_max": 0,
                "delta_min": 0,
                "delta_direction": "neutral",
                "vol_total": 0,
                "vol_buy": 0,
                "vol_sell": 0,
                "duration_s": 0,
                "wick_top": 0,
                "wick_bot": 0,
                "ticks_per_sec": 0,
                "vol_efficiency": 0,
                "pattern": {},
                "liquidity_break": None,
            }
        return Result()
    
    def get_realtime_status(self):
        return {"total_clusters": 0}
    
    def switch_symbol(self, symbol):
        pass
    
    def reset(self):
        pass
''',

    'backend/database/repository.py': '''"""Database Repository - SQLite"""

import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, database_url=None):
        self.db_path = "market_analyst.db"
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER PRIMARY KEY,
                cluster_id INTEGER,
                symbol TEXT,
                price_open REAL,
                price_close REAL,
                delta_final REAL,
                vol_total REAL,
                duration_seconds REAL,
                timestamp_close TIMESTAMP,
                pattern TEXT,
                outcome TEXT DEFAULT 'PENDENTE'
            )
        """)
        conn.commit()
        conn.close()
    
    def get_session(self):
        return sqlite3.connect(self.db_path)
    
    def save_cluster(self, cluster_data):
        conn = self.get_session()
        c = conn.cursor()
        c.execute("""
            INSERT INTO clusters
            (cluster_id, symbol, price_open, price_close, delta_final, vol_total, duration_seconds, timestamp_close, pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cluster_data.get('cluster_id'),
            cluster_data.get('symbol'),
            cluster_data.get('price_open'),
            cluster_data.get('price_close'),
            cluster_data.get('delta_final'),
            cluster_data.get('vol_total'),
            cluster_data.get('duration_seconds'),
            datetime.now(),
            cluster_data.get('pattern', 'UNKNOWN'),
        ))
        conn.commit()
        conn.close()
    
    def get_clusters(self, symbol, limit=100):
        conn = self.get_session()
        c = conn.cursor()
        c.execute("SELECT * FROM clusters WHERE symbol=? ORDER BY timestamp_close DESC LIMIT ?", (symbol, limit))
        rows = c.fetchall()
        conn.close()
        return rows
''',

    'backend/cache/redis_client.py': '''"""Redis Cache"""

import json

class RedisCache:
    def __init__(self, url=None):
        self.cache = {}
    
    def set(self, key, value, ttl_seconds=3600):
        self.cache[key] = value
        return True
    
    def get(self, key):
        return self.cache.get(key)
    
    def delete(self, key):
        if key in self.cache:
            del self.cache[key]
        return True
''',

    'backend/config/logging_config.py': '''"""Logging Configuration"""

import logging
import os

def setup_logging(log_dir="logs", log_level=None):
    if log_level is None:
        log_level = os.environ.get("LOG_LEVEL", "INFO")
    
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='[%(asctime)s] [%(levelname)-8s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "backend.log"), encoding='utf-8')
        ]
    )
''',

    'backend/ml/config.py': '''"""ML Config"""

import os

class MLConfig:
    MODELS_DIR = os.environ.get("ML_MODELS_DIR", "models")
    DATA_DIR = os.environ.get("ML_DATA_DIR", "data")
    OUTCOME_ENABLED = os.environ.get("ML_OUTCOME_ENABLED", "False") == "True"
    PATTERN_ENABLED = os.environ.get("ML_PATTERN_ENABLED", "False") == "True"

ml_config = MLConfig()
''',

    'backend/ml/pipelines/inference.py': '''"""ML Inference Pipeline"""

class MLInferencePipeline:
    def __init__(self):
        self.outcomes_loaded = False
        self.patterns_loaded = False
    
    def predict(self, cluster):
        return {'success': False, 'ml_predictions': {}}
    
    def get_status(self):
        return {'pipeline_active': False}

ml_pipeline = MLInferencePipeline()
''',

    'backend/ml/features/feature_engineering.py': '''"""Feature Engineering"""

import numpy as np

class FeatureExtractor:
    def extract_from_cluster(self, cluster):
        return np.array([1.0] * 10)
    
    def extract_batch(self, clusters):
        return np.array([[1.0] * 10 for _ in clusters])
''',

    'backend/ml/models/outcome_predictor.py': '''"""Outcome Predictor"""

class OutcomePredictor:
    def __init__(self, model_path=None):
        self.model = None
        self.is_trained = False
    
    def load_model(self):
        return False
    
    def predict(self, cluster):
        return "NEUTRAL", 0.5
    
    def train(self, X, y):
        return False
''',

    'backend/ml/models/pattern_classifier.py': '''"""Pattern Classifier"""

class PatternClassifier:
    def __init__(self, model_path=None):
        self.model = None
        self.is_trained = False
    
    def load_model(self):
        return False
    
    def predict(self, cluster):
        return "NEUTRO", 0.5
    
    def train(self, X, y):
        return False
''',
}

print("Creating stub files...")
for file_path, content in STUB_FILES.items():
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   OK: {file_path}")
print()

# ============================================================
# REQUIREMENTS.TXT
# ============================================================

REQUIREMENTS = '''websockets>=12.0
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

print("Creating requirements.txt...")
with open("requirements.txt", "w", encoding='utf-8') as f:
    f.write(REQUIREMENTS)
print("   OK: requirements.txt created")
print()

# ============================================================
# WEBSOCKET_SERVER.PY COMPLETO E FUNCIONAL
# ============================================================

WEBSOCKET = '''"""
WebSocket Server - Market Analyst Pro
Versao Completa Funcional
"""

import asyncio
import json
import time
import os
import sys
import logging
from pathlib import Path

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
    logger.error("ERROR: websockets not found. Install: pip install websockets")
    sys.exit(1)

# Adicionar o diretório atual ao sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger.info("=" * 60)
logger.info("MARKET ANALYST PRO - WebSocket Server")
logger.info("=" * 60)
logger.info("")

# ============================================================
# IMPORTS COM TRATAMENTO DE ERRO
# ============================================================

try:
    from backend.analyst_orchestrator import AnalystOrchestrator
    logger.info("OK: Analyst Orchestrator loaded")
except Exception as e:
    logger.error(f"ERROR: Failed to load Orchestrator: {e}")
    AnalystOrchestrator = None

try:
    from backend.mt5_feed import MT5Feed, SYM_CFG
    logger.info("OK: MT5 Feed loaded")
except Exception as e:
    logger.error(f"ERROR: Failed to load MT5 Feed: {e}")
    MT5Feed = None
    SYM_CFG = {}

try:
    from backend.ai_synthesizer import AISynthesizer
    logger.info("OK: AI Synthesizer loaded")
except Exception as e:
    logger.warning(f"WARNING: AI Synthesizer not available: {e}")
    AISynthesizer = None

try:
    from backend.analysts import ClusterClosureAnalyst
    logger.info("OK: Cluster Closure Analyst loaded")
except Exception as e:
    logger.error(f"ERROR: Failed to load Cluster Closure: {e}")
    ClusterClosureAnalyst = None

# Database (optional)
try:
    from backend.database.repository import Database
    db = Database()
    logger.info("OK: Database loaded (SQLite)")
except Exception as e:
    logger.warning(f"WARNING: Database not available: {e}")
    db = None

logger.info("")

# ============================================================
# CONFIG
# ============================================================

WS_PORT = int(os.environ.get("WS_PORT", 8766))
SYMBOL = os.environ.get("SYMBOL", "XAUUSD")
WEIGHT_MODE = os.environ.get("WEIGHT_MODE", "price_weighted")

sym_cfg = SYM_CFG.get(SYMBOL, {"step": 0.01, "delta_th": 100})

logger.info(f"WebSocket Port: {WS_PORT}")
logger.info(f"Symbol: {SYMBOL}")
logger.info(f"Weight Mode: {WEIGHT_MODE}")
logger.info(f"Database: OK (SQLite)")
logger.info("")

# ============================================================
# INITIALIZE
# ============================================================

if MT5Feed:
    feed = MT5Feed(symbol=SYMBOL, weight_mode=WEIGHT_MODE)
else:
    logger.error("Cannot initialize without MT5Feed")
    sys.exit(1)

if AnalystOrchestrator:
    orchestrator = AnalystOrchestrator(
        config={
            "imbalance": {"price_step": sym_cfg["step"], "imbalance_ratio": 3.0},
            "volume_profile": {"price_step": sym_cfg["step"]},
            "absorption": {"window_ms": 100},
            "execution_style": {},
        },
        symbol=SYMBOL,
    )
else:
    logger.error("Cannot initialize without AnalystOrchestrator")
    sys.exit(1)

if ClusterClosureAnalyst:
    closure_analyst = ClusterClosureAnalyst(config={
        "max_clusters": 500,
        "symbol": SYMBOL,
    })
else:
    logger.error("Cannot initialize without ClusterClosureAnalyst")
    sys.exit(1)

ai_synthesizer = AISynthesizer() if AISynthesizer else None

# ============================================================
# STATE
# ============================================================

cluster_state = {"delta": 0.0, "open_price": 0.0, "open_ts": 0.0, "tick_count": 0}
clients = set()
tick_counter = 0

# ============================================================
# FUNCTIONS
# ============================================================

def _get_delta_th():
    return sym_cfg.get("delta_th", 100)

async def _safe_send(websocket, payload: str) -> bool:
    try:
        await asyncio.wait_for(websocket.send(payload), timeout=2.0)
        return True
    except Exception as e:
        logger.warning(f"WARNING: Send failed: {str(e)[:50]}")
        clients.discard(websocket)
        return False

async def _broadcast_payload(payload: str):
    if not clients:
        return
    await asyncio.gather(
        *[_safe_send(c, payload) for c in list(clients)],
        return_exceptions=True
    )

async def handle_client(websocket, path=None):
    clients.add(websocket)
    client_id = id(websocket) % 1000
    logger.info(f"CLIENT [{client_id}] connected ({len(clients)} total)")

    try:
        await _safe_send(websocket, json.dumps({
            "type": "connected",
            "data": {
                "source": "mt5" if feed.connected else "simulation",
                "symbol": feed.symbol,
            }
        }))

        async for message in websocket:
            try:
                data = json.loads(message)
                t = data.get("type", "")

                if t == "get_status":
                    status = orchestrator.get_realtime_status()
                    await websocket.send(json.dumps({"type": "status", "data": status}))
                elif t == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                logger.warning(f"WARNING: Invalid JSON from {client_id}")
            except Exception as e:
                logger.warning(f"WARNING: Handler error: {str(e)[:50]}")

    except websockets.ConnectionClosed:
        logger.info(f"CLIENT [{client_id}] disconnected")
    except Exception as e:
        logger.warning(f"WARNING: Client error: {str(e)[:50]}")
    finally:
        clients.discard(websocket)

# ============================================================
# TICK PROCESSOR
# ============================================================

async def broadcast_tick(tick_data):
    global tick_counter, cluster_state

    tick_counter += 1
    ts = tick_data.get("timestamp", time.time())
    if ts > 1e12:
        ts = ts / 1000.0

    vol = tick_data.get("volume_synthetic", 1.0)
    side = tick_data.get("side", "")

    if side == "buy":
        cluster_state["delta"] += vol
    elif side == "sell":
        cluster_state["delta"] -= vol

    closure_analyst.feed_tick(tick_data)

    delta_th = _get_delta_th()

    if abs(cluster_state["delta"]) >= delta_th:
        try:
            result = closure_analyst.on_cluster_close(
                close_price=tick_data.get("price", 0),
                close_ts=ts,
                analyst_signals={},
            )
            
            if db:
                try:
                    db.save_cluster({
                        'cluster_id': result.details.get('cluster_id'),
                        'symbol': feed.symbol,
                        'price_open': result.details.get('price_open', 0),
                        'price_close': result.details.get('price_close', 0),
                        'delta_final': result.details.get('delta_final', 0),
                        'vol_total': result.details.get('vol_total', 0),
                        'duration_seconds': result.details.get('duration_seconds', 0),
                        'pattern': result.classification,
                    })
                except Exception as e:
                    logger.warning(f"WARNING: DB save error: {str(e)[:50]}")
            
        except Exception as e:
            logger.error(f"ERROR: on_cluster_close: {str(e)[:50]}")
            cluster_state.update({
                "delta": 0.0,
                "open_price": tick_data.get("price", 0),
                "open_ts": ts,
                "tick_count": 0,
            })
            return

        cluster_state.update({
            "delta": 0.0,
            "open_price": tick_data.get("price", 0),
            "open_ts": ts,
            "tick_count": 0,
        })

        if clients:
            msg = json.dumps({
                "type": "cluster_closed",
                "data": {
                    "cluster_id": result.details.get("cluster_id"),
                    "pattern": result.classification,
                    "delta": result.details.get("delta_final"),
                }
            }, default=str)
            await _broadcast_payload(msg)

    if tick_counter % 100 == 0:
        logger.info(f"TICK #{tick_counter} | Clients: {len(clients)} | Price: {tick_data.get('price', 0):.2f}")

    if clients:
        msg = json.dumps({"type": "tick", "data": tick_data})
        await _broadcast_payload(msg)

# ============================================================
# MAIN
# ============================================================

async def tick_processor():
    logger.info("Starting tick processor...")
    async for tick in feed.stream():
        try:
            orchestrator.feed_tick(tick)
        except Exception as e:
            logger.warning(f"WARNING: Orchestrator error: {str(e)[:50]}")
        try:
            await broadcast_tick(tick)
        except Exception as e:
            logger.warning(f"WARNING: Broadcast error: {str(e)[:50]}")

async def main():
    if not feed.initialize():
        logger.warning("WARNING: MT5 not available - using simulation")

    async with websockets.serve(handle_client, "0.0.0.0", WS_PORT):
        logger.info(f"OK: WebSocket running on ws://0.0.0.0:{WS_PORT}")
        logger.info("")
        await tick_processor()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Server stopped")
'''

print("Creating backend/websocket_server.py...")
with open("backend/websocket_server.py", "w", encoding='utf-8') as f:
    f.write(WEBSOCKET)
print("   OK: websocket_server.py created")
print()

# ============================================================
# .ENV.EXAMPLE
# ============================================================

ENV = '''DATABASE_URL=sqlite:///market_analyst.db
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

print("Creating .env.example...")
with open(".env.example", "w", encoding='utf-8') as f:
    f.write(ENV)
print("   OK: .env.example created")
print()

# ============================================================
# START.BAT
# ============================================================

BAT = '''@echo off
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

print("Creating start.bat...")
with open("start.bat", "w", encoding='utf-8') as f:
    f.write(BAT)
print("   OK: start.bat created")
print()

print("=" * 70)
print("OK: SETUP COMPLETE!")
print("=" * 70)
print()
print("Next steps:")
print("   1. .\\start.bat")
print()
print("Or manually:")
print("   python -m venv venv")
print("   .\\venv\\Scripts\\activate")
print("   pip install -r requirements.txt")
print("   python backend/websocket_server.py")
print()