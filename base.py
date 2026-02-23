from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional
import time


@dataclass
class AnalysisResult:
    analyst_name: str
    timestamp: float
    price: float
    classification: str
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


class BaseAnalyst:
    """Classe base simples e compatível para analistas de fluxo."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = config or {}
        self.name: str = self.__class__.__name__
        self.is_ready: bool = False
        self._tick_buffer_maxlen: int = int(self.config.get("tick_buffer_maxlen", 20000))
        self._ticks: Deque[Dict[str, Any]] = deque(maxlen=max(100, self._tick_buffer_maxlen))

    def _normalize_timestamp(self, ts: Any) -> float:
        try:
            v = float(ts)
        except (TypeError, ValueError):
            return time.time()
        if v > 1e12:  # ms
            return v / 1000.0
        return v

    def _normalize_side(self, side: Any) -> str:
        s = str(side or "").strip().lower()
        if s in ("b", "buy", "buyer"):
            return "buy"
        if s in ("s", "sell", "seller"):
            return "sell"
        return "neutral"

    def _extract_volume(self, tick: Dict[str, Any], default: float = 1.0) -> float:
        for key in ("volume_synthetic", "volume_real", "volume"):
            if key in tick and tick[key] is not None:
                try:
                    v = float(tick[key])
                    if v >= 0:
                        return v
                except (TypeError, ValueError):
                    pass
        return float(default)

    def feed_tick(self, tick: Dict[str, Any]) -> None:
        """Normaliza e entrega o tick para o analista."""
        t = dict(tick)
        t["timestamp"] = self._normalize_timestamp(t.get("timestamp", time.time()))
        t["side"] = self._normalize_side(t.get("side"))
        try:
            t["price"] = float(t.get("price", 0.0))
        except (TypeError, ValueError):
            t["price"] = 0.0
        t["_volume"] = self._extract_volume(t)
        self._ticks.append(t)
        self._on_tick(t)

    def get_ticks_in_range(self, start_ts: float, end_ts: float) -> List[Dict[str, Any]]:
        s = self._normalize_timestamp(start_ts)
        e = self._normalize_timestamp(end_ts)
        if s > e:
            s, e = e, s
        return [t for t in self._ticks if s <= t.get("timestamp", 0.0) <= e]

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        raise NotImplementedError

    def _on_tick(self, tick: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_realtime_status(self) -> Dict[str, Any]:
        return {"status": "active" if self.is_ready else "warmup", "ticks": len(self._ticks)}

    def reset(self) -> None:
        self._ticks.clear()
        self.is_ready = False
