"""
Train Outcome — Market Analyst Pro
Script de treino: carrega clusters rotulados do DB, extrai 25 features,
treina XGBoost com split temporal e salva o modelo.

Uso:
    python -m backend.ml.training.train_outcome
    ou via WebSocket: { "type": "train_ml", "symbol": "XAUUSD" }
"""

from __future__ import annotations

import logging
import os
import sys

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-8s] %(name)s — %(message)s",
)
logger = logging.getLogger("train_outcome")

# ── adiciona o backend ao path ───────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "..", "..")
sys.path.insert(0, os.path.abspath(_BACKEND))


def train_and_save(database_url: str, symbol: str = "XAUUSD") -> bool:
    try:
        from database.repository import Database
        from ml.models.outcome_predictor import OutcomePredictor, OUTCOME_MAP
        from ml.features.feature_engineering import FeatureExtractor

        logger.info(f"Connecting to database: {database_url.split('://')[0]}")
        db = Database(database_url)

        # carrega clusters rotulados em ordem cronológica
        labeled = db.get_labeled_clusters(symbol, limit=10_000)
        valid   = [c for c in labeled if c.get("outcome") in ("BULL", "BEAR", "NEUTRAL")]

        logger.info(f"Total labeled clusters for {symbol}: {len(valid)}")

        if len(valid) < 50:
            logger.error(f"Insufficient data: {len(valid)} < 50 labeled clusters")
            return False

        # distribuição de classes
        from collections import Counter
        dist = Counter(c["outcome"] for c in valid)
        logger.info(f"Class distribution: {dict(dist)}")

        # extrai features (em ordem temporal — sem shuffling)
        delta_th  = float(os.environ.get("DELTA_THRESHOLD", "100"))
        extractor = FeatureExtractor(delta_threshold=delta_th)
        X = extractor.extract_batch(valid)
        y = np.array([OUTCOME_MAP[c["outcome"]] for c in valid], dtype=np.int32)

        logger.info(f"Feature matrix: {X.shape} | target: {y.shape}")

        # treina e salva
        predictor = OutcomePredictor()
        if not predictor.train(X, y):
            logger.error("Training failed")
            return False

        if not predictor.save_model():
            logger.error("Failed to save model")
            return False

        info = predictor.get_info()
        logger.info(
            f"Training complete | val_accuracy={info['val_accuracy']:.1%} | "
            f"model={info['model_type']} | saved={info['model_path']}"
        )
        return True

    except Exception as exc:
        logger.error(f"train_and_save error: {exc}", exc_info=True)
        return False


if __name__ == "__main__":
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///market_analyst.db")
    _symbol = os.environ.get("SYMBOL", "XAUUSD")
    logger.info(f"Starting training | symbol={_symbol} | db={_db_url.split('://')[0]}")
    success = train_and_save(_db_url, _symbol)
    sys.exit(0 if success else 1)
