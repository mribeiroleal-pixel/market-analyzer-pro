"""
MT5 Feed — Market Analyst Pro
Conecta ao MetaTrader 5 via API oficial e emite ticks normalizados.
Fallback para modo simulado (geração realista de ticks) quando MT5 não disponível.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import time
from typing import Any, AsyncGenerator, Dict, Optional

logger = logging.getLogger("mt5_feed")

# ── configuração por símbolo ──────────────────────────────────────────────────
SYM_CFG: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {"step": 0.50,   "delta_th": 100,  "digits": 2,  "base_price": 2320.0,  "volatility": 0.15,  "label": "XAU/USD"},
    "BTCUSD": {"step": 10.0,   "delta_th": 200,  "digits": 2,  "base_price": 67000.0, "volatility": 0.80,  "label": "BTC/USD"},
    "EURUSD": {"step": 0.0001, "delta_th": 50,   "digits": 5,  "base_price": 1.0850,  "volatility": 0.0003,"label": "EUR/USD"},
    "GBPUSD": {"step": 0.0001, "delta_th": 60,   "digits": 5,  "base_price": 1.2700,  "volatility": 0.0004,"label": "GBP/USD"},
    "USTEC":  {"step": 1.0,    "delta_th": 150,  "digits": 2,  "base_price": 17500.0, "volatility": 5.0,   "label": "USTEC"},
}

# ── weight modes ──────────────────────────────────────────────────────────────
WEIGHT_MODES = ("price_weighted", "spread_weighted", "equal")


class MT5Feed:
    """
    Abstrai o feed de ticks do MetaTrader 5.
    - Se MT5 disponível e credenciais configuradas → modo LIVE
    - Caso contrário → modo SIMULATED (realista para testes)
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        weight_mode: str = "price_weighted",
    ) -> None:
        self.symbol      = symbol.upper()
        self.weight_mode = weight_mode if weight_mode in WEIGHT_MODES else "price_weighted"
        self.connected   = False
        self._mt5        = None
        self._tick_seq   = 0
        self._last_price: Optional[float] = None

        # config do símbolo
        self._cfg = SYM_CFG.get(self.symbol, SYM_CFG["XAUUSD"])

    # ─────────────────────────────────────────────────────────────────────────
    # initialize
    # ─────────────────────────────────────────────────────────────────────────
    def initialize(self) -> bool:
        """Tenta conectar ao MT5. Retorna True se bem-sucedido."""
        account  = os.environ.get("MT5_ACCOUNT", "")
        password = os.environ.get("MT5_PASSWORD", "")
        server   = os.environ.get("MT5_SERVER", "")

        if not account or not password:
            logger.info("MT5 credentials not set → SIMULATED mode")
            return False

        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5

            if not mt5.initialize():
                logger.warning(f"MT5 initialize() failed: {mt5.last_error()}")
                return False

            if not mt5.login(int(account), password=password, server=server):
                logger.warning(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False

            info = mt5.account_info()
            logger.info(
                f"MT5 LIVE connected | account={info.login} | "
                f"server={info.server} | balance={info.balance}"
            )
            self.connected = True
            return True

        except ImportError:
            logger.info("MetaTrader5 package not installed → SIMULATED mode")
            return False
        except Exception as exc:
            logger.warning(f"MT5 connect error: {exc} → SIMULATED mode")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # stream — gerador assíncrono principal
    # ─────────────────────────────────────────────────────────────────────────
    async def stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Emite ticks normalizados continuamente."""
        if self.connected and self._mt5:
            async for tick in self._stream_live():
                yield tick
        else:
            async for tick in self._stream_simulated():
                yield tick

    # ─────────────────────────────────────────────────────────────────────────
    # _stream_live — ticks reais do MT5
    # ─────────────────────────────────────────────────────────────────────────
    async def _stream_live(self) -> AsyncGenerator[Dict[str, Any], None]:
        mt5 = self._mt5
        last_ts: float = 0.0

        while True:
            try:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    await asyncio.sleep(0.01)
                    continue

                ts = float(tick.time_msc) / 1000.0
                if ts <= last_ts:
                    await asyncio.sleep(0.005)
                    continue
                last_ts = ts

                # determina lado pelo ask/bid
                bid = float(tick.bid)
                ask = float(tick.ask)
                mid = (bid + ask) / 2.0
                spread = ask - bid

                # volume real se disponível
                vol_real = float(getattr(tick, "volume_real", 0.0) or 0.0)
                vol_syn  = self._calc_volume_synthetic(mid, spread)
                volume   = vol_real if vol_real > 0 else vol_syn

                # lado com base na última mudança de preço
                side = "buy" if mid >= (self._last_price or mid) else "sell"
                self._last_price = mid

                self._tick_seq += 1
                yield self._normalize_tick(
                    price=mid,
                    side=side,
                    volume=volume,
                    spread=spread,
                    ts=ts,
                    bid=bid,
                    ask=ask,
                )

            except Exception as exc:
                logger.warning(f"MT5 live tick error: {exc}")
                await asyncio.sleep(0.1)

    # ─────────────────────────────────────────────────────────────────────────
    # _stream_simulated — geração realista de ticks
    # ─────────────────────────────────────────────────────────────────────────
    async def _stream_simulated(self) -> AsyncGenerator[Dict[str, Any], None]:
        cfg       = self._cfg
        price     = cfg["base_price"]
        vol_step  = cfg["step"]
        vol_level = cfg["volatility"]
        digits    = cfg["digits"]

        # micro-estrutura simulada
        trend         = 0.0        # drift suave
        trend_strength = 0.0
        trend_ticks   = 0
        MAX_TREND     = random.randint(80, 250)

        while True:
            # ── velocidade variável (burst / calmo) ─────────────────────
            hour = time.localtime().tm_hour
            market_active = 8 <= hour <= 22
            base_interval = 0.008 if market_active else 0.035
            burst = random.random() < 0.04
            interval = random.expovariate(1 / (0.003 if burst else base_interval))
            interval = max(0.001, min(interval, 0.5))

            # ── micro-trend ──────────────────────────────────────────────
            trend_ticks += 1
            if trend_ticks >= MAX_TREND:
                trend = random.uniform(-1, 1)
                trend_strength = random.uniform(0.3, 0.9)
                trend_ticks = 0
                MAX_TREND = random.randint(80, 250)

            # ── movimento de preço ───────────────────────────────────────
            noise      = random.gauss(0, vol_level)
            drift      = trend * trend_strength * vol_level * 0.5
            raw_change = noise + drift

            # quantiza ao step
            steps  = round(raw_change / vol_step)
            change = steps * vol_step
            price  = max(price + change, vol_step)
            price  = round(price, digits)

            # ── volume sintético ─────────────────────────────────────────
            vol = self._calc_volume_synthetic(price, vol_step * 0.5)

            # ── lado (buy/sell) ──────────────────────────────────────────
            if trend > 0.3:
                side_weights = [0.65, 0.35]   # mais buy
            elif trend < -0.3:
                side_weights = [0.35, 0.65]   # mais sell
            else:
                side_weights = [0.52, 0.48]
            side = random.choices(["buy", "sell"], weights=side_weights)[0]

            ts = time.time()
            self._tick_seq += 1

            yield self._normalize_tick(
                price=price,
                side=side,
                volume=vol,
                spread=vol_step * 0.5,
                ts=ts,
            )

            await asyncio.sleep(interval)

    # ─────────────────────────────────────────────────────────────────────────
    # helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _calc_volume_synthetic(self, price: float, spread: float) -> float:
        """
        Retorna volume bruto normalizado (sempre ~1.0 base).
        O orchestrator aplica a ponderação por weight_mode internamente.
        Assim o frontend recebe volumes em escala humana (não dividido por preço).
        """
        base = random.lognormvariate(0, 0.6)   # log-normal centrado em ~1.0
        return max(0.01, base)

    def _normalize_tick(
        self,
        price: float,
        side: str,
        volume: float,
        spread: float = 0.0,
        ts: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Retorna tick no formato padrão esperado pelo front e pelo orchestrator."""
        now = ts or time.time()
        return {
            # identificação
            "symbol":           self.symbol,
            "source":           "MT5_LIVE" if self.connected else "MT5_SIMULATED",
            # preço
            "price":            price,
            "bid":              bid if bid is not None else price,
            "ask":              ask if ask is not None else price,
            "spread":           spread,
            # volume
            "volume_synthetic": round(volume, 6),
            "volume_real":      0.0,
            # fluxo
            "side":             side,
            # tempo
            "timestamp":        now,
            "timestamp_ms":     int(now * 1000),
            # meta
            "_tick_seq":        self._tick_seq,
            "weight_mode":      self.weight_mode,
        }

    def shutdown(self) -> None:
        if self._mt5 and self.connected:
            try:
                self._mt5.shutdown()
                logger.info("MT5 shutdown OK")
            except Exception:
                pass
        self.connected = False
