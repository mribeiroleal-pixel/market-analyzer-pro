"""
Feature Engineering — Market Analyst Pro
Extrai 25 features dimensionais dos clusters para treino e inferência ML.
Inclui sinais dos 6 analistas, geometria do cluster e contexto histórico.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("feature_eng")

# ── mapeamento de sinais → score numérico ─────────────────────────────────────
_SIGNAL_SCORE: Dict[str, float] = {
    # Bull +1
    "ABSORCAO_COMPRA":           1.0,
    "IMBALANCE_COMPRADOR":       1.0,
    "DELTA_COMPRADOR_FORTE":     1.0,
    "PRESSAO_COMPRADORA":        0.7,
    "REVERSAO_FLUXO_VENDEDOR":   0.8,
    "EXECUCAO_AGRESSIVA_COMPRA": 0.9,
    "BREAKOUT_REAL":             0.8,
    "ABAIXO_VALOR":              0.6,
    "CONFLUENCIA_COMPRADORA":    1.0,
    # Bear -1
    "ABSORCAO_VENDA":           -1.0,
    "IMBALANCE_VENDEDOR":       -1.0,
    "DELTA_VENDEDOR_FORTE":     -1.0,
    "PRESSAO_VENDEDORA":        -0.7,
    "REVERSAO_FLUXO_COMPRADOR": -0.8,
    "EXECUCAO_AGRESSIVA_VENDA": -0.9,
    "SWEEP_ALTA":               -0.5,
    "SWEEP_BAIXA":              -0.5,
    "ACIMA_VALOR":              -0.6,
    "CONFLUENCIA_VENDEDORA":    -1.0,
    # Neutral 0
    "SEM_ABSORCAO":   0.0,
    "SEM_IMBALANCE":  0.0,
    "DELTA_NEUTRO":   0.0,
    "NEUTRO":         0.0,
    "SEM_SWEEP":      0.0,
    "DENTRO_VALOR":   0.0,
    "EXECUCAO_PASSIVA": -0.1,
}

FEATURE_NAMES = [
    # ── geometria do cluster (8) ─────────────────────────────────────────────
    "delta_sign",          # +1 bull / -1 bear
    "delta_abs_norm",      # |delta| normalizado pelo threshold
    "vol_efficiency",      # price_range / vol_total
    "wick_ratio_top",      # wick topo (rejeição)
    "wick_ratio_bot",      # wick base (rejeição)
    "wick_asymmetry",      # wick_top - wick_bot  (assimetria de rejeição)
    "body_ratio",          # body_vol / total_vol
    "close_position",      # (close-low)/(high-low) — posição do fechamento

    # ── velocidade e tempo (3) ───────────────────────────────────────────────
    "ticks_per_second",    # velocidade bruta
    "duration_log",        # log(duration_seconds+1) — normaliza skew
    "velocity_norm",       # ticks_per_second / media histórica

    # ── sinais dos 6 analistas encodados (6) ─────────────────────────────────
    "absorption_score",    # -1 a +1
    "delta_flow_score",
    "execution_score",
    "imbalance_score",
    "sweep_score",
    "volume_profile_score",

    # ── confluência (3) ──────────────────────────────────────────────────────
    "bull_confluence",     # count de sinais bull (0-6)
    "bear_confluence",     # count de sinais bear (0-6)
    "confluence_net",      # bull - bear normalizado (-1 a +1)

    # ── contexto histórico (3) ───────────────────────────────────────────────
    "prev_outcome_bull",   # cluster anterior foi BULL? (0/1)
    "prev_outcome_bear",   # cluster anterior foi BEAR? (0/1)
    "trend_3",             # direção líquida dos últimos 3 clusters (-1 a +1)

    # ── volume contexto (2) ──────────────────────────────────────────────────
    "vol_total_norm",      # vol_total / media histórica (z-score cap)
    "delta_vol_ratio",     # |delta| / vol_total
]

assert len(FEATURE_NAMES) == 25, f"Expected 25 features, got {len(FEATURE_NAMES)}"


class FeatureExtractor:
    """
    Transforma um cluster dict (ou ClusterRecord) em vetor numpy de 25 features.
    Mantém histórico leve para calcular features contextuais.
    """

    def __init__(self, delta_threshold: float = 100.0) -> None:
        self.delta_threshold = max(delta_threshold, 1.0)
        self._history: List[Dict[str, Any]] = []   # últimos N clusters
        self._max_history = 200

        # estatísticas rolantes (para normalização)
        self._vol_mean   = 1.0
        self._vel_mean   = 1.0

    # ─────────────────────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────────────────────
    def extract_from_cluster(self, cluster: Dict[str, Any]) -> np.ndarray:
        return self._extract(cluster)

    def extract_batch(self, clusters: List[Dict[str, Any]]) -> np.ndarray:
        """Para treino: processa em ordem temporal para features contextuais."""
        self._history.clear()
        rows = []
        for c in clusters:
            rows.append(self._extract(c))
            self._push_history(c)
        return np.array(rows, dtype=np.float32)

    @property
    def feature_names(self) -> List[str]:
        return list(FEATURE_NAMES)

    @property
    def n_features(self) -> int:
        return 25

    # ─────────────────────────────────────────────────────────────────────────
    # _extract
    # ─────────────────────────────────────────────────────────────────────────
    def _extract(self, c: Dict[str, Any]) -> np.ndarray:
        # ── valores base ─────────────────────────────────────────────────────
        delta_final  = _fv(c.get("delta_final", 0.0))
        vol_total    = max(_fv(c.get("vol_total", 1.0)), 1e-6)
        vol_buy      = _fv(c.get("vol_buy", 0.0))
        vol_sell     = _fv(c.get("vol_sell", 0.0))
        price_open   = _fv(c.get("price_open", 0.0))
        price_close  = _fv(c.get("price_close", 0.0))
        price_high   = _fv(c.get("price_high", price_close))
        price_low    = _fv(c.get("price_low",  price_close))
        price_range  = max(price_high - price_low, 1e-8)
        duration     = max(_fv(c.get("duration_seconds", 1.0)), 0.001)
        ticks_ps     = _fv(c.get("ticks_per_second", 0.0))
        wick_top     = min(_fv(c.get("wick_ratio_top", 0.0)), 1.5)
        wick_bot     = min(_fv(c.get("wick_ratio_bot", 0.0)), 1.5)
        vol_eff      = _fv(c.get("vol_efficiency", 0.0))

        # ── geometria ────────────────────────────────────────────────────────
        delta_sign      = 1.0 if delta_final > 0 else (-1.0 if delta_final < 0 else 0.0)
        delta_abs_norm  = min(abs(delta_final) / self.delta_threshold, 3.0)
        body_vol        = min(vol_buy, vol_sell)
        body_ratio      = body_vol / vol_total
        close_pos       = (price_close - price_low) / price_range
        wick_asym       = wick_top - wick_bot
        delta_vol_ratio = min(abs(delta_final) / vol_total, 1.0)

        # ── velocidade ───────────────────────────────────────────────────────
        duration_log  = math.log1p(duration)
        # atualiza media rolante de volume e velocidade
        self._vol_mean = 0.95 * self._vol_mean + 0.05 * vol_total
        self._vel_mean = 0.95 * self._vel_mean + 0.05 * (ticks_ps or 1.0)
        vol_total_norm = _cap(vol_total / max(self._vol_mean, 1e-6), 5.0)
        vel_norm       = _cap(ticks_ps  / max(self._vel_mean, 1e-6), 5.0)

        # ── sinais dos analistas ─────────────────────────────────────────────
        analyst_signals = c.get("analyst_signals") or {}
        ab_score  = _sig_score(analyst_signals, "absorption")
        df_score  = _sig_score(analyst_signals, "delta_flow")
        ex_score  = _sig_score(analyst_signals, "execution")
        im_score  = _sig_score(analyst_signals, "imbalance")
        sw_score  = _sig_score(analyst_signals, "sweep")
        vp_score  = _sig_score(analyst_signals, "volume_profile")

        all_scores = [ab_score, df_score, ex_score, im_score, sw_score, vp_score]
        bull_conf = sum(1 for s in all_scores if s > 0.3)
        bear_conf = sum(1 for s in all_scores if s < -0.3)
        conf_net  = _cap((bull_conf - bear_conf) / 6.0, 1.0)

        # ── contexto histórico ───────────────────────────────────────────────
        prev_bull, prev_bear, trend3 = self._context_features()

        # ── monta vetor ──────────────────────────────────────────────────────
        vec = np.array([
            delta_sign, delta_abs_norm, vol_eff,
            wick_top, wick_bot, wick_asym, body_ratio, close_pos,
            ticks_ps, duration_log, vel_norm,
            ab_score, df_score, ex_score, im_score, sw_score, vp_score,
            float(bull_conf), float(bear_conf), conf_net,
            prev_bull, prev_bear, trend3,
            vol_total_norm, delta_vol_ratio,
        ], dtype=np.float32)

        # sanitiza NaN / Inf
        vec = np.nan_to_num(vec, nan=0.0, posinf=3.0, neginf=-3.0)
        return vec

    # ─────────────────────────────────────────────────────────────────────────
    # contexto histórico
    # ─────────────────────────────────────────────────────────────────────────
    def _context_features(self) -> tuple:
        if not self._history:
            return 0.0, 0.0, 0.0
        prev = self._history[-1]
        outcome = prev.get("outcome", "PENDENTE")
        prev_bull = 1.0 if outcome == "BULL" else 0.0
        prev_bear = 1.0 if outcome == "BEAR" else 0.0

        # trend líquido últimos 3
        recent = self._history[-3:]
        scores = []
        for h in recent:
            out = h.get("outcome", "PENDENTE")
            scores.append(1.0 if out == "BULL" else (-1.0 if out == "BEAR" else 0.0))
        trend3 = sum(scores) / max(len(scores), 1) if scores else 0.0
        return prev_bull, prev_bear, trend3

    def push_cluster(self, cluster: Dict[str, Any]) -> None:
        """Atualiza histórico após cada cluster — chamar em produção."""
        self._push_history(cluster)

    def _push_history(self, cluster: Dict[str, Any]) -> None:
        self._history.append(cluster)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]


# ── helpers ───────────────────────────────────────────────────────────────────
def _fv(v: Any, default: float = 0.0) -> float:
    try:
        r = float(v)
        return r if math.isfinite(r) else default
    except (TypeError, ValueError):
        return default


def _cap(v: float, limit: float) -> float:
    return max(-limit, min(limit, v))


def _sig_score(signals: Dict[str, Any], name: str) -> float:
    """Extrai score -1..+1 do sinal de um analista."""
    data = signals.get(name, {})
    if not isinstance(data, dict):
        return 0.0
    sig  = str(data.get("signal", "NEUTRO"))
    conf = _fv(data.get("confidence", 0.5))
    base = _SIGNAL_SCORE.get(sig, 0.0)
    return _cap(base * conf, 1.0)
