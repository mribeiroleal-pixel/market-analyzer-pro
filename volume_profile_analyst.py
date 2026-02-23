from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_HALF_UP

from .base import BaseAnalyst, AnalysisResult


class VolumeProfileAnalyst(BaseAnalyst):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "VolumeProfile"
        self.price_step = Decimal(str(self.config.get("price_step", "0.0001")))
        self.value_area_ratio = float(self.config.get("value_area_ratio", 0.7))
        self.min_ticks = int(self.config.get("min_ticks", 10))
        self.ready_ticks = int(self.config.get("ready_ticks", 50))
        self._counter = 0

    def _p2l(self, price: float) -> int:
        return int((Decimal(str(price)) / self.price_step).to_integral_value(rounding=ROUND_HALF_UP))

    def _l2p(self, level: int) -> float:
        return float(Decimal(level) * self.price_step)

    def _on_tick(self, tick: Dict[str, Any]) -> None:
        self._counter += 1
        if self._counter >= self.ready_ticks:
            self.is_ready = True

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        ticks = self.get_ticks_in_range(time_start, time_end)
        e = self._normalize_timestamp(time_end)
        if len(ticks) < self.min_ticks:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {"ticks": len(ticks)}, "Poucos ticks para volume profile.")
        profile: Dict[int, float] = defaultdict(float)
        for t in ticks:
            lv = self._p2l(float(t.get("price", 0.0)))
            profile[lv] += float(t.get("_volume", self._extract_volume(t)))
        if not profile:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {}, "Perfil vazio.")
        total_vol = sum(profile.values())
        poc_level = max(profile, key=lambda k: profile[k])
        sorted_by_vol = sorted(profile.items(), key=lambda kv: kv[1], reverse=True)
        va_levels = set()
        acc = 0.0
        for lv, v in sorted_by_vol:
            va_levels.add(lv); acc += v
            if acc / (total_vol or 1.0) >= self.value_area_ratio:
                break
        vah = max(va_levels); val = min(va_levels)
        current_level = self._p2l(price)
        if current_level > vah:
            cls = "ACIMA_VALOR"
            desc = "Preço acima da área de valor (possível continuação/excesso)."
        elif current_level < val:
            cls = "ABAIXO_VALOR"
            desc = "Preço abaixo da área de valor (possível continuação/excesso)."
        else:
            cls = "DENTRO_VALOR"
            desc = "Preço dentro da área de valor."
        conf = 0.55 if cls == "DENTRO_VALOR" else 0.7
        details = {
            "poc": self._l2p(poc_level),
            "vah": self._l2p(vah),
            "val": self._l2p(val),
            "levels": len(profile),
            "total_volume": round(total_vol, 2),
            "value_area_coverage": round(acc / (total_vol or 1.0), 3),
        }
        return AnalysisResult(self.name, e, price, cls, conf, details, desc)

    def get_realtime_status(self) -> Dict[str, Any]:
        return {"status": "active" if self.is_ready else "warmup", "ticks_processed": self._counter, "price_step": str(self.price_step)}

    def reset(self) -> None:
        super().reset(); self._counter = 0
