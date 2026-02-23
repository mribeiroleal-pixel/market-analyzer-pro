"""
📈 Delta Flow Analyst — Detecta fluxo agressivo (delta), aceleração e reversão.

Objetivo:
- Medir dominância compradora/vendedora por janela de ticks
- Identificar aceleração de delta (pressão aumentando)
- Identificar reversão de fluxo (mudança de dominância)
- Expor status em tempo real para painel

Compatível com:
- backend/base.py -> BaseAnalyst, AnalysisResult
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional
import time

from .base import BaseAnalyst, AnalysisResult


class DeltaFlowAnalyst(BaseAnalyst):
    """
    Analista de fluxo por delta (agressão líquida).

    Lógica:
    - Acumula ticks recentes em uma janela deslizante
    - Calcula delta = vol_buy - vol_sell
    - Mede proporção de dominância (|delta| / vol_total)
    - Compara delta recente vs delta anterior para detectar aceleração / reversão
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config or {})
        self.name = "DeltaFlow"

        # Configs
        self.window_ticks: int = max(20, int(self.config.get("window_ticks", 120)))
        self.min_ticks_region: int = max(5, int(self.config.get("min_ticks_region", 12)))
        self.min_volume_region: float = max(0.0, float(self.config.get("min_volume_region", 2.0)))

        self.delta_dom_threshold: float = float(self.config.get("delta_dom_threshold", 0.60))
        self.strong_dom_threshold: float = float(self.config.get("strong_dom_threshold", 0.75))
        self.reversal_dom_threshold: float = float(self.config.get("reversal_dom_threshold", 0.55))
        self.accel_factor_threshold: float = float(self.config.get("accel_factor_threshold", 1.35))

        self.realtime_lookback: int = max(10, int(self.config.get("realtime_lookback", 40)))
        self.log_every_ticks: int = max(10, int(self.config.get("log_every_ticks", 100)))

        # Buffer de ticks recentes (normalizados)
        self._ticks: Deque[Dict[str, Any]] = deque(maxlen=self.window_ticks * 4)

        # Telemetria
        self.tick_counter: int = 0
        self.total_volume_received: float = 0.0
        self.invalid_ticks: int = 0
        self.last_log_time: float = time.time()

        # Estado
        self.is_ready = False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_timestamp(ts: Any) -> float:
        """Normaliza timestamp para segundos (aceita ms)."""
        try:
            tsf = float(ts)
        except (TypeError, ValueError):
            return 0.0
        return tsf / 1000.0 if tsf > 1e12 else tsf

    @staticmethod
    def _normalize_side(side: Any) -> str:
        """Normaliza side para 'buy' / 'sell' / 'neutral'."""
        if not isinstance(side, str):
            return "neutral"
        s = side.strip().lower()
        if s in ("buy", "b", "compra", "buyer"):
            return "buy"
        if s in ("sell", "s", "venda", "seller"):
            return "sell"
        return "neutral"

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            v = float(value)
            if v != v:  # NaN
                return default
            return v
        except (TypeError, ValueError):
            return default

    def _get_volume(self, tick: Dict[str, Any]) -> float:
        """
        Prioridade de volume:
        1) volume_synthetic
        2) volume_real
        3) volume
        fallback: 0.0
        """
        for key in ("volume_synthetic", "volume_real", "volume"):
            if key in tick and tick[key] is not None:
                v = self._safe_float(tick[key], 0.0)
                if v >= 0:
                    return v
        return 0.0

    def _slice_metrics(self, ticks: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calcula métricas básicas de uma lista de ticks normalizados."""
        if not ticks:
            return {
                "vol_buy": 0.0,
                "vol_sell": 0.0,
                "vol_total": 0.0,
                "delta": 0.0,
                "delta_abs": 0.0,
                "dom_ratio": 0.0,
                "tick_count": 0,
                "price_start": 0.0,
                "price_end": 0.0,
                "price_change": 0.0,
                "duration_s": 0.0,
                "ticks_per_sec": 0.0,
            }

        vol_buy = 0.0
        vol_sell = 0.0

        for t in ticks:
            side = t["side"]
            vol = t["vol"]
            if side == "buy":
                vol_buy += vol
            elif side == "sell":
                vol_sell += vol

        vol_total = vol_buy + vol_sell
        delta = vol_buy - vol_sell
        delta_abs = abs(delta)
        dom_ratio = (delta_abs / vol_total) if vol_total > 0 else 0.0

        p0 = ticks[0]["price"]
        p1 = ticks[-1]["price"]
        ts0 = ticks[0]["ts"]
        ts1 = ticks[-1]["ts"]
        duration = max(0.001, ts1 - ts0)

        return {
            "vol_buy": vol_buy,
            "vol_sell": vol_sell,
            "vol_total": vol_total,
            "delta": delta,
            "delta_abs": delta_abs,
            "dom_ratio": dom_ratio,
            "tick_count": len(ticks),
            "price_start": p0,
            "price_end": p1,
            "price_change": p1 - p0,
            "duration_s": duration,
            "ticks_per_sec": len(ticks) / duration,
        }

    def _classify_direction(self, delta: float, dom_ratio: float) -> str:
        """Classifica direção principal do fluxo."""
        if dom_ratio < self.delta_dom_threshold:
            return "NEUTRO"
        return "COMPRADOR" if delta > 0 else "VENDEDOR"

    # ------------------------------------------------------------------ #
    # Interface BaseAnalyst
    # ------------------------------------------------------------------ #
    def _on_tick(self, tick: Dict[str, Any]) -> None:
        """
        Processa tick em tempo real.
        Espera chaves: price, side, timestamp, volume_*
        """
        self.tick_counter += 1

        price = self._safe_float(tick.get("price"), 0.0)
        ts = self._normalize_timestamp(tick.get("timestamp", time.time()))
        side = self._normalize_side(tick.get("side"))
        vol = self._get_volume(tick)

        # Tick inválido mínimo
        if price <= 0 or ts <= 0:
            self.invalid_ticks += 1
            return

        self.total_volume_received += vol

        self._ticks.append(
            {
                "price": price,
                "ts": ts,
                "side": side,
                "vol": vol,
            }
        )

        # warmup
        if len(self._ticks) >= max(30, self.min_ticks_region):
            self.is_ready = True

        # log periódico
        if self.tick_counter % self.log_every_ticks == 0:
            now = time.time()
            if now - self.last_log_time > 5:
                print(
                    f"📈 [DELTA_FLOW] ticks={self.tick_counter} "
                    f"| vol={self.total_volume_received:.1f} "
                    f"| invalid={self.invalid_ticks} "
                    f"| buffer={len(self._ticks)}"
                )
                self.last_log_time = now

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        """
        Analisa uma região de tempo e classifica o fluxo de delta.

        Args:
            price: preço de referência
            time_start: timestamp início (s ou ms)
            time_end: timestamp fim (s ou ms)
        """
        time_start = self._normalize_timestamp(time_start)
        time_end = self._normalize_timestamp(time_end)

        if time_end < time_start:
            time_start, time_end = time_end, time_start

        ticks = self.get_ticks_in_range(time_start, time_end)

        if len(ticks) < self.min_ticks_region:
            return AnalysisResult(
                self.name,
                time_end,
                price,
                "DADOS_INSUFICIENTES",
                0.0,
                description=f"Apenas {len(ticks)} ticks na região (mínimo {self.min_ticks_region}).",
                details={"ticks_encontrados": len(ticks)},
            )

        # normaliza ticks da região (sem alterar origem)
        region_ticks: List[Dict[str, Any]] = []
        invalid_local = 0
        for t in ticks:
            p = self._safe_float(t.get("price"), 0.0)
            ts = self._normalize_timestamp(t.get("timestamp", 0.0))
            s = self._normalize_side(t.get("side"))
            v = self._get_volume(t)
            if p <= 0 or ts <= 0:
                invalid_local += 1
                continue
            region_ticks.append({"price": p, "ts": ts, "side": s, "vol": v})

        if len(region_ticks) < self.min_ticks_region:
            return AnalysisResult(
                self.name,
                time_end,
                price,
                "DADOS_INSUFICIENTES",
                0.0,
                description=f"Ticks válidos insuficientes na região ({len(region_ticks)}).",
                details={
                    "ticks_validos": len(region_ticks),
                    "ticks_invalidos": invalid_local,
                },
            )

        metrics = self._slice_metrics(region_ticks)

        if metrics["vol_total"] < self.min_volume_region:
            return AnalysisResult(
                self.name,
                time_end,
                price,
                "DADOS_INSUFICIENTES",
                0.0,
                description=(
                    f"Volume total insuficiente ({metrics['vol_total']:.2f}) "
                    f"na região (mínimo {self.min_volume_region:.2f})."
                ),
                details={
                    "vol_total": round(metrics["vol_total"], 4),
                    "ticks_validos": metrics["tick_count"],
                },
            )

        # Divide em metades para detectar aceleração/reversão
        n = len(region_ticks)
        mid = max(1, n // 2)
        first_metrics = self._slice_metrics(region_ticks[:mid])
        last_metrics = self._slice_metrics(region_ticks[mid:])

        first_dom = self._classify_direction(first_metrics["delta"], first_metrics["dom_ratio"])
        last_dom = self._classify_direction(last_metrics["delta"], last_metrics["dom_ratio"])
        final_dom = self._classify_direction(metrics["delta"], metrics["dom_ratio"])

        # aceleração: mesma direção + delta final significativamente maior
        same_direction = (
            first_dom in ("COMPRADOR", "VENDEDOR")
            and last_dom == first_dom
        )
        accel_factor = (
            (last_metrics["delta_abs"] / first_metrics["delta_abs"])
            if first_metrics["delta_abs"] > 0
            else (999.0 if last_metrics["delta_abs"] > 0 else 1.0)
        )
        is_accel = same_direction and accel_factor >= self.accel_factor_threshold

        # reversão: primeira metade dominava uma direção e a última domina a oposta
        is_reversal = (
            first_dom in ("COMPRADOR", "VENDEDOR")
            and last_dom in ("COMPRADOR", "VENDEDOR")
            and first_dom != last_dom
            and last_metrics["dom_ratio"] >= self.reversal_dom_threshold
        )

        # alinhamento com movimento de preço
        price_change = metrics["price_change"]
        price_aligns = (
            (metrics["delta"] > 0 and price_change >= 0)
            or (metrics["delta"] < 0 and price_change <= 0)
        )

        details = {
            "tick_count": metrics["tick_count"],
            "vol_total": round(metrics["vol_total"], 4),
            "vol_buy": round(metrics["vol_buy"], 4),
            "vol_sell": round(metrics["vol_sell"], 4),
            "delta": round(metrics["delta"], 4),
            "dom_ratio": round(metrics["dom_ratio"], 3),
            "direction": final_dom,
            "price_start": round(metrics["price_start"], 6),
            "price_end": round(metrics["price_end"], 6),
            "price_change": round(price_change, 6),
            "duration_s": round(metrics["duration_s"], 4),
            "ticks_per_sec": round(metrics["ticks_per_sec"], 2),
            "first_half_delta": round(first_metrics["delta"], 4),
            "first_half_dom_ratio": round(first_metrics["dom_ratio"], 3),
            "first_half_dir": first_dom,
            "last_half_delta": round(last_metrics["delta"], 4),
            "last_half_dom_ratio": round(last_metrics["dom_ratio"], 3),
            "last_half_dir": last_dom,
            "accel_factor": round(accel_factor if accel_factor != 999.0 else 999.0, 3),
            "is_accel": is_accel,
            "is_reversal": is_reversal,
            "price_aligns": price_aligns,
            "ticks_invalidos_ignorados": invalid_local,
        }

        # Classificação final
        if is_reversal:
            conf = min(0.92, 0.62 + last_metrics["dom_ratio"] * 0.25 + (0.05 if price_aligns else 0.0))
            label = (
                "REVERSAO_FLUXO_COMPRADOR"
                if last_dom == "COMPRADOR"
                else "REVERSAO_FLUXO_VENDEDOR"
            )
            desc = (
                f"🔁 Reversão de fluxo detectada: {first_dom} → {last_dom}. "
                f"Dom última metade={last_metrics['dom_ratio']:.0%} | Δ final={metrics['delta']:+.2f}"
            )
            return AnalysisResult(self.name, time_end, price, label, round(conf, 3), details, desc)

        if final_dom == "COMPRADOR" and metrics["dom_ratio"] >= self.strong_dom_threshold:
            conf = min(0.95, 0.60 + metrics["dom_ratio"] * 0.25 + (0.08 if is_accel else 0.0))
            label = "DELTA_COMPRADOR_FORTE" if is_accel else "DELTA_COMPRADOR"
            desc = (
                f"📈 Fluxo comprador dominante ({metrics['dom_ratio']:.0%}). "
                f"Δ={metrics['delta']:+.2f} | Vol={metrics['vol_total']:.1f}"
                + (" | aceleração detectada" if is_accel else "")
            )
            return AnalysisResult(self.name, time_end, price, label, round(conf, 3), details, desc)

        if final_dom == "VENDEDOR" and metrics["dom_ratio"] >= self.strong_dom_threshold:
            conf = min(0.95, 0.60 + metrics["dom_ratio"] * 0.25 + (0.08 if is_accel else 0.0))
            label = "DELTA_VENDEDOR_FORTE" if is_accel else "DELTA_VENDEDOR"
            desc = (
                f"📉 Fluxo vendedor dominante ({metrics['dom_ratio']:.0%}). "
                f"Δ={metrics['delta']:+.2f} | Vol={metrics['vol_total']:.1f}"
                + (" | aceleração detectada" if is_accel else "")
            )
            return AnalysisResult(self.name, time_end, price, label, round(conf, 3), details, desc)

        if final_dom in ("COMPRADOR", "VENDEDOR"):
            conf = min(0.80, 0.50 + metrics["dom_ratio"] * 0.25)
            label = "PRESSAO_COMPRADORA" if final_dom == "COMPRADOR" else "PRESSAO_VENDEDORA"
            desc = (
                f"Fluxo com viés {final_dom.lower()} ({metrics['dom_ratio']:.0%}), "
                f"sem dominância forte. Δ={metrics['delta']:+.2f}"
            )
            return AnalysisResult(self.name, time_end, price, label, round(conf, 3), details, desc)

        return AnalysisResult(
            self.name,
            time_end,
            price,
            "DELTA_NEUTRO",
            0.55,
            details,
            f"Fluxo neutro. Δ={metrics['delta']:+.2f} | dominância={metrics['dom_ratio']:.0%}",
        )

    def get_realtime_status(self) -> Dict[str, Any]:
        """Status resumido em tempo real para painel."""
        if not self.is_ready or len(self._ticks) < 10:
            return {
                "status": "warmup",
                "ticks": self.tick_counter,
                "buffer_ticks": len(self._ticks),
                "total_volume": round(self.total_volume_received, 2),
                "invalid_ticks": self.invalid_ticks,
            }

        recent = list(self._ticks)[-self.realtime_lookback:]
        m = self._slice_metrics(recent)
        direction = self._classify_direction(m["delta"], m["dom_ratio"])

        return {
            "status": "active",
            "ticks": self.tick_counter,
            "buffer_ticks": len(self._ticks),
            "total_volume": round(self.total_volume_received, 2),
            "invalid_ticks": self.invalid_ticks,
            "recent_delta": round(m["delta"], 4),
            "recent_dom_ratio": round(m["dom_ratio"], 3),
            "recent_direction": direction,
            "recent_vol_total": round(m["vol_total"], 2),
            "recent_ticks_per_sec": round(m["ticks_per_sec"], 2),
        }

    def reset(self) -> None:
        """Reset completo do analista."""
        super().reset()
        self._ticks.clear()
        self.tick_counter = 0
        self.total_volume_received = 0.0
        self.invalid_ticks = 0
        self.last_log_time = time.time()
        self.is_ready = False

    def __repr__(self) -> str:
        return (
            f"<DeltaFlowAnalyst ready={self.is_ready} ticks={self.tick_counter} "
            f"buffer={len(self._ticks)}>"
        )