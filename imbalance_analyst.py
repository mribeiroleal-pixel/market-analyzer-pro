from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_HALF_UP

from .base import BaseAnalyst, AnalysisResult


class ImbalanceAnalyst(BaseAnalyst):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "Imbalance"
        self.price_step = Decimal(str(self.config.get("price_step", "0.0001")))
        if self.price_step <= 0:
            raise ValueError("price_step must be > 0")
        self.imbalance_ratio = float(self.config.get("imbalance_ratio", 3.0))
        self.max_levels = int(self.config.get("max_levels", 2000))
        self.min_volume_threshold = float(self.config.get("min_volume_threshold", 0.1))
        self.ready_ticks = int(self.config.get("ready_ticks", 20))
        self.levels: Dict[int, Dict[str, float]] = defaultdict(lambda: {"ask": 0.0, "bid": 0.0})
        self._level_order: deque[int] = deque(maxlen=max(50, self.max_levels))
        self.tick_counter = 0

    def _p2l(self, price: float) -> int:
        return int((Decimal(str(price)) / self.price_step).to_integral_value(rounding=ROUND_HALF_UP))

    def _l2p(self, level: int) -> float:
        return float(Decimal(level) * self.price_step)

    def _on_tick(self, tick: Dict[str, Any]) -> None:
        self.tick_counter += 1
        level = self._p2l(float(tick.get("price", 0.0)))
        vol = float(tick.get("_volume", self._extract_volume(tick)))
        side = tick.get("side", "neutral")
        if level not in self.levels:
            if len(self.levels) >= self.max_levels and self._level_order:
                oldest = self._level_order.popleft()
                self.levels.pop(oldest, None)
            self._level_order.append(level)
        if side == "buy":
            self.levels[level]["ask"] += vol
        elif side == "sell":
            self.levels[level]["bid"] += vol
        if self.tick_counter >= self.ready_ticks:
            self.is_ready = True

    def _stacking(self, imbs: List[Dict[str, Any]], sorted_lvs: List[int]) -> int:
        if not imbs:
            return 0
        imb_set = {i["level"] for i in imbs}
        cur = mx = 0
        for lv in sorted_lvs:
            if lv in imb_set:
                cur += 1; mx = max(mx, cur)
            else:
                cur = 0
        return mx

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        s = self._normalize_timestamp(time_start)
        e = self._normalize_timestamp(time_end)
        ticks = self.get_ticks_in_range(s, e)
        if len(ticks) < 5:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {"ticks": len(ticks)}, "Poucos ticks na região.")

        rl: Dict[int, Dict[str, float]] = defaultdict(lambda: {"ask": 0.0, "bid": 0.0})
        for t in ticks:
            lv = self._p2l(float(t.get("price", 0.0)))
            vol = float(t.get("_volume", self._extract_volume(t)))
            side = t.get("side", "neutral")
            if side == "buy": rl[lv]["ask"] += vol
            elif side == "sell": rl[lv]["bid"] += vol

        sorted_lvs = sorted(rl)
        if len(sorted_lvs) < 2:
            return AnalysisResult(self.name, e, price, "DADOS_INSUFICIENTES", 0.0, {"levels": len(sorted_lvs)}, "Poucos níveis de preço.")

        buy_imbs: List[Dict[str, Any]] = []
        sell_imbs: List[Dict[str, Any]] = []
        for i in range(1, len(sorted_lvs)):
            cur, prev = sorted_lvs[i], sorted_lvs[i-1]
            ask_cur = rl[cur]["ask"]; bid_prev = rl[prev]["bid"]
            if bid_prev >= self.min_volume_threshold:
                ratio = ask_cur / bid_prev if bid_prev > 0 else 0.0
                if ratio >= self.imbalance_ratio:
                    buy_imbs.append({"level": cur, "ratio": round(ratio, 2)})
            elif ask_cur > self.min_volume_threshold:
                buy_imbs.append({"level": cur, "ratio": 999.0, "zero_side": True})

            bid_cur = rl[cur]["bid"]; ask_prev = rl[prev]["ask"]
            if ask_prev >= self.min_volume_threshold:
                ratio = bid_cur / ask_prev if ask_prev > 0 else 0.0
                if ratio >= self.imbalance_ratio:
                    sell_imbs.append({"level": cur, "ratio": round(ratio, 2)})
            elif bid_cur > self.min_volume_threshold:
                sell_imbs.append({"level": cur, "ratio": 999.0, "zero_side": True})

        bs = self._stacking(buy_imbs, sorted_lvs)
        ss = self._stacking(sell_imbs, sorted_lvs)
        details = {
            "buy_imbalances": len(buy_imbs),
            "sell_imbalances": len(sell_imbs),
            "buy_stacking": bs,
            "sell_stacking": ss,
            "total_levels": len(sorted_lvs),
            "levels_preview": [self._l2p(lv) for lv in sorted_lvs[:10]],
        }

        if bs >= 3 and bs >= ss:
            conf = min(0.95, 0.6 + bs * 0.08)
            return AnalysisResult(self.name, e, price, "IMBALANCE_COMPRADOR", conf, details, f"Stacking comprador S{bs} detectado.")
        if ss >= 3:
            conf = min(0.95, 0.6 + ss * 0.08)
            return AnalysisResult(self.name, e, price, "IMBALANCE_VENDEDOR", conf, details, f"Stacking vendedor S{ss} detectado.")
        if buy_imbs or sell_imbs:
            dom = "comprador" if len(buy_imbs) >= len(sell_imbs) else "vendedor"
            return AnalysisResult(self.name, e, price, "IMBALANCE_ISOLADO", 0.5, details, f"Imbalances isolados. Dominante: {dom}.")
        return AnalysisResult(self.name, e, price, "SEM_IMBALANCE", 0.6, details, "Fluxo equilibrado.")

    def get_realtime_status(self) -> Dict[str, Any]:
        return {"status": "active" if self.is_ready else "warmup", "tracked_levels": len(self.levels), "ticks": self.tick_counter, "price_step": str(self.price_step)}

    def reset(self) -> None:
        super().reset()
        self.levels.clear(); self._level_order.clear(); self.tick_counter = 0
