"""
🔒 Cluster Closure Analyst — Captura e rotula clusters ao fechar.

Gera dataset para treinamento de IA e detecta padrões de fechamento.

Compatível com base.py existente.
Integração principal via on_cluster_close() chamado pelo websocket_server.py
quando delta acumulado atinge delta_th.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Deque, Dict, List, Optional
import json
import logging
import math
import time

from .base import BaseAnalyst, AnalysisResult

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- #
# Snapshot de um cluster completo
# --------------------------------------------------------------------- #
@dataclass
class ClusterSnapshot:
    """
    Representa um cluster completo — desde abertura até fechamento.

    Campos preenchidos ao fechar + campos de outcome preenchidos
    pelo PRÓXIMO cluster (rotulagem retroativa).
    """

    # Identificação
    cluster_id: int
    symbol: str = "XAUUSD"

    # Tempo
    timestamp_open: float = 0.0
    timestamp_close: float = 0.0
    duration_seconds: float = 0.0

    # Geometria de preço
    price_open: float = 0.0
    price_close: float = 0.0
    price_high: float = 0.0
    price_low: float = 0.0
    price_range: float = 0.0

    # Delta
    delta_final: float = 0.0
    delta_max: float = 0.0
    delta_min: float = 0.0
    delta_direction: str = ""  # "buy" | "sell"

    # Wick ratio (rejeição)
    wick_ratio_top: float = 0.0
    wick_ratio_bot: float = 0.0

    # Volume
    vol_total: float = 0.0
    vol_buy: float = 0.0
    vol_sell: float = 0.0
    vol_efficiency: float = 0.0  # price_range / vol_total

    # Velocidade
    tick_count: int = 0
    ticks_per_second: float = 0.0

    # Sinais dos analistas no fechamento
    absorption_signal: str = "N/A"
    imbalance_signal: str = "N/A"
    delta_flow_signal: str = "N/A"
    execution_signal: str = "N/A"
    sweep_signal: str = "N/A"
    volume_profile_signal: str = "N/A"
    liquidity_break_signal: str = "N/A"

    # Padrão detectado pelo ClusterClosure
    pattern: str = "NEUTRO"
    pattern_confidence: float = 0.5

    # Rotulagem retroativa — preenchida quando o PRÓXIMO cluster fechar
    next_direction: str = "PENDENTE"     # "UP" | "DOWN" | "NEUTRAL"
    next_price_change: float = 0.0
    next_delta_direction: str = "PENDENTE"
    outcome: str = "PENDENTE"            # "BULL" | "BEAR" | "NEUTRAL"


class ClusterClosureAnalyst(BaseAnalyst):
    """
    Captura o estado completo de cada cluster ao fechar.

    Diferença para outros analistas:
    - fluxo principal via on_cluster_close()
    - _on_tick() apenas acumula estado do cluster em construção
    - analyze_region() existe para compatibilidade com BaseAnalyst
      e retorna análise estatística do histórico de clusters
    """

    DEFAULTS = {
        "max_clusters": 500,
        "symbol": "XAUUSD",
        "recent_vol_lookback": 50,
        "ready_clusters": 3,
        "neutral_range_factor": 0.20,   # 20% do range médio
        "fallback_neutral_th": 0.10,
        "fast_ticks_per_sec": 30.0,
        "high_vol_factor": 1.5,
        "low_vol_factor": 0.4,
        "very_low_vol_factor": 0.5,
        "slow_cluster_seconds": 45.0,
        "wick_rejection_ratio": 0.4,
        "pattern_stats_min_samples": 5,
        "print_logs": True,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config or {})
        self.name = "ClusterClosure"

        # Config sanitizada
        self.max_clusters: int = max(10, int(self.config.get("max_clusters", self.DEFAULTS["max_clusters"])))
        self.symbol: str = str(self.config.get("symbol", self.DEFAULTS["symbol"]) or "XAUUSD")
        self.recent_vol_lookback: int = max(
            5, int(self.config.get("recent_vol_lookback", self.DEFAULTS["recent_vol_lookback"]))
        )
        self.ready_clusters: int = max(1, int(self.config.get("ready_clusters", self.DEFAULTS["ready_clusters"])))

        self.neutral_range_factor: float = float(
            self.config.get("neutral_range_factor", self.DEFAULTS["neutral_range_factor"])
        )
        self.fallback_neutral_th: float = float(
            self.config.get("fallback_neutral_th", self.DEFAULTS["fallback_neutral_th"])
        )
        self.fast_ticks_per_sec: float = float(
            self.config.get("fast_ticks_per_sec", self.DEFAULTS["fast_ticks_per_sec"])
        )
        self.high_vol_factor: float = float(
            self.config.get("high_vol_factor", self.DEFAULTS["high_vol_factor"])
        )
        self.low_vol_factor: float = float(
            self.config.get("low_vol_factor", self.DEFAULTS["low_vol_factor"])
        )
        self.very_low_vol_factor: float = float(
            self.config.get("very_low_vol_factor", self.DEFAULTS["very_low_vol_factor"])
        )
        self.slow_cluster_seconds: float = float(
            self.config.get("slow_cluster_seconds", self.DEFAULTS["slow_cluster_seconds"])
        )
        self.wick_rejection_ratio: float = float(
            self.config.get("wick_rejection_ratio", self.DEFAULTS["wick_rejection_ratio"])
        )
        self.pattern_stats_min_samples: int = max(
            1, int(self.config.get("pattern_stats_min_samples", self.DEFAULTS["pattern_stats_min_samples"]))
        )
        self.print_logs: bool = bool(self.config.get("print_logs", self.DEFAULTS["print_logs"]))

        # Histórico de clusters fechados
        self.closed_clusters: Deque[ClusterSnapshot] = deque(maxlen=self.max_clusters)

        # Contador de clusters
        self.cluster_counter: int = 0

        # Estatísticas de padrões "aprendidos"
        self.pattern_stats: Dict[str, Dict[str, Any]] = {}

        # Volume recente (contexto)
        self._recent_vol: Deque[float] = deque(maxlen=self.recent_vol_lookback)

        # Estado cluster atual
        self.current_delta: float = 0.0
        self._reset_current()

        self.is_ready = False

        if self.print_logs:
            print(f"🔒 [CLUSTER_CLOSURE] Inicializado | max_clusters={self.max_clusters} | symbol={self.symbol}")
        logger.info("ClusterClosureAnalyst initialized max_clusters=%s symbol=%s", self.max_clusters, self.symbol)

    # ------------------------------------------------------------------ #
    # Helpers base
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            v = float(value)
            if not math.isfinite(v):
                return default
            return v
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_timestamp_local(ts: Any) -> float:
        """Fallback local de normalização caso BaseAnalyst não ofereça."""
        try:
            tsf = float(ts)
        except (TypeError, ValueError):
            return 0.0
        return tsf / 1000.0 if tsf > 1e12 else tsf

    def _normalize_timestamp_safe(self, ts: Any) -> float:
        """
        Usa _normalize_timestamp da base se existir; senão usa fallback local.
        """
        base_fn = getattr(self, "_normalize_timestamp", None)
        if callable(base_fn):
            try:
                return float(base_fn(ts))
            except Exception:
                pass
        return self._normalize_timestamp_local(ts)

    def _get_volume(self, tick: Dict[str, Any]) -> float:
        """Extrai volume com prioridade correta (volume_synthetic > real > volume)."""
        for key in ("volume_synthetic", "volume_real", "volume"):
            if key in tick and tick[key] is not None:
                v = self._safe_float(tick[key], 0.0)
                if v >= 0:
                    return v
        return 0.0

    @staticmethod
    def _normalize_side(side: Any) -> str:
        """Normaliza side para buy/sell/neutral."""
        if not isinstance(side, str):
            return "neutral"
        s = side.strip().lower()
        if s in ("buy", "b", "compra", "buyer"):
            return "buy"
        if s in ("sell", "s", "venda", "seller"):
            return "sell"
        return "neutral"

    # ------------------------------------------------------------------ #
    # Estado interno do cluster atual
    # ------------------------------------------------------------------ #
    def _reset_current(self) -> None:
        """Reseta o estado do cluster atual para o próximo cluster."""
        self.current = {
            "open_price": 0.0,
            "high": 0.0,
            "low": float("inf"),
            "vol_buy": 0.0,
            "vol_sell": 0.0,
            "delta_max": 0.0,
            "delta_min": 0.0,
            "tick_count": 0,
            "ts_open": 0.0,
            "last_price": 0.0,
            "last_ts": 0.0,
        }
        self.current_delta = 0.0

    # ------------------------------------------------------------------ #
    # Interface BaseAnalyst
    # ------------------------------------------------------------------ #
    def _on_tick(self, tick: Dict[str, Any]) -> None:
        """
        Acumula estado do cluster atual tick a tick.
        Timestamp idealmente já vem normalizado pela base; ainda assim normalizamos.
        """
        price = self._safe_float(tick.get("price"), 0.0)
        if price <= 0:
            return

        vol = self._get_volume(tick)
        side = self._normalize_side(tick.get("side"))
        ts = self._normalize_timestamp_safe(tick.get("timestamp", time.time()))
        if ts <= 0:
            ts = time.time()

        # primeiro tick do cluster
        if self.current["tick_count"] == 0:
            self.current["open_price"] = price
            self.current["ts_open"] = ts
            self.current["high"] = price
            self.current["low"] = price

        # atualiza preço/tempo final
        self.current["last_price"] = price
        self.current["last_ts"] = ts

        # atualiza high/low
        self.current["high"] = max(self.current["high"], price)
        self.current["low"] = min(self.current["low"], price)
        self.current["tick_count"] += 1

        # volume + delta
        if side == "buy":
            self.current["vol_buy"] += vol
            self.current_delta += vol
        elif side == "sell":
            self.current["vol_sell"] += vol
            self.current_delta -= vol

        # extremos de delta intracluster
        self.current["delta_max"] = max(self.current["delta_max"], self.current_delta)
        self.current["delta_min"] = min(self.current["delta_min"], self.current_delta)

    def analyze_region(self, price: float, time_start: float, time_end: float) -> AnalysisResult:
        """
        Compatibilidade com BaseAnalyst.
        Retorna análise estatística dos clusters fechados na região.
        """
        time_start = self._normalize_timestamp_safe(time_start)
        time_end = self._normalize_timestamp_safe(time_end)

        if time_end < time_start:
            time_start, time_end = time_end, time_start

        clusters_in_range = [
            c for c in self.closed_clusters
            if time_start <= c.timestamp_close <= time_end
        ]

        if not clusters_in_range:
            return AnalysisResult(
                self.name,
                time_end,
                price,
                "SEM_CLUSTERS",
                0.0,
                description="Nenhum cluster fechado na região selecionada.",
                details={"total_clusters": self.cluster_counter},
            )

        bull = sum(1 for c in clusters_in_range if c.outcome == "BULL")
        bear = sum(1 for c in clusters_in_range if c.outcome == "BEAR")
        neutral = sum(1 for c in clusters_in_range if c.outcome == "NEUTRAL")
        pending = sum(1 for c in clusters_in_range if c.outcome == "PENDENTE")

        total = len(clusters_in_range)
        labeled = total - pending

        patterns: Dict[str, int] = {}
        for c in clusters_in_range:
            patterns[c.pattern] = patterns.get(c.pattern, 0) + 1
        dominant_pattern = max(patterns, key=patterns.get) if patterns else "N/A"

        avg_vol = sum(c.vol_total for c in clusters_in_range) / total
        avg_duration = sum(c.duration_seconds for c in clusters_in_range) / total
        avg_delta = sum(abs(c.delta_final) for c in clusters_in_range) / total

        details = {
            "clusters_na_regiao": total,
            "clusters_rotulados": labeled,
            "bull": bull,
            "bear": bear,
            "neutral": neutral,
            "pendente": pending,
            "padrao_dominante": dominant_pattern,
            "vol_medio": round(avg_vol, 2),
            "duracao_media_s": round(avg_duration, 2),
            "delta_medio_abs": round(avg_delta, 4),
            "padroes": patterns,
        }

        if labeled > 0:
            bull_rate = bull / labeled
            bear_rate = bear / labeled

            if bull_rate > 0.6:
                conf = min(0.90, 0.60 + bull_rate * 0.30)
                return AnalysisResult(
                    self.name,
                    time_end,
                    price,
                    "HISTORICO_BULL",
                    round(conf, 3),
                    details,
                    f"📈 {bull}/{labeled} clusters rotulados foram BULL ({bull_rate:.0%}). "
                    f"Padrão dominante: {dominant_pattern}.",
                )
            if bear_rate > 0.6:
                conf = min(0.90, 0.60 + bear_rate * 0.30)
                return AnalysisResult(
                    self.name,
                    time_end,
                    price,
                    "HISTORICO_BEAR",
                    round(conf, 3),
                    details,
                    f"📉 {bear}/{labeled} clusters rotulados foram BEAR ({bear_rate:.0%}). "
                    f"Padrão dominante: {dominant_pattern}.",
                )

        return AnalysisResult(
            self.name,
            time_end,
            price,
            "HISTORICO_NEUTRO",
            0.50,
            details,
            f"Região com {total} clusters. Padrão dominante: {dominant_pattern}. "
            f"Vol médio: {avg_vol:.1f} | Duração média: {avg_duration:.1f}s",
        )

    # ------------------------------------------------------------------ #
    # Fluxo principal — chamado pelo servidor
    # ------------------------------------------------------------------ #
    def on_cluster_close(
        self,
        close_price: float,
        close_ts: float,
        analyst_signals: Optional[Dict[str, str]] = None,
    ) -> AnalysisResult:
        """
        Chamado pelo websocket_server quando o cluster fecha.

        Args:
            close_price: preço no fechamento do cluster
            close_ts: timestamp do fechamento (s ou ms)
            analyst_signals: sinais dos outros analistas

        Returns:
            AnalysisResult com padrão detectado para o cluster recém-fechado.
        """
        analyst_signals = analyst_signals or {}
        close_price = self._safe_float(close_price, self.current.get("last_price", 0.0))
        close_ts = self._normalize_timestamp_safe(close_ts)

        if close_price <= 0:
            close_price = self.current.get("last_price", 0.0) or self.current.get("open_price", 0.0)

        if close_ts <= 0:
            close_ts = self.current.get("last_ts", 0.0) or time.time()

        c = self.current

        # Se fechar sem tick algum, cria snapshot mínimo (evita crash)
        if c["tick_count"] == 0:
            self.cluster_counter += 1
            snap = ClusterSnapshot(
                cluster_id=self.cluster_counter,
                symbol=self.symbol,
                timestamp_open=close_ts,
                timestamp_close=close_ts,
                duration_seconds=0.001,
                price_open=close_price,
                price_close=close_price,
                price_high=close_price,
                price_low=close_price,
                price_range=0.0,
                delta_final=0.0,
                delta_max=0.0,
                delta_min=0.0,
                delta_direction="buy",
                vol_total=0.0,
                vol_buy=0.0,
                vol_sell=0.0,
                tick_count=0,
                ticks_per_second=0.0,
                absorption_signal=analyst_signals.get("absorption", "N/A"),
                imbalance_signal=analyst_signals.get("imbalance", "N/A"),
                delta_flow_signal=analyst_signals.get("delta_flow", "N/A"),
                execution_signal=analyst_signals.get("execution", "N/A"),
                sweep_signal=analyst_signals.get("sweep", "N/A"),
                volume_profile_signal=analyst_signals.get("volume_profile", "N/A"),
                liquidity_break_signal=analyst_signals.get("liquidity_break", "N/A"),
                pattern="NEUTRO",
                pattern_confidence=0.30,
            )
            self.closed_clusters.append(snap)
            self._reset_current()
            return AnalysisResult(
                self.name,
                close_ts,
                close_price,
                "NEUTRO",
                0.30,
                details={"cluster_id": self.cluster_counter, "warning": "cluster fechado sem ticks"},
                description="Cluster fechado sem ticks válidos.",
            )

        # Métricas do cluster
        duration = max(close_ts - c["ts_open"], 0.001)
        vol_total = c["vol_buy"] + c["vol_sell"]

        high = c["high"] if math.isfinite(c["high"]) else close_price
        low = c["low"] if math.isfinite(c["low"]) and c["low"] != float("inf") else close_price
        price_range = max(0.0, high - low)

        direction = "buy" if self.current_delta >= 0 else "sell"

        # Wick ratios
        if price_range > 0:
            wick_top = max(0.0, (high - close_price) / price_range)
            wick_bot = max(0.0, (close_price - low) / price_range)
            # clamp
            wick_top = min(wick_top, 1.5)
            wick_bot = min(wick_bot, 1.5)
        else:
            wick_top = 0.0
            wick_bot = 0.0

        vol_efficiency = (price_range / vol_total) if vol_total > 0 else 0.0

        self.cluster_counter += 1

        snapshot = ClusterSnapshot(
            cluster_id=self.cluster_counter,
            symbol=self.symbol,
            timestamp_open=round(c["ts_open"], 6),
            timestamp_close=round(close_ts, 6),
            duration_seconds=round(duration, 3),
            price_open=round(c["open_price"], 6),
            price_close=round(close_price, 6),
            price_high=round(high, 6),
            price_low=round(low, 6),
            price_range=round(price_range, 6),
            delta_final=round(self.current_delta, 4),
            delta_max=round(c["delta_max"], 4),
            delta_min=round(c["delta_min"], 4),
            delta_direction=direction,
            wick_ratio_top=round(wick_top, 3),
            wick_ratio_bot=round(wick_bot, 3),
            vol_total=round(vol_total, 4),
            vol_buy=round(c["vol_buy"], 4),
            vol_sell=round(c["vol_sell"], 4),
            vol_efficiency=round(vol_efficiency, 6),
            tick_count=int(c["tick_count"]),
            ticks_per_second=round((c["tick_count"] / duration) if duration > 0 else 0.0, 2),
            absorption_signal=str(analyst_signals.get("absorption", "N/A")),
            imbalance_signal=str(analyst_signals.get("imbalance", "N/A")),
            delta_flow_signal=str(analyst_signals.get("delta_flow", "N/A")),
            execution_signal=str(analyst_signals.get("execution", "N/A")),
            sweep_signal=str(analyst_signals.get("sweep", "N/A")),
            volume_profile_signal=str(analyst_signals.get("volume_profile", "N/A")),
            liquidity_break_signal=str(analyst_signals.get("liquidity_break", "N/A")),
        )

        # Rotula cluster anterior com o que aconteceu depois
        if self.closed_clusters:
            prev = self.closed_clusters[-1]
            price_change = close_price - prev.price_close
            prev.next_price_change = round(price_change, 6)
            prev.next_delta_direction = direction

            neutral_th = self._get_neutral_threshold()

            if abs(price_change) <= neutral_th:
                prev.next_direction = "NEUTRAL"
                prev.outcome = "NEUTRAL"
            elif price_change > 0:
                prev.next_direction = "UP"
                prev.outcome = "BULL"
            else:
                prev.next_direction = "DOWN"
                prev.outcome = "BEAR"

            self._update_pattern_stats(prev)

        # Detecta padrão do cluster recém-fechado
        pattern = self._detect_pattern(snapshot)
        snapshot.pattern = str(pattern["label"])
        snapshot.pattern_confidence = float(pattern["confidence"])

        # contexto
        self._recent_vol.append(float(vol_total))

        # armazena
        self.closed_clusters.append(snapshot)

        # reset próximo cluster
        self._reset_current()

        # ready
        if self.cluster_counter >= self.ready_clusters:
            self.is_ready = True

        if self.print_logs:
            print(
                f"🔒 [CLUSTER #{self.cluster_counter}] "
                f"dir={direction.upper()} | delta={snapshot.delta_final:+.2f} | "
                f"vol={vol_total:.1f} | dur={duration:.1f}s | "
                f"padrão={snapshot.pattern} ({snapshot.pattern_confidence:.0%})"
            )

        return AnalysisResult(
            self.name,
            close_ts,
            close_price,
            snapshot.pattern,
            round(snapshot.pattern_confidence, 3),
            details={
                "cluster_id": self.cluster_counter,
                "delta_final": snapshot.delta_final,
                "delta_direction": direction,
                "duration_s": snapshot.duration_seconds,
                "vol_total": snapshot.vol_total,
                "vol_buy": snapshot.vol_buy,
                "vol_sell": snapshot.vol_sell,
                "tick_count": snapshot.tick_count,
                "ticks_per_sec": snapshot.ticks_per_second,
                "wick_top": snapshot.wick_ratio_top,
                "wick_bot": snapshot.wick_ratio_bot,
                "vol_efficiency": snapshot.vol_efficiency,
                "pattern": pattern,
                "total_clusters": self.cluster_counter,
                "labeled_clusters": sum(1 for c2 in self.closed_clusters if c2.outcome != "PENDENTE"),
                "analyst_signals": analyst_signals,
            },
            description=str(pattern["description"]),
        )

    # ------------------------------------------------------------------ #
    # Detecção de padrões
    # ------------------------------------------------------------------ #
    def _detect_pattern(self, snap: ClusterSnapshot) -> Dict[str, Any]:
        """
        Detecta padrões de mercado baseado no cluster e sinais dos outros analistas.

        Hierarquia:
        1) Exaustão
        2) Confluência
        3) Vácuo
        4) Momentum
        5) Indecisão
        6) Rejeição por wick
        7) Neutro
        """
        abs_sig = snap.absorption_signal or "N/A"
        imb_sig = snap.imbalance_signal or "N/A"
        flow_sig = snap.delta_flow_signal or "N/A"
        exec_sig = snap.execution_signal or "N/A"
        lb_sig = snap.liquidity_break_signal or "N/A"
        direction = snap.delta_direction

        # 1) EXAUSTÃO
        if direction == "buy" and "ABSORCAO_VENDA" in abs_sig.upper():
            return {
                "label": "EXAUSTAO_COMPRADORA",
                "confidence": 0.78,
                "description": (
                    f"⚠️ Cluster fechou comprador (Δ={snap.delta_final:+.2f}) "
                    f"mas absorção vendedora detectada. Institucional absorveu compras."
                ),
            }

        if direction == "sell" and "ABSORCAO_COMPRA" in abs_sig.upper():
            return {
                "label": "EXAUSTAO_VENDEDORA",
                "confidence": 0.78,
                "description": (
                    f"⚠️ Cluster fechou vendedor (Δ={snap.delta_final:+.2f}) "
                    f"mas absorção compradora detectada. Institucional absorveu vendas."
                ),
            }

        # 2) CONFLUÊNCIA
        buy_keywords = ["COMPRA", "COMPRADOR", "DEMANDA", "AGRESSIVO", "BUY", "BULL", "ALTA"]
        sell_keywords = ["VENDA", "VENDEDOR", "OFERTA", "SELL", "BEAR", "BAIXA"]

        all_signals = [abs_sig, imb_sig, flow_sig, exec_sig, lb_sig]

        if direction == "buy":
            aligned = sum(
                1 for s in all_signals
                if any(k in str(s).upper() for k in buy_keywords)
            )
            if aligned >= 3:
                return {
                    "label": "CONFLUENCIA_COMPRADORA",
                    "confidence": min(0.92, 0.68 + aligned * 0.05),
                    "description": (
                        f"✅ {aligned}/{len(all_signals)} analistas confirmam pressão compradora. "
                        f"Δ={snap.delta_final:+.2f} | Vol={snap.vol_total:.1f} | Dur={snap.duration_seconds:.1f}s"
                    ),
                }
            if aligned == 2:
                return {
                    "label": "PRESSAO_COMPRADORA",
                    "confidence": 0.62,
                    "description": (
                        f"↗️ {aligned}/{len(all_signals)} analistas com viés comprador. "
                        f"Δ={snap.delta_final:+.2f} | Vol={snap.vol_total:.1f}"
                    ),
                }

        else:  # sell
            aligned = sum(
                1 for s in all_signals
                if any(k in str(s).upper() for k in sell_keywords)
            )
            if aligned >= 3:
                return {
                    "label": "CONFLUENCIA_VENDEDORA",
                    "confidence": min(0.92, 0.68 + aligned * 0.05),
                    "description": (
                        f"✅ {aligned}/{len(all_signals)} analistas confirmam pressão vendedora. "
                        f"Δ={snap.delta_final:+.2f} | Vol={snap.vol_total:.1f} | Dur={snap.duration_seconds:.1f}s"
                    ),
                }
            if aligned == 2:
                return {
                    "label": "PRESSAO_VENDEDORA",
                    "confidence": 0.62,
                    "description": (
                        f"↘️ {aligned}/{len(all_signals)} analistas com viés vendedor. "
                        f"Δ={snap.delta_final:+.2f} | Vol={snap.vol_total:.1f}"
                    ),
                }

        avg_vol = self._get_avg_volume()

        # 3) VÁCUO
        is_low_volume = avg_vol > 0 and snap.vol_total < avg_vol * self.low_vol_factor
        if is_low_volume and snap.price_range > 0:
            return {
                "label": "VACUO_LIQUIDEZ",
                "confidence": 0.65,
                "description": (
                    f"🕳️ Cluster com volume baixo ({snap.vol_total:.1f} vs média {avg_vol:.1f}). "
                    f"Preço moveu com pouca contraparte — movimento frágil."
                ),
            }

        # 4) MOMENTUM
        is_fast = snap.ticks_per_second > self.fast_ticks_per_sec
        is_high_vol = avg_vol > 0 and snap.vol_total > avg_vol * self.high_vol_factor
        if is_fast and is_high_vol:
            dir_label = "COMPRADOR" if direction == "buy" else "VENDEDOR"
            return {
                "label": f"MOMENTUM_{dir_label}",
                "confidence": min(0.80, 0.60 + (snap.ticks_per_second / 200.0)),
                "description": (
                    f"⚡ Momentum {dir_label.lower()}! "
                    f"{snap.ticks_per_second:.0f} ticks/s | "
                    f"Vol={snap.vol_total:.1f} ({(snap.vol_total/avg_vol):.1f}x média) | "
                    f"Δ={snap.delta_final:+.2f}"
                ),
            }

        # 5) INDECISÃO
        is_slow = snap.duration_seconds > self.slow_cluster_seconds
        is_very_low_vol = avg_vol > 0 and snap.vol_total < avg_vol * self.very_low_vol_factor
        if is_slow and is_very_low_vol:
            return {
                "label": "INDECISAO",
                "confidence": 0.55,
                "description": (
                    f"😐 Cluster lento ({snap.duration_seconds:.0f}s) com volume baixo "
                    f"({snap.vol_total:.1f}). Mercado indeciso."
                ),
            }

        # 6) WICK REJECTION
        has_wick = snap.wick_ratio_top > self.wick_rejection_ratio or snap.wick_ratio_bot > self.wick_rejection_ratio
        if has_wick and is_high_vol:
            if snap.wick_ratio_top > snap.wick_ratio_bot:
                return {
                    "label": "REJEICAO_TOPO",
                    "confidence": 0.70,
                    "description": (
                        f"📌 Wick no TOPO ({snap.wick_ratio_top:.0%} do range) com volume alto. "
                        f"Rejeição institucional — viés bearish."
                    ),
                }
            return {
                "label": "REJEICAO_BASE",
                "confidence": 0.70,
                "description": (
                    f"📌 Wick na BASE ({snap.wick_ratio_bot:.0%} do range) com volume alto. "
                    f"Rejeição institucional — viés bullish."
                ),
            }

        # 7) Fallback
        return {
            "label": "NEUTRO",
            "confidence": 0.50,
            "description": (
                f"Fechamento neutro. Δ={snap.delta_final:+.2f} | Dir={direction.upper()} | "
                f"Vol={snap.vol_total:.1f} | Dur={snap.duration_seconds:.1f}s"
            ),
        }

    # ------------------------------------------------------------------ #
    # Estatísticas e helpers
    # ------------------------------------------------------------------ #
    def _get_avg_volume(self) -> float:
        """Retorna volume médio recente dos clusters fechados."""
        if not self._recent_vol:
            return 0.0
        return sum(self._recent_vol) / len(self._recent_vol)

    def _get_neutral_threshold(self) -> float:
        """
        Threshold para classificar movimento como neutro,
        baseado no range médio recente.
        """
        if len(self.closed_clusters) < 3:
            return self.fallback_neutral_th

        recent_ranges = [
            c.price_range for c in list(self.closed_clusters)[-10:]
            if c.price_range > 0
        ]

        if not recent_ranges:
            return self.fallback_neutral_th

        avg_range = sum(recent_ranges) / len(recent_ranges)
        return max(0.0, avg_range * self.neutral_range_factor)

    def _update_pattern_stats(self, snap: ClusterSnapshot) -> None:
        """
        Atualiza estatísticas por combinação de sinais.
        """
        if snap.outcome == "PENDENTE":
            return

        # Chave mais estável (sem truncar demais)
        key = (
            f"abs={snap.absorption_signal}|"
            f"imb={snap.imbalance_signal}|"
            f"flow={snap.delta_flow_signal}|"
            f"dir={snap.delta_direction}|"
            f"pat={snap.pattern}"
        )

        if key not in self.pattern_stats:
            self.pattern_stats[key] = {
                "bull": 0,
                "bear": 0,
                "neutral": 0,
                "total": 0,
                "pattern": snap.pattern,
            }

        self.pattern_stats[key]["total"] += 1

        if snap.outcome == "BULL":
            self.pattern_stats[key]["bull"] += 1
        elif snap.outcome == "BEAR":
            self.pattern_stats[key]["bear"] += 1
        else:
            self.pattern_stats[key]["neutral"] += 1

    # ------------------------------------------------------------------ #
    # Export / métricas
    # ------------------------------------------------------------------ #
    def export_dataset(self) -> List[Dict[str, Any]]:
        """Exporta apenas clusters rotulados (outcome definido)."""
        return [asdict(c) for c in self.closed_clusters if c.outcome != "PENDENTE"]

    def export_all(self) -> List[Dict[str, Any]]:
        """Exporta todos os clusters, incluindo pendentes."""
        return [asdict(c) for c in self.closed_clusters]

    def save_dataset(self, filepath: str = "clusters_dataset.json") -> int:
        """
        Salva dataset em JSON. Retorna número de clusters salvos.
        """
        dataset = self.export_dataset()
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.exception("Falha ao salvar dataset em %s", filepath)
            raise exc

        if self.print_logs:
            print(f"💾 [CLUSTER_CLOSURE] Dataset salvo: {len(dataset)} clusters → {filepath}")
        return len(dataset)

    def get_pattern_accuracy(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna taxa de acerto por combinação de padrões.
        Inclui apenas combinações com amostra mínima.
        """
        result: Dict[str, Dict[str, Any]] = {}
        for key, stats in self.pattern_stats.items():
            if stats["total"] < self.pattern_stats_min_samples:
                continue

            dominant_count = max(stats["bull"], stats["bear"], stats["neutral"])
            accuracy = dominant_count / stats["total"]

            if stats["bull"] == dominant_count:
                bias = "BULL"
            elif stats["bear"] == dominant_count:
                bias = "BEAR"
            else:
                bias = "NEUTRAL"

            result[key] = {
                "total": stats["total"],
                "bull": stats["bull"],
                "bear": stats["bear"],
                "neutral": stats["neutral"],
                "accuracy": round(accuracy, 3),
                "bias": bias,
                "pattern": stats.get("pattern", "N/A"),
            }

        return dict(sorted(result.items(), key=lambda x: x[1]["accuracy"], reverse=True))

    def get_recent_clusters(self, n: int = 10) -> List[Dict[str, Any]]:
        """Retorna os N clusters mais recentes como dicts."""
        n = max(1, int(n))
        clusters = list(self.closed_clusters)
        return [asdict(c) for c in clusters[-n:]]

    def get_realtime_status(self) -> Dict[str, Any]:
        """Status em tempo real para frontend/painel."""
        labeled = sum(1 for c in self.closed_clusters if c.outcome != "PENDENTE")
        bull = sum(1 for c in self.closed_clusters if c.outcome == "BULL")
        bear = sum(1 for c in self.closed_clusters if c.outcome == "BEAR")

        pattern_counts: Dict[str, int] = {}
        for c in self.closed_clusters:
            pattern_counts[c.pattern] = pattern_counts.get(c.pattern, 0) + 1

        return {
            "status": "active" if self.is_ready else "warmup",
            "symbol": self.symbol,
            "total_clusters": self.cluster_counter,
            "labeled_clusters": labeled,
            "bull_clusters": bull,
            "bear_clusters": bear,
            "avg_volume": round(self._get_avg_volume(), 2),
            "patterns_learned": len(self.pattern_stats),
            "pattern_distribution": pattern_counts,
            "current_cluster": {
                "tick_count": int(self.current["tick_count"]),
                "delta": round(self.current_delta, 4),
                "vol_buy": round(self.current.get("vol_buy", 0.0), 2),
                "vol_sell": round(self.current.get("vol_sell", 0.0), 2),
                "open_price": round(self.current.get("open_price", 0.0), 6),
                "high": round(self.current.get("high", 0.0), 6) if self.current.get("tick_count", 0) > 0 else 0.0,
                "low": round(self.current.get("low", 0.0), 6) if self.current.get("tick_count", 0) > 0 and self.current.get("low") != float("inf") else 0.0,
            },
        }

    def reset(self) -> None:
        """Reset completo do analista."""
        super().reset()
        self.closed_clusters.clear()
        self._recent_vol.clear()
        self.pattern_stats.clear()
        self.cluster_counter = 0
        self._reset_current()
        self.is_ready = False
        if self.print_logs:
            print("🔄 [CLUSTER_CLOSURE] Reset completo")

    def switch_symbol(self, symbol: str) -> None:
        """Atualiza símbolo e reseta estado."""
        self.symbol = str(symbol or "XAUUSD")
        self.reset()
        if self.print_logs:
            print(f"🔄 [CLUSTER_CLOSURE] Símbolo alterado para {self.symbol}")