"""
AI Synthesizer — Market Analyst Pro
Sintetiza os sinais dos 6 analistas via LLM (Groq) e gera um sinal unificado
com direção, confiança e descrição legível para o frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("ai_synth")

# ── labels legíveis por classificação ────────────────────────────────────────
_BULL_SIGNALS = {
    "ABSORCAO_COMPRA", "IMBALANCE_COMPRADOR", "DELTA_COMPRADOR_FORTE",
    "PRESSAO_COMPRADORA", "REVERSAO_FLUXO_VENDEDOR",
    "EXECUCAO_AGRESSIVA_COMPRA", "BREAKOUT_REAL", "ABAIXO_VALOR",
    "CONFLUENCIA_COMPRADORA",
}
_BEAR_SIGNALS = {
    "ABSORCAO_VENDA", "IMBALANCE_VENDEDOR", "DELTA_VENDEDOR_FORTE",
    "PRESSAO_VENDEDORA", "REVERSAO_FLUXO_COMPRADOR",
    "EXECUCAO_AGRESSIVA_VENDA", "SWEEP_ALTA", "SWEEP_BAIXA", "ACIMA_VALOR",
    "CONFLUENCIA_VENDEDORA",
}
_NEUTRAL_SIGNALS = {
    "SEM_ABSORCAO", "SEM_IMBALANCE", "DELTA_NEUTRO",
    "EXECUCAO_PASSIVA", "NEUTRO", "SEM_SWEEP", "DENTRO_VALOR",
}


class AISynthesizer:
    """
    Sintetiza os sinais dos 6 analistas.

    Modos:
    - Se GROQ_API_KEY configurada → usa Groq (LLM rápido)
    - Caso contrário → síntese local baseada em regras (sem custo, sem latência)
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self.available = True   # síntese local sempre disponível
        self._groq_enabled = bool(self._api_key)
        self._groq_client: Optional[Any] = None
        self._last_call_ts = 0.0
        self._min_interval = 1.0   # throttle: 1 req/s no máximo

        if self._groq_enabled:
            try:
                from groq import AsyncGroq
                self._groq_client = AsyncGroq(api_key=self._api_key)
                logger.info("AI Synthesizer: Groq LLM enabled")
            except ImportError:
                logger.info("groq package not installed — using rule-based synthesis")
                self._groq_enabled = False
        else:
            logger.info("AI Synthesizer: rule-based mode (set GROQ_API_KEY for LLM)")

    # ─────────────────────────────────────────────────────────────────────────
    # synthesize — entry point público (chamado pelo websocket_server)
    # ─────────────────────────────────────────────────────────────────────────
    async def synthesize(
        self,
        analyst_results: Dict[str, Any],
        price: float,
        symbol: str = "XAUUSD",
    ) -> Dict[str, Any]:
        """
        Retorna sinal unificado:
        {
            direction:   "BULL" | "BEAR" | "NEUTRAL",
            confidence:  0.0–1.0,
            score:       -6 a +6  (votos líquidos),
            description: str,
            analysts_summary: {...},
            source:      "groq" | "rules",
            timestamp:   float,
        }
        """
        try:
            summary = self._build_summary(analyst_results)
            direction, confidence, score = self._vote(summary)

            if self._groq_enabled and self._groq_client:
                now = time.time()
                if now - self._last_call_ts >= self._min_interval:
                    self._last_call_ts = now
                    try:
                        description = await self._groq_describe(
                            summary, direction, confidence, price, symbol
                        )
                        return {
                            "direction":        direction,
                            "confidence":       round(confidence, 3),
                            "score":            score,
                            "description":      description,
                            "analysts_summary": summary,
                            "source":           "groq",
                            "timestamp":        time.time(),
                        }
                    except Exception as exc:
                        logger.debug(f"Groq call failed: {exc} — fallback to rules")

            # rule-based description
            description = self._rule_description(summary, direction, confidence, score, price, symbol)
            return {
                "direction":        direction,
                "confidence":       round(confidence, 3),
                "score":            score,
                "description":      description,
                "analysts_summary": summary,
                "source":           "rules",
                "timestamp":        time.time(),
            }

        except Exception as exc:
            logger.error(f"Synthesize error: {exc}")
            return {
                "direction":   "NEUTRAL",
                "confidence":  0.0,
                "score":       0,
                "description": "Erro na síntese.",
                "source":      "error",
                "timestamp":   time.time(),
            }

    # ─────────────────────────────────────────────────────────────────────────
    # _build_summary
    # ─────────────────────────────────────────────────────────────────────────
    def _build_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai classificação + confiança de cada analista."""
        summary: Dict[str, Any] = {}
        for name, data in results.items():
            if isinstance(data, dict):
                summary[name] = {
                    "signal":     data.get("classification", data.get("signal", "NEUTRO")),
                    "confidence": float(data.get("confidence", 0.5)),
                }
        return summary

    # ─────────────────────────────────────────────────────────────────────────
    # _vote — conta votos bull/bear/neutral
    # ─────────────────────────────────────────────────────────────────────────
    def _vote(self, summary: Dict[str, Any]):
        bull_score = 0.0
        bear_score = 0.0
        n = 0

        for data in summary.values():
            sig  = data.get("signal", "NEUTRO")
            conf = float(data.get("confidence", 0.5))
            n   += 1
            if sig in _BULL_SIGNALS:
                bull_score += conf
            elif sig in _BEAR_SIGNALS:
                bear_score += conf
            # neutral: não contribui

        score = round(bull_score - bear_score, 3)   # positivo = bull

        if n == 0:
            return "NEUTRAL", 0.5, 0

        # normaliza confiança
        total = bull_score + bear_score
        if total < 0.01:
            return "NEUTRAL", 0.5, 0

        if bull_score > bear_score:
            direction  = "BULL"
            confidence = min(0.97, bull_score / total * 0.85 + 0.15)
        elif bear_score > bull_score:
            direction  = "BEAR"
            confidence = min(0.97, bear_score / total * 0.85 + 0.15)
        else:
            direction  = "NEUTRAL"
            confidence = 0.5

        return direction, round(confidence, 3), round(score, 2)

    # ─────────────────────────────────────────────────────────────────────────
    # _rule_description — texto gerado por regras
    # ─────────────────────────────────────────────────────────────────────────
    def _rule_description(
        self,
        summary: Dict[str, Any],
        direction: str,
        confidence: float,
        score: float,
        price: float,
        symbol: str,
    ) -> str:
        bulls = [n for n, d in summary.items() if d.get("signal") in _BULL_SIGNALS]
        bears = [n for n, d in summary.items() if d.get("signal") in _BEAR_SIGNALS]

        name_map = {
            "absorption":     "Absorção",
            "delta_flow":     "Delta",
            "execution":      "Execução",
            "imbalance":      "Imbalance",
            "sweep":          "Sweep",
            "volume_profile": "Volume Profile",
        }

        def fmt(names):
            return ", ".join(name_map.get(n, n) for n in names) if names else "nenhum"

        pct = int(confidence * 100)

        if direction == "BULL":
            return (
                f"📈 SINAL COMPRADOR ({pct}% conf) | {symbol} @ {price:.2f} | "
                f"Analistas Bull: {fmt(bulls)} | Analistas Bear: {fmt(bears)}"
            )
        elif direction == "BEAR":
            return (
                f"📉 SINAL VENDEDOR ({pct}% conf) | {symbol} @ {price:.2f} | "
                f"Analistas Bear: {fmt(bears)} | Analistas Bull: {fmt(bulls)}"
            )
        else:
            return (
                f"➡️ NEUTRO ({pct}% conf) | {symbol} @ {price:.2f} | "
                f"Sem confluência direcional clara."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # _groq_describe — descrição via LLM
    # ─────────────────────────────────────────────────────────────────────────
    async def _groq_describe(
        self,
        summary: Dict[str, Any],
        direction: str,
        confidence: float,
        price: float,
        symbol: str,
    ) -> str:
        signals_text = "\n".join(
            f"  - {name}: {d['signal']} (conf={d['confidence']:.0%})"
            for name, d in summary.items()
        )

        prompt = (
            f"Você é um trader institucional especializado em microestrutura de mercado.\n"
            f"Símbolo: {symbol} | Preço atual: {price:.4f}\n"
            f"Sinais dos analistas:\n{signals_text}\n"
            f"Direção sintetizada: {direction} | Confiança: {confidence:.0%}\n\n"
            f"Em 2 frases curtas e objetivas (máx 120 caracteres cada), descreva:\n"
            f"1) O que o fluxo está indicando agora.\n"
            f"2) O que o trader deve observar.\n"
            f"Responda apenas as 2 frases, sem prefixos ou listas."
        )

        response = await self._groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
