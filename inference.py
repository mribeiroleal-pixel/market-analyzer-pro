"""
ML Inference Pipeline — Market Analyst Pro
Carrega o modelo treinado e faz predição em tempo real para cada cluster fechado.
Conecta FeatureExtractor → OutcomePredictor.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("ml_inference")


class MLInferencePipeline:
    """
    Interface única para inferência ML em produção.
    Chamada pelo websocket_server a cada cluster fechado.
    """

    def __init__(self) -> None:
        self._predictor = None
        self._extractor = None
        self._loaded    = False

    # ─────────────────────────────────────────────────────────────────────────
    # load — tenta carregar modelo em disco
    # ─────────────────────────────────────────────────────────────────────────
    def load(self) -> bool:
        try:
            from ml.models.outcome_predictor import OutcomePredictor
            from ml.features.feature_engineering import FeatureExtractor

            delta_threshold = float(os.environ.get("DELTA_THRESHOLD", "100"))
            self._extractor = FeatureExtractor(delta_threshold=delta_threshold)
            self._predictor = OutcomePredictor()
            self._loaded    = self._predictor.load_model()

            if self._loaded:
                logger.info(f"ML pipeline loaded | {self._predictor.get_info()}")
            else:
                logger.info("ML pipeline ready — no model yet (train first)")
            return True

        except Exception as exc:
            logger.warning(f"ML pipeline load error: {exc}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # predict — inferência em um cluster
    # ─────────────────────────────────────────────────────────────────────────
    def predict(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        """
        cluster: dict com todos os campos do cluster fechado.
        Retorna:
        {
            success: bool,
            outcome: "BULL" | "BEAR" | "NEUTRAL",
            confidence: float,
            features_used: int,
        }
        """
        if not self._loaded or self._predictor is None or self._extractor is None:
            return {"success": False, "outcome": "NEUTRAL", "confidence": 0.5, "features_used": 0}

        try:
            x = self._extractor.extract_from_cluster(cluster)
            outcome, confidence = self._predictor.predict(x)

            # atualiza histórico do extractor para próxima predição
            self._extractor.push_cluster({**cluster, "ml_outcome": outcome})

            return {
                "success":       True,
                "outcome":       outcome,
                "confidence":    confidence,
                "features_used": int(x.shape[0]),
            }

        except Exception as exc:
            logger.debug(f"Inference error: {exc}")
            return {"success": False, "outcome": "NEUTRAL", "confidence": 0.5, "features_used": 0}

    # ─────────────────────────────────────────────────────────────────────────
    # helpers
    # ─────────────────────────────────────────────────────────────────────────
    def is_ready(self) -> bool:
        return self._loaded and self._predictor is not None and self._predictor.is_trained

    def get_status(self) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "pipeline_active": self._loaded,
            "model_ready":     self.is_ready(),
        }
        if self._predictor:
            base.update(self._predictor.get_info())
        return base

    def reload(self) -> bool:
        """Recarrega modelo após retreino."""
        if self._predictor:
            self._loaded = self._predictor.load_model()
            if self._loaded:
                logger.info("ML pipeline reloaded")
        return self._loaded


# instância global (usada como singleton no websocket_server)
ml_pipeline = MLInferencePipeline()
