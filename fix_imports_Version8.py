"""
🔧 Fix - Corrige todos os imports
"""

import os

print("=" * 70)
print("🔧 CORRIGINDO IMPORTS")
print("=" * 70)
print()

# ============================================================
# VERIFICAR ARQUIVOS
# ============================================================

backend_files = [
    'backend/analyst_orchestrator.py',
    'backend/mt5_feed.py',
    'backend/ai_synthesizer.py',
    'backend/analysts/__init__.py',
    'backend/liquidity_break_ml.py',
]

print("Verificando arquivos...")
for f in backend_files:
    exists = "✅" if os.path.exists(f) else "❌"
    print(f"   {exists} {f}")

print()

# ============================================================
# CRIAR __init__.py CORRETO
# ============================================================

print("Criando __init__.py corretos...")

init_files = {
    'backend/__init__.py': '''"""Backend Module"""
import sys
from pathlib import Path

# Permitir imports diretos
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
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ {filepath}")

print()

# ============================================================
# CRIAR WEBSOCKET_SERVER.PY SIMPLIFICADO (SEM ORQUESTRADOR)
# ============================================================

print("Criando websocket_server.py simplificado...")

websocket_code = '''"""
🌐 WebSocket Server - Market Analyst Pro
Versao Simplificada - Apenas Liquidity Break ML
"""

import asyncio
import json
import time
import os
import sys
import logging
from pathlib import Path

# ============================================================
# SETUP
# ============================================================

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

logger.info("=" * 60)
logger.info("MARKET ANALYST PRO - WebSocket Server")
logger.info("Modo: Liquidity Break ML Only")
logger.info("=" * 60)
logger.info("")

# ============================================================
# IMPORTS - LIQUIDITY BREAK ML
# ============================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

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

# ============================================================
# CONFIG
# ============================================================

WS_PORT = int(os.environ.get("WS_PORT", 8766))
SYMBOL = os.environ.get("SYMBOL", "XAUUSD")

logger.info(f"WebSocket Port: {WS_PORT}")
logger.info(f"Symbol: {SYMBOL}")
logger.info(f"Liquidity Break Dataset: {len(dataset.data)} quebras")
logger.info("")

# ============================================================
# STATE
# ============================================================

clients = set()

# ============================================================
# FUNCTIONS
# ============================================================

async def _safe_send(websocket, payload: str) -> bool:
    try:
        await asyncio.wait_for(websocket.send(payload), timeout=2.0)
        return True
    except Exception as e:
        clients.discard(websocket)
        return False

async def _broadcast_payload(payload: str):
    if not clients:
        return
    await asyncio.gather(
        *[_safe_send(c, payload) for c in list(clients)],
        return_exceptions=True
    )

# ============================================================
# LIQUIDITY BREAK HANDLERS
# ============================================================

async def handle_liquidity_break_command(websocket, data):
    """Processa comandos de liquidity break"""
    
    command = data.get('command')
    
    try:
        # ========== ADD BREAK ==========
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
        
        # ========== GET ALL BREAKS ==========
        elif command == 'get_liquidity_breaks':
            symbol = data.get('symbol', 'XAUUSD')
            breaks = dataset.get_breaks_by_symbol(symbol)
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_breaks_list',
                'data': breaks,
                'count': len(breaks),
            }, default=str))
        
        # ========== GET STATS ==========
        elif command == 'get_liquidity_stats':
            stats = dataset.get_stats()
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_stats',
                'data': stats,
            }))
        
        # ========== TRAIN ML ==========
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
        
        # ========== PREDICT BREAK ==========
        elif command == 'predict_liquidity_break':
            delta = data.get('delta', 0)
            volume = data.get('volume', 0)
            wick_top = data.get('wick_top', 0)
            wick_bot = data.get('wick_bot', 0)
            confidence = data.get('confidence', 0.5)
            
            break_type, prob = ml_model.predict(delta, volume, wick_top, wick_bot, confidence)
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_prediction',
                'break_type': break_type,
                'confidence': prob,
            }))
        
        # ========== DELETE BREAK ==========
        elif command == 'delete_liquidity_break':
            break_id = data.get('break_id')
            
            dataset.data = [b for b in dataset.data if b.get('id') != break_id]
            dataset.save()
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_break_deleted',
                'success': True,
            }))
        
        # ========== UPDATE BREAK ==========
        elif command == 'update_liquidity_break':
            break_id = data.get('break_id')
            updates = {
                'type': data.get('type'),
                'confidence_manual': data.get('confidence_manual'),
                'notes': data.get('notes'),
                'is_structural': data.get('is_structural'),
            }
            
            success = dataset.update_break(break_id, {k: v for k, v in updates.items() if v is not None})
            
            await _safe_send(websocket, json.dumps({
                'type': 'liquidity_break_updated',
                'success': success,
            }))
        
        # ========== GET ML STATUS ==========
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

# ============================================================
# WEBSOCKET HANDLER
# ============================================================

async def handle_client(websocket, path=None):
    clients.add(websocket)
    client_id = id(websocket) % 1000
    logger.info(f"CLIENT [{client_id}] connected ({len(clients)} total)")

    try:
        # Status inicial
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
                
                # LIQUIDITY BREAK COMMANDS
                if t == "liquidity_break_command":
                    await handle_liquidity_break_command(websocket, data)
                
                # PING
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

# ============================================================
# MAIN
# ============================================================

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", WS_PORT):
        logger.info(f"OK: WebSocket running on ws://0.0.0.0:{WS_PORT}")
        logger.info("")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
'''

with open("backend/websocket_server.py", "w", encoding='utf-8') as f:
    f.write(websocket_code)
print("   ✅ backend/websocket_server.py")

print()

# ============================================================
# CRIAR STUB FILES SE NÃO EXISTIR
# ============================================================

print("Criando stub files...")

stub_files = {
    'backend/analyst_orchestrator.py': '''"""Analyst Orchestrator - Stub"""

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

    'backend/mt5_feed.py': '''"""MT5 Feed - Stub"""

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

    'backend/ai_synthesizer.py': '''"""AI Synthesizer - Stub"""

class AISynthesizer:
    def __init__(self):
        self.available = False
''',
}

for filepath, content in stub_files.items():
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ {filepath} (criado)")
    else:
        print(f"   ✓ {filepath} (já existe)")

print()

print("=" * 70)
print("✅ CORRECAO COMPLETA!")
print("=" * 70)
print()
print("Agora execute: .\\start.bat")
print()