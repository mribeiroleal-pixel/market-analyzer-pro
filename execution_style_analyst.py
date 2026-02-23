from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

from .base import BaseAnalyst, AnalysisResult


class ExecutionClass(str, Enum):
    AGGRESSIVE_BUY = "EXECUCAO_AGRESSIVA_COMPRA"
    AGGRESSIVE_SELL = "EXECUCAO_AGRESSIVA_VENDA"
    PASSIVE = "EXECUCAO_PASSIVA"
    NEUTRAL = "NEUTRO"


class ExecutionStyleAnalyst(BaseAnalyst):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "ExecutionStyle"
        self.window_ticks = int(self.config.get("window_ticks", 400))
        self.passive_efficiency_th = float(self.config.get("passive_efficiency_th", 0.0005))
        self._ticks_exec: Deque[Dict[str, Any]] = deque(maxlen=self.window_ticks)
        self._last_side: Optional[str] = None
        self._streak = 0
        self._reversal_count = 0

    def _on_tick(self, tick: Dict[str, Any]) -> None:
        side = tick.get("side") if tick.get("side") in ("buy", "sell") else None
        if side and side == self._last_side:
            self._streak += 1
        else:
            if self._last_side and side and side != self._last_side:
                self._reversal_count += 1
            self._streak = 1 if side else 0
            self._last_side = side
        self._ticks_exec.append({"price": float(tick.get("price", 0.0)), "side": side, "vol": float(tick.get("_volume", self._extract_volume(tick))), "ts": float(tick.get("timestamp", 0.0))})
        self.is_ready = len(self._ticks_exec) >= max(40, int(self.window_ticks * 0.25))

    def _calc_dominance(self, vols: List[float], sides: List[Optional[str]]) -> Tuple[str, float, float, float]:
        buy_vol = sum(v for v, s in zip(vols, sides) if s == "buy")
        sell_vol = sum(v for v, s in zip(vols, sides) if s == "sell")
        total = buy_vol + sell_vol or 1.0
        dom = "buy" if buy_vol > sell_vol else "sell" if sell_vol > buy_vol else "neutral"
        return dom, max(buy_vol, sell_vol) / total, buy_vol, sell_vol

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        ticks = self.get_ticks_in_range(time_start, time_end)
        e = self._normalize_timestamp(time_end)
        if len(ticks) < 10:
            return AnalysisResult(self.name, e, price, ExecutionClass.NEUTRAL.value, 0.3, {"tick_count": len(ticks)}, "Poucos ticks.")
        prices = [float(t.get("price", 0.0)) for t in ticks]
        vols = [float(t.get("_volume", self._extract_volume(t))) for t in ticks]
        sides = [t.get("side") if t.get("side") in ("buy", "sell") else None for t in ticks]
        p0, p1 = prices[0], prices[-1]
        prange = max(prices) - min(prices)
        total_vol = sum(vols) or 1.0
        efficiency = prange / total_vol
        dom, dom_ratio, buyv, sellv = self._calc_dominance(vols, sides)
        aggression_score = max(0.0, min(1.0, 0.6 * dom_ratio + 0.4 * (1.0 if abs(p1-p0) > 0 else 0.0)))
        if dom == "buy" and aggression_score >= 0.7 and p1 >= p0:
            cls = ExecutionClass.AGGRESSIVE_BUY.value
        elif dom == "sell" and aggression_score >= 0.7 and p1 <= p0:
            cls = ExecutionClass.AGGRESSIVE_SELL.value
        elif efficiency < self.passive_efficiency_th and dom_ratio < 0.7:
            cls = ExecutionClass.PASSIVE.value
        else:
            cls = ExecutionClass.NEUTRAL.value
        conf = max(0.3, min(0.9, 0.45 + 0.40 * min(1.0, len(ticks)/200.0) * dom_ratio))
        details = {"aggression_score": round(aggression_score, 3), "efficiency": round(efficiency, 8), "dominant_side": dom, "dominant_ratio": round(dom_ratio, 3), "tick_count": len(ticks), "buy_vol": round(buyv,2), "sell_vol": round(sellv,2), "price_range": round(prange, 8)}
        desc = f"Dom={dom} ({dom_ratio:.0%}) | eff={efficiency:.6f} | Δp={p1-p0:+.2f} | ticks={len(ticks)}"
        return AnalysisResult(self.name, e, price, cls, round(conf, 3), details, desc)

    def get_realtime_status(self) -> Dict[str, Any]:
        if not self.is_ready:
            return {"status": "warmup", "ticks": len(self._ticks_exec)}
        ticks = list(self._ticks_exec)
        prices = [t["price"] for t in ticks]
        vols = [t["vol"] for t in ticks]
        dom, dom_ratio, _, _ = self._calc_dominance(vols, [t["side"] for t in ticks])
        efficiency = ((max(prices) - min(prices)) / (sum(vols) or 1.0)) if prices else 0.0
        trend = dom if dom_ratio >= 0.65 else "neutral"
        return {"status": "active", "trend": trend, "dominant_ratio": round(dom_ratio, 3), "efficiency": round(efficiency, 8), "streak": self._streak, "reversals": self._reversal_count, "ticks": len(ticks)}

    def reset(self) -> None:
        super().reset(); self._ticks_exec.clear(); self._last_side = None; self._streak = 0; self._reversal_count = 0
