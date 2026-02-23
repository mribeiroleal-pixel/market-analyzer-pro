from __future__ import annotations

from collections import deque
from typing import Any, Dict, Optional
import time

from .base import BaseAnalyst, AnalysisResult


class AbsorptionAnalyst(BaseAnalyst):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "Absorption"
        self.window_ms = int(self.config.get("window_ms", 100))
        self.absorption_threshold = float(self.config.get("absorption_threshold", 0.45))
        self.min_volume_per_window = float(self.config.get("min_volume_per_window", 2.0))
        self.max_windows = int(self.config.get("max_windows", 5000))
        self.warmup_windows = int(self.config.get("warmup_windows", 50))
        self.price_tolerance_abs = float(self.config.get("price_tolerance_abs", 1e-4))
        self.log_every_ticks = int(self.config.get("log_every_ticks", 100))

        self.micro_windows = deque(maxlen=max(100, self.max_windows))
        self.current_window = self._new_window()
        self.tick_counter = 0
        self.total_volume_received = 0.0
        self.invalid_ticks = 0
        self.out_of_order_ticks = 0
        self._last_ts = 0.0
        self.last_log_time = time.time()

    def _new_window(self) -> Dict[str, float]:
        return {"start_time": 0.0, "vol_buy": 0.0, "vol_sell": 0.0, "price_start": 0.0, "price_end": 0.0, "ticks": 0.0}

    def _on_tick(self, tick: Dict[str, Any]) -> None:
        self.tick_counter += 1
        ts = float(tick.get("timestamp", 0.0))
        px = float(tick.get("price", 0.0))
        side = tick.get("side", "neutral")
        vol = float(tick.get("_volume", self._extract_volume(tick)))
        if px <= 0:
            self.invalid_ticks += 1
            return
        if ts < self._last_ts:
            self.out_of_order_ticks += 1
        self._last_ts = max(self._last_ts, ts)
        self.total_volume_received += max(0.0, vol)

        if self.current_window["ticks"] == 0:
            self.current_window["start_time"] = ts
            self.current_window["price_start"] = px
            self.current_window["price_end"] = px

        elapsed_ms = (ts - self.current_window["start_time"]) * 1000.0
        if self.current_window["ticks"] > 0 and elapsed_ms >= self.window_ms:
            self.micro_windows.append(dict(self.current_window))
            self.current_window = self._new_window()
            self.current_window["start_time"] = ts
            self.current_window["price_start"] = px
            self.current_window["price_end"] = px

        if side == "buy":
            self.current_window["vol_buy"] += vol
        elif side == "sell":
            self.current_window["vol_sell"] += vol
        self.current_window["price_end"] = px
        self.current_window["ticks"] += 1

        if len(self.micro_windows) >= self.warmup_windows:
            self.is_ready = True

    def _price_tol(self, price: float) -> float:
        return max(self.price_tolerance_abs, abs(price) * float(self.config.get("price_tolerance_bps", 0.0)) / 10000.0)

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        s = self._normalize_timestamp(time_start)
        e = self._normalize_timestamp(time_end)
        if s > e:
            s, e = e, s
        windows = [w for w in self.micro_windows if s <= w["start_time"] <= e]
        if len(windows) < 3:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {"windows": len(windows)}, f"Apenas {len(windows)} janelas.")

        abs_buy = abs_sell = valid = 0
        for w in windows:
            buyv = w["vol_buy"]; sellv = w["vol_sell"]
            total = buyv + sellv
            if total < self.min_volume_per_window:
                continue
            valid += 1
            delta = buyv - sellv
            pct = abs(delta) / total if total > 0 else 0.0
            pm = w["price_end"] - w["price_start"]
            tol = self._price_tol(w["price_start"] or price or 1.0)
            if delta < 0 and pct >= self.absorption_threshold and pm >= -tol:
                abs_buy += 1
            if delta > 0 and pct >= self.absorption_threshold and pm <= tol:
                abs_sell += 1

        if valid < 3:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {"valid_windows": valid}, "Janelas válidas insuficientes.")

        total_buy = sum(w["vol_buy"] for w in windows)
        total_sell = sum(w["vol_sell"] for w in windows)
        total_vol = total_buy + total_sell
        bp = abs_buy / valid
        sp = abs_sell / valid
        details = {
            "valid_windows": valid,
            "total_windows": len(windows),
            "abs_buy_pct": round(bp, 3),
            "abs_sell_pct": round(sp, 3),
            "delta": round(total_buy - total_sell, 4),
            "total_volume_region": round(total_vol, 2),
        }
        if bp > 0.35:
            conf = min(0.95, 0.55 + bp + min(0.15, total_vol / 1000.0))
            return AnalysisResult(self.name, e, price, "ABSORCAO_COMPRA", conf, details, "Vendas agressivas absorvidas sem queda proporcional.")
        if sp > 0.35:
            conf = min(0.95, 0.55 + sp + min(0.15, total_vol / 1000.0))
            return AnalysisResult(self.name, e, price, "ABSORCAO_VENDA", conf, details, "Compras agressivas absorvidas sem alta proporcional.")
        conf = max(0.35, min(0.75, 0.45 + min(0.2, total_vol / 1500.0) + min(0.15, valid / 20.0)))
        return AnalysisResult(self.name, e, price, "SEM_ABSORCAO", conf, details, "Sem absorção significativa.")

    def get_realtime_status(self) -> Dict[str, Any]:
        status = "active" if self.is_ready else "warmup"
        recent = list(self.micro_windows)[-20:]
        return {
            "status": status,
            "ticks": self.tick_counter,
            "windows": len(self.micro_windows),
            "recent_windows": len(recent),
            "invalid_ticks": self.invalid_ticks,
            "out_of_order_ticks": self.out_of_order_ticks,
            "total_volume": round(self.total_volume_received, 2),
        }

    def reset(self) -> None:
        super().reset()
        self.micro_windows.clear()
        self.current_window = self._new_window()
        self.tick_counter = 0
        self.total_volume_received = 0.0
        self.invalid_ticks = 0
        self.out_of_order_ticks = 0
        self._last_ts = 0.0
