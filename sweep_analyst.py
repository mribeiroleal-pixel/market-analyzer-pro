from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from .base import BaseAnalyst, AnalysisResult


@dataclass
class SweepMetrics:
    price_start: float
    price_end: float
    price_max: float
    price_min: float
    price_range: float
    speed_per_sec: float
    reach_high: float
    reject_high: float
    reach_low: float
    reject_low: float
    vol_ratio_first_last: float
    max_tick_vol: float
    ticks: int


class LiquiditySweepAnalyst(BaseAnalyst):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "LiquiditySweep"
        self.sweep_threshold = float(self.config.get("sweep_rejection", 0.5))
        self.breakout_vol_ratio = float(self.config.get("breakout_vol_ratio", 1.5))
        self.min_ticks = int(self.config.get("min_ticks", 5))
        self.ready_ticks = int(self.config.get("ready_ticks", 100))
        self.reach_threshold = float(self.config.get("reach_threshold", 0.7))
        self.reject_threshold = float(self.config.get("reject_threshold", 0.2))
        self.tick_counter = 0

    def _on_tick(self, tick: Dict[str, Any]) -> None:
        self.tick_counter += 1
        if self.tick_counter >= self.ready_ticks:
            self.is_ready = True

    def _calc_metrics(self, ticks: List[Dict[str, Any]]) -> SweepMetrics:
        prices = [float(t.get("price", 0.0)) for t in ticks]
        p_start, p_end = prices[0], prices[-1]
        p_max, p_min = max(prices), min(prices)
        p_range = p_max - p_min
        ts_start = self._normalize_timestamp(ticks[0].get("timestamp", 0.0))
        ts_end = self._normalize_timestamp(ticks[-1].get("timestamp", 0.0))
        time_span = max(ts_end - ts_start, 0.01)
        speed = p_range / time_span if time_span > 0 else 0.0
        reach_high = (p_max - p_start) / p_range if p_range else 0.0
        reject_high = (p_max - p_end) / p_range if p_range else 0.0
        reach_low = (p_start - p_min) / p_range if p_range else 0.0
        reject_low = (p_end - p_min) / p_range if p_range else 0.0
        n = len(ticks)
        one = max(1, n // 3)
        vol_first = sum(float(t.get("_volume", self._extract_volume(t))) for t in ticks[:one])
        vol_last = sum(float(t.get("_volume", self._extract_volume(t))) for t in ticks[-one:])
        vol_ratio = (vol_last / vol_first) if vol_first > 0 else 1.0
        max_tick_vol = max(float(t.get("_volume", self._extract_volume(t))) for t in ticks)
        return SweepMetrics(round(p_start, 6), round(p_end, 6), round(p_max, 6), round(p_min, 6), round(p_range, 6), round(speed, 6), round(reach_high, 3), round(reject_high, 3), round(reach_low, 3), round(reject_low, 3), round(vol_ratio, 3), round(max_tick_vol, 4), n)

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        ticks = self.get_ticks_in_range(time_start, time_end)
        e = self._normalize_timestamp(time_end)
        if len(ticks) < self.min_ticks:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {"ticks": len(ticks)}, "Poucos ticks.")
        metrics = self._calc_metrics(ticks)
        if metrics.price_range == 0:
            return AnalysisResult(self.name, e, price, "SEM_SWEEP", 0.4, asdict(metrics), "Sem range.")
        if metrics.reach_high > self.reach_threshold and metrics.reject_high > self.sweep_threshold:
            conf = min(0.95, 0.5 + metrics.reject_high * 0.4)
            return AnalysisResult(self.name, e, price, "SWEEP_ALTA", conf, asdict(metrics), "Varrida para cima com rejeição.")
        if metrics.reach_low > self.reach_threshold and metrics.reject_low > self.sweep_threshold:
            conf = min(0.95, 0.5 + metrics.reject_low * 0.4)
            return AnalysisResult(self.name, e, price, "SWEEP_BAIXA", conf, asdict(metrics), "Varrida para baixo com rejeição.")
        if (metrics.reject_high < self.reject_threshold or metrics.reject_low < self.reject_threshold) and metrics.vol_ratio_first_last >= self.breakout_vol_ratio:
            return AnalysisResult(self.name, e, price, "BREAKOUT_REAL", 0.75, asdict(metrics), "Breakout com volume final crescente.")
        return AnalysisResult(self.name, e, price, "SEM_SWEEP", 0.55, asdict(metrics), "Movimento normal.")

    def get_realtime_status(self) -> Dict[str, Any]:
        return {"status": "active" if self.is_ready else "warmup", "ticks_processed": self.tick_counter}

    def reset(self) -> None:
        super().reset(); self.tick_counter = 0
