"""
Analyst Orchestrator — Market Analyst Pro
Gerencia os 6 analistas em paralelo, acumula ticks no cluster em formação
e detecta o fechamento quando |delta| >= threshold.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional

from analysts.absorption_analyst   import AbsorptionAnalyst
from analysts.delta_flow_analyst   import DeltaFlowAnalyst
from analysts.execution_style_analyst import ExecutionStyleAnalyst
from analysts.imbalance_analyst    import ImbalanceAnalyst
from analysts.sweep_analyst        import LiquiditySweepAnalyst
from analysts.volume_profile_analyst import VolumeProfileAnalyst
from analysts.cluster_closure_analyst import ClusterClosureAnalyst

logger = logging.getLogger("orchestrator")


class AnalystOrchestrator:
    """
    Recebe ticks brutos → distribui para os 6 analistas → detecta
    fechamento de cluster → retorna resultado para o WebSocket.
    """

    def __init__(self, config: Dict[str, Any], symbol: str = "XAUUSD") -> None:
        self.config  = config
        self.symbol  = symbol

        self.price_step      = float(config.get("price_step", 0.50))
        self.delta_threshold = float(config.get("delta_threshold", 100.0))
        self.weight_mode     = config.get("weight_mode", "price_weighted")

        # ── analyst config compartilhado ──────────────────────────────────
        analyst_cfg: Dict[str, Any] = {
            "price_step":   self.price_step,
            "weight_mode":  self.weight_mode,
            "ready_ticks":  20,
        }

        # ── instancia os 6 analistas ──────────────────────────────────────
        self.analysts: Dict[str, Any] = {
            "absorption":    AbsorptionAnalyst(analyst_cfg),
            "delta_flow":    DeltaFlowAnalyst(analyst_cfg),
            "execution":     ExecutionStyleAnalyst(analyst_cfg),
            "imbalance":     ImbalanceAnalyst({**analyst_cfg, "price_step": str(self.price_step)}),
            "sweep":         LiquiditySweepAnalyst(analyst_cfg),
            "volume_profile": VolumeProfileAnalyst({**analyst_cfg, "price_step": str(self.price_step)}),
        }

        # ── cluster closure (lógica de fechamento + snapshot) ─────────────
        closure_cfg = {
            **analyst_cfg,
            "delta_threshold": self.delta_threshold,
            "symbol":          symbol,
        }
        self.cluster_analyst = ClusterClosureAnalyst(closure_cfg)

        # ── estado do cluster em formação ─────────────────────────────────
        self._reset_forming()
        self._tick_seq: int = 0

        logger.info(
            f"Orchestrator ready | symbol={symbol} | step={self.price_step} | "
            f"threshold={self.delta_threshold} | mode={self.weight_mode}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # helpers internos
    # ─────────────────────────────────────────────────────────────────────────
    def _reset_forming(self) -> None:
        self._forming: Dict[str, Any] = {
            "vol_buy":   0.0,
            "vol_sell":  0.0,
            "delta":     0.0,
            "price_open": None,
            "price_high": None,
            "price_low":  None,
            "price_close": None,
            "ts_open":    None,
            "ts_close":   None,
            "ticks":      0,
        }

    def _quantize(self, price: float) -> float:
        if self.price_step <= 0:
            return price
        return round(round(price / self.price_step) * self.price_step, 10)

    def _calc_weight(self, price: float, spread: float = 0.0) -> float:
        if self.weight_mode == "price_weighted":
            return max(price, 1.0)
        if self.weight_mode == "spread_weighted":
            return max(spread, 0.1)
        return 1.0  # equal

    # ─────────────────────────────────────────────────────────────────────────
    # feed_tick — retorna dict com cluster_closed=True quando fecha
    # ─────────────────────────────────────────────────────────────────────────
    def feed_tick(self, raw_tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._tick_seq += 1
        raw_tick["_tick_seq"] = self._tick_seq

        price  = float(raw_tick.get("price", 0.0))
        side   = str(raw_tick.get("side", "neutral")).lower()
        spread = float(raw_tick.get("spread", 0.0))
        ts     = float(raw_tick.get("timestamp", time.time()))

        if price <= 0:
            return None

        # volume já normalizado pelo mt5_feed — usa direto
        # O weight_mode é aplicado apenas para diferenciar importância relativa
        # entre símbolos no ML, não na escala do delta
        raw_vol = float(raw_tick.get("volume_synthetic", raw_tick.get("volume", 1.0)))
        vol     = max(raw_vol, 0.001)

        # distribui para os 6 analistas
        for analyst in self.analysts.values():
            try:
                analyst.feed_tick({**raw_tick, "volume_synthetic": vol})
            except Exception as exc:
                logger.debug(f"Analyst feed error ({analyst.name}): {exc}")

        # atualiza cluster em formação
        f = self._forming
        if f["price_open"] is None:
            f["price_open"] = price
            f["ts_open"]    = ts
            f["price_high"] = price
            f["price_low"]  = price

        f["price_close"] = price
        f["ts_close"]    = ts
        f["price_high"]  = max(f["price_high"], price)
        f["price_low"]   = min(f["price_low"],  price)
        f["ticks"]      += 1

        if side == "buy":
            f["vol_buy"] += vol
        elif side == "sell":
            f["vol_sell"] += vol

        f["delta"] = f["vol_buy"] - f["vol_sell"]

        # ── verifica fechamento ────────────────────────────────────────────
        if abs(f["delta"]) >= self.delta_threshold:
            return self._close_cluster(ts)

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # _close_cluster
    # ─────────────────────────────────────────────────────────────────────────
    def _close_cluster(self, close_ts: float) -> Dict[str, Any]:
        f = self._forming
        close_price = f["price_close"]

        # coleta sinais dos analistas para o snapshot
        analyst_signals = self._collect_signals(
            close_price,
            f["ts_open"] or close_ts,
            close_ts,
        )

        # delega ao ClusterClosureAnalyst para gerar snapshot + pattern
        cluster_snapshot = self.cluster_analyst.on_cluster_close(
            close_price=close_price,
            close_ts=close_ts,
            analyst_signals=analyst_signals,
            forming=dict(f),
            symbol=self.symbol,
        )

        # reseta cluster
        self._reset_forming()

        return {
            "cluster_closed": True,
            "cluster_data": {
                **cluster_snapshot,
                "symbol": self.symbol,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # analyze_region — chamado pelo front no botão 🔍 Achar
    # ─────────────────────────────────────────────────────────────────────────
    def analyze_region(
        self, price: float, time_start: float, time_end: float
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for name, analyst in self.analysts.items():
            try:
                r = analyst.analyze_region(price, time_start, time_end)
                results[name] = {
                    "classification": r.classification,
                    "confidence":     round(r.confidence, 3),
                    "description":    r.description,
                    "details":        r.details,
                    "analyst":        r.analyst_name,
                    "timestamp":      r.timestamp,
                    "price":          r.price,
                }
            except Exception as exc:
                logger.debug(f"analyze_region error ({name}): {exc}")
                results[name] = {"classification": "ERRO", "confidence": 0.0, "description": str(exc)}
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # _collect_signals — sinais em tempo real de cada analista
    # ─────────────────────────────────────────────────────────────────────────
    def _collect_signals(
        self, price: float, time_start: float, time_end: float
    ) -> Dict[str, Any]:
        signals: Dict[str, Any] = {}
        for name, analyst in self.analysts.items():
            try:
                r = analyst.analyze_region(price, time_start, time_end)
                signals[name] = {
                    "signal":     r.classification,
                    "confidence": round(r.confidence, 3),
                    "details":    r.details,
                }
            except Exception:
                signals[name] = {"signal": "ERRO", "confidence": 0.0, "details": {}}
        return signals

    # ─────────────────────────────────────────────────────────────────────────
    # get_realtime_status — enviado ao front a cada N ticks
    # ─────────────────────────────────────────────────────────────────────────
    def get_realtime_status(self) -> Dict[str, Any]:
        f = self._forming
        analysts_status: Dict[str, Any] = {}
        for name, analyst in self.analysts.items():
            try:
                analysts_status[name] = analyst.get_realtime_status()
            except Exception:
                analysts_status[name] = {"status": "error"}

        return {
            "symbol":          self.symbol,
            "tick_seq":        self._tick_seq,
            "delta_threshold": self.delta_threshold,
            "price_step":      self.price_step,
            "weight_mode":     self.weight_mode,
            "forming": {
                "delta":       round(f["delta"], 4),
                "vol_buy":     round(f["vol_buy"], 4),
                "vol_sell":    round(f["vol_sell"], 4),
                "ticks":       f["ticks"],
                "price_open":  f["price_open"],
                "price_close": f["price_close"],
                "price_high":  f["price_high"],
                "price_low":   f["price_low"],
                "pct_complete": round(
                    min(1.0, abs(f["delta"]) / max(self.delta_threshold, 1.0)), 3
                ),
            },
            "analysts":        analysts_status,
            "clusters_closed": self.cluster_analyst.cluster_count
            if hasattr(self.cluster_analyst, "cluster_count") else 0,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # reset
    # ─────────────────────────────────────────────────────────────────────────
    def reset(self) -> None:
        self._reset_forming()
        self._tick_seq = 0
        for analyst in self.analysts.values():
            try:
                analyst.reset()
            except Exception:
                pass
        self.cluster_analyst.reset()
        logger.info("Orchestrator reset")
