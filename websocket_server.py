"""
WebSocket Server — Market Analyst Pro
Integra: 6 Analistas + MT5 Feed + DB + Redis Cache + ML Inference + AI Synthesizer
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional, Set

# ── paths ────────────────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, project_root)

# ── env ──────────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

# ── logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="[%(asctime)s] [%(levelname)-8s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("logs", "backend.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("ws_server")

# ── deps ─────────────────────────────────────────────────────────────────────
try:
    import websockets
except ImportError:
    logger.error("pip install websockets")
    sys.exit(1)

# ── internal modules ─────────────────────────────────────────────────────────
from analyst_orchestrator import AnalystOrchestrator
from mt5_feed import MT5Feed, SYM_CFG
from ai_synthesizer import AISynthesizer
from database.repository import Database
from cache.redis_client import RedisCache
from ml.pipelines.inference import MLInferencePipeline

# ── config ───────────────────────────────────────────────────────────────────
WS_PORT      = int(os.environ.get("WS_PORT", 8766))
WS_HOST      = os.environ.get("WS_HOST", "0.0.0.0")
SYMBOL       = os.environ.get("SYMBOL", "XAUUSD")
WEIGHT_MODE  = os.environ.get("WEIGHT_MODE", "price_weighted")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///market_analyst.db")
REDIS_URL    = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
ENABLE_DB    = os.environ.get("ENABLE_DB", "True").lower() == "true"
ENABLE_ML    = os.environ.get("ENABLE_ML", "False").lower() == "true"
ENABLE_CACHE = os.environ.get("ENABLE_CACHE", "False").lower() == "true"

logger.info("=" * 60)
logger.info("MARKET ANALYST PRO — WebSocket Server")
logger.info(f"Symbol: {SYMBOL} | Port: {WS_PORT} | DB: {ENABLE_DB} | ML: {ENABLE_ML} | Cache: {ENABLE_CACHE}")
logger.info("=" * 60)

# ── services (lazy init) ─────────────────────────────────────────────────────
db: Optional[Database] = None
cache: Optional[RedisCache] = None
ml_pipeline: Optional[MLInferencePipeline] = None
ai_synth: AISynthesizer = AISynthesizer()

if ENABLE_DB:
    try:
        db = Database(DATABASE_URL)
        logger.info("OK: Database connected")
    except Exception as exc:
        logger.warning(f"DB disabled — {exc}")
        db = None

if ENABLE_CACHE:
    try:
        cache = RedisCache(REDIS_URL)
        logger.info("OK: Redis connected")
    except Exception as exc:
        logger.warning(f"Cache disabled — {exc}")
        cache = None

if ENABLE_ML:
    try:
        ml_pipeline = MLInferencePipeline()
        ml_pipeline.load()
        logger.info(f"OK: ML pipeline loaded — {ml_pipeline.get_status()}")
    except Exception as exc:
        logger.warning(f"ML disabled — {exc}")
        ml_pipeline = None

# ── global state ──────────────────────────────────────────────────────────────
clients: Set = set()
current_symbol: str = SYMBOL
orchestrator: Optional[AnalystOrchestrator] = None
mt5: Optional[MT5Feed] = None
tick_history: list = []          # histórico leve para loadHistory
MAX_HISTORY = 50_000


def _build_orchestrator(symbol: str) -> AnalystOrchestrator:
    cfg = SYM_CFG.get(symbol, SYM_CFG["XAUUSD"])
    config = {
        "symbol": symbol,
        "price_step": cfg["step"],
        "delta_threshold": cfg["delta_th"],
        "weight_mode": WEIGHT_MODE,
    }
    return AnalystOrchestrator(config, symbol)


def _build_mt5(symbol: str) -> MT5Feed:
    return MT5Feed(symbol=symbol, weight_mode=WEIGHT_MODE)


# ── helpers ───────────────────────────────────────────────────────────────────
async def _safe_send(ws, payload: str) -> bool:
    try:
        await asyncio.wait_for(ws.send(payload), timeout=2.0)
        return True
    except Exception:
        clients.discard(ws)
        return False


async def _broadcast(payload: str) -> None:
    if not clients:
        return
    dead = set()
    results = await asyncio.gather(
        *[asyncio.wait_for(ws.send(payload), timeout=2.0) for ws in clients],
        return_exceptions=True,
    )
    for ws, result in zip(list(clients), results):
        if isinstance(result, Exception):
            dead.add(ws)
    clients.difference_update(dead)


def _serialize(obj: Any) -> Any:
    """JSON-safe serializer for floats/ints."""
    if isinstance(obj, float):
        if obj != obj:   # NaN
            return None
        if obj == float("inf") or obj == float("-inf"):
            return None
        return obj
    return str(obj)


# ── cluster closed callback ───────────────────────────────────────────────────
async def _on_cluster_closed(cluster_data: Dict[str, Any]) -> None:
    """Chamado pelo orchestrator quando um cluster fecha."""

    # 1. ML Inference
    ml_result: Dict[str, Any] = {}
    if ml_pipeline and ml_pipeline.is_ready():
        try:
            ml_result = ml_pipeline.predict(cluster_data)
        except Exception as exc:
            logger.debug(f"ML predict error: {exc}")

    # 2. Persistência
    if db:
        try:
            record = {**cluster_data, "ml_prediction": ml_result or None}
            db.save_cluster(record)
        except Exception as exc:
            logger.debug(f"DB save error: {exc}")

    # 3. Cache
    if cache:
        try:
            key = f"cluster:{current_symbol}:last"
            cache.set(key, cluster_data, ttl_seconds=3600)
        except Exception as exc:
            logger.debug(f"Cache set error: {exc}")

    # 4. Broadcast
    payload = json.dumps(
        {"type": "cluster_closed", "data": {**cluster_data, "ml": ml_result}},
        default=_serialize,
    )
    await _broadcast(payload)


# ── MT5 feed loop ─────────────────────────────────────────────────────────────
async def _feed_loop() -> None:
    global orchestrator, mt5, tick_history, current_symbol

    orchestrator = _build_orchestrator(current_symbol)
    mt5 = _build_mt5(current_symbol)

    connected = mt5.initialize()
    source = "MT5_LIVE" if connected else "MT5_SIMULATED"
    logger.info(f"Feed source: {source}")

    # notifica clientes do status inicial (broadcast para quem já está conectado)
    cfg = SYM_CFG.get(current_symbol, SYM_CFG["XAUUSD"])
    connect_msg = json.dumps({
        "type": "connected",
        "data": {
            "source":        source,
            "mt5_connected": connected,
            "symbol":        current_symbol,
            "price_step":    cfg["step"],
            "delta_th":      cfg["delta_th"],
            "weight_mode":   WEIGHT_MODE,
            "db_enabled":    ENABLE_DB,
            "ml_enabled":    ENABLE_ML,
            "cache_enabled": ENABLE_CACHE,
        },
    })
    await _broadcast(connect_msg)   # ← FIX: envia para todos os clientes conectados

    async for raw_tick in mt5.stream():
        if not raw_tick:
            continue

        # acumula histórico leve
        tick_history.append(raw_tick)
        if len(tick_history) > MAX_HISTORY:
            tick_history = tick_history[-MAX_HISTORY:]

        # feed ao orchestrator
        result = orchestrator.feed_tick(raw_tick)

        # se gerou cluster fechado
        if result and result.get("cluster_closed"):
            await _on_cluster_closed(result["cluster_data"])

        # broadcast do tick ao front
        tick_payload = json.dumps(
            {"type": "tick", "data": raw_tick},
            default=_serialize,
        )
        await _broadcast(tick_payload)

        # engine status periódico (a cada 50 ticks; _tick_seq começa em 1)
        seq = raw_tick.get("_tick_seq", 0)
        if seq <= 1 or seq % 50 == 0:
            status = orchestrator.get_realtime_status()
            status["mt5_connected"] = bool(mt5 and mt5.connected)
            status["source"]        = "MT5_LIVE" if (mt5 and mt5.connected) else "MT5_SIMULATED"
            await _broadcast(
                json.dumps({"type": "engine_status", "data": status}, default=_serialize)
            )


# ── client message handlers ───────────────────────────────────────────────────
async def _handle_switch_symbol(ws, data: Dict[str, Any]) -> None:
    global current_symbol, orchestrator, mt5, tick_history

    new_sym = data.get("symbol", "XAUUSD").upper()
    if new_sym not in SYM_CFG:
        await _safe_send(ws, json.dumps({"type": "error", "message": f"Símbolo desconhecido: {new_sym}"}))
        return

    current_symbol = new_sym
    tick_history = []
    orchestrator = _build_orchestrator(current_symbol)
    mt5 = _build_mt5(current_symbol)
    mt5.initialize()

    cfg = SYM_CFG[current_symbol]
    await _broadcast(
        json.dumps({
            "type": "symbol_changed",
            "config": {
                "symbol": current_symbol,
                "price_step": cfg["step"],
                "delta_th": cfg["delta_th"],
            },
        })
    )
    logger.info(f"Symbol switched → {current_symbol}")


async def _handle_get_history(ws, data: Dict[str, Any]) -> None:
    symbol = data.get("symbol", current_symbol)
    hours  = float(data.get("hours", 1))
    cutoff = time.time() - hours * 3600

    # 1) tenta cache de ticks
    if cache:
        cached = cache.get(f"history:{symbol}:{hours}")
        if cached:
            await _safe_send(ws, json.dumps({
                "type": "history",
                "ticks": cached,
                "symbol": symbol,
                "count": len(cached),
                "hours": hours,
                "source": "cache",
            }, default=_serialize))
            return

    # 2) filtra tick_history em memória (ticks acumulados desde início)
    ticks = [
        t for t in tick_history
        if float(t.get("timestamp", 0)) >= cutoff
        and t.get("symbol", symbol) == symbol
    ]

    # 3) tenta ticks do DB se poucos em memória
    if len(ticks) < 100 and db:
        try:
            db_ticks = db.get_ticks(symbol, hours=hours)
            if db_ticks:
                ticks = db_ticks
        except Exception:
            pass

    # 4) se ainda tem ticks, envia como history
    if ticks:
        if cache:
            cache.set(f"history:{symbol}:{hours}", ticks, ttl_seconds=60)
        await _safe_send(ws, json.dumps({
            "type": "history",
            "ticks": ticks,
            "symbol": symbol,
            "count": len(ticks),
            "hours": hours,
            "source": "memory" if not db else "db",
        }, default=_serialize))
        return

    # 5) sem ticks: envia clusters do DB diretamente (para o front desenhar sem reprocessar)
    db_clusters = []
    if db:
        try:
            db_clusters = db.get_clusters(symbol, limit=500)
        except Exception:
            pass

    await _safe_send(ws, json.dumps({
        "type":    "history",
        "ticks":   [],
        "clusters": db_clusters,   # front pode usar se ticks vazio
        "symbol":  symbol,
        "count":   0,
        "hours":   hours,
        "source":  "clusters_db",
    }, default=_serialize))


async def _handle_analyze_region(ws, data: Dict[str, Any]) -> None:
    if not orchestrator:
        await _safe_send(ws, json.dumps({"type": "error", "message": "Orchestrator não inicializado"}))
        return

    price      = float(data.get("price", 0))
    time_start = float(data.get("time_start", time.time() - 60))
    time_end   = float(data.get("time_end",   time.time()))

    results = orchestrator.analyze_region(price, time_start, time_end)

    # AI synthesis
    ai_signal: Dict[str, Any] = {}
    if ai_synth.available:
        try:
            ai_signal = await ai_synth.synthesize(results, price, current_symbol)
        except Exception as exc:
            logger.debug(f"AI synth error: {exc}")

    await _safe_send(ws, json.dumps({
        "type": "analysis",
        "data": {
            "analysts": results,
            "ai_signal": ai_signal,
            "price": price,
            "time_start": time_start,
            "time_end": time_end,
        },
    }, default=_serialize))


async def _handle_train_ml(ws, data: Dict[str, Any]) -> None:
    if not db:
        await _safe_send(ws, json.dumps({"type": "error", "message": "Database não habilitado (ENABLE_DB=True)"}))
        return

    symbol = data.get("symbol", current_symbol)
    try:
        from ml.training.train_outcome import train_and_save
        success = train_and_save(DATABASE_URL, symbol)
        # recarrega pipeline
        if success and ml_pipeline:
            ml_pipeline.load()
        await _safe_send(ws, json.dumps({
            "type": "ml_trained",
            "success": success,
            "symbol": symbol,
        }))
    except Exception as exc:
        logger.error(f"Train ML error: {exc}")
        await _safe_send(ws, json.dumps({"type": "error", "message": str(exc)}))


async def _handle_get_ml_status(ws) -> None:
    status = ml_pipeline.get_status() if ml_pipeline else {"pipeline_active": False}
    await _safe_send(ws, json.dumps({"type": "ml_status", "data": status}))


async def _handle_get_clusters(ws, data: Dict[str, Any]) -> None:
    if not db:
        await _safe_send(ws, json.dumps({"type": "clusters_list", "data": [], "count": 0}))
        return
    symbol = data.get("symbol", current_symbol)
    limit  = int(data.get("limit", 200))
    rows   = db.get_clusters(symbol, limit=limit)
    await _safe_send(ws, json.dumps({
        "type": "clusters_list",
        "data": rows,
        "count": len(rows),
    }, default=_serialize))


# ── client handler ────────────────────────────────────────────────────────────
async def handle_client(ws, path=None) -> None:
    clients.add(ws)
    cid = id(ws) % 10000
    logger.info(f"CLIENT [{cid:04d}] connected  (total={len(clients)})")

    cfg = SYM_CFG.get(current_symbol, SYM_CFG["XAUUSD"])
    _mt5_live = bool(mt5 and mt5.connected)
    await _safe_send(ws, json.dumps({
        "type": "connected",
        "data": {
            "symbol":        current_symbol,
            "price_step":    cfg["step"],
            "delta_th":      cfg["delta_th"],
            "weight_mode":   WEIGHT_MODE,
            "db_enabled":    ENABLE_DB,
            "ml_enabled":    ENABLE_ML,
            "cache_enabled": ENABLE_CACHE,
            "source":        "MT5_LIVE" if _mt5_live else "MT5_SIMULATED",
            "mt5_connected": _mt5_live,
        },
    }))

    try:
        async for message in ws:
            try:
                data = json.loads(message)
                t = data.get("type", "")

                if t == "switch_symbol":
                    await _handle_switch_symbol(ws, data)

                elif t == "get_history" or data.get("action") == "get_history":
                    await _handle_get_history(ws, data)

                elif t == "analyze_region":
                    await _handle_analyze_region(ws, data)

                elif t == "train_ml":
                    await _handle_train_ml(ws, data)

                elif t == "get_ml_status":
                    await _handle_get_ml_status(ws)

                elif t == "get_clusters":
                    await _handle_get_clusters(ws, data)

                elif t == "get_engine_status":
                    if orchestrator:
                        status = orchestrator.get_realtime_status()
                        await _safe_send(ws, json.dumps({"type": "engine_status", "data": status}, default=_serialize))

                elif t == "reset":
                    if orchestrator:
                        orchestrator.reset()
                    await _safe_send(ws, json.dumps({"type": "reset_ok"}))

                elif t == "ping":
                    await _safe_send(ws, json.dumps({"type": "pong", "ts": time.time()}))

            except json.JSONDecodeError:
                pass
            except Exception as exc:
                logger.debug(f"Handler error [{cid:04d}]: {str(exc)[:80]}")

    except Exception as exc:
        logger.debug(f"Client error [{cid:04d}]: {str(exc)[:80]}")
    finally:
        clients.discard(ws)
        logger.info(f"CLIENT [{cid:04d}] disconnected (total={len(clients)})")


# ── main ──────────────────────────────────────────────────────────────────────
async def main() -> None:
    feed_task = asyncio.create_task(_feed_loop())

    async with websockets.serve(handle_client, WS_HOST, WS_PORT):
        logger.info(f"WebSocket running → ws://{WS_HOST}:{WS_PORT}")
        logger.info("Aguardando conexões do frontend...")
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            feed_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
