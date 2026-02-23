"""
Outcome Predictor — Market Analyst Pro
XGBoost multiclass (BULL / BEAR / NEUTRAL) com split temporal
e serialização/deserialização de modelo.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("outcome_pred")

OUTCOME_MAP   = {"NEUTRAL": 0, "BULL": 1, "BEAR": 2}
OUTCOME_NAMES = {v: k for k, v in OUTCOME_MAP.items()}
MODEL_FILE    = os.environ.get("ML_MODELS_DIR", "models") + "/outcome_predictor.pkl"


class OutcomePredictor:
    """
    Classificador XGBoost para prever o outcome do próximo cluster.
    Fallback para GradientBoosting do sklearn se xgboost não instalado.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path  = model_path or MODEL_FILE
        self.model       = None
        self.scaler      = None
        self.is_trained  = False
        self._n_features = 25
        self._train_size = 0
        self._val_accuracy: float = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # train
    # ─────────────────────────────────────────────────────────────────────────
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        """
        Treina com split temporal 80/20 — sem data leakage.
        X: (N, 25) float32 | y: (N,) int {0,1,2}
        """
        if len(X) < 50:
            logger.error(f"Insufficient samples: {len(X)} < 50")
            return False

        try:
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import accuracy_score

            # split temporal (nunca aleatório — evita lookahead)
            split = int(len(X) * 0.8)
            X_train, X_val = X[:split], X[split:]
            y_train, y_val = y[:split], y[split:]

            # normalização
            scaler = StandardScaler()
            X_train_sc = scaler.fit_transform(X_train)
            X_val_sc   = scaler.transform(X_val)

            # tenta XGBoost, cai para GradientBoosting
            model = _build_model(len(X_train))
            model.fit(X_train_sc, y_train)

            # avaliação
            y_pred = model.predict(X_val_sc)
            acc = accuracy_score(y_val, y_pred)

            self.model      = model
            self.scaler     = scaler
            self.is_trained = True
            self._train_size = len(X_train)
            self._val_accuracy = float(acc)

            logger.info(
                f"OutcomePredictor trained | samples={len(X)} | "
                f"val_acc={acc:.1%} | split={split}/{len(X)-split}"
            )
            return True

        except Exception as exc:
            logger.error(f"Training error: {exc}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # predict
    # ─────────────────────────────────────────────────────────────────────────
    def predict(self, x: np.ndarray) -> Tuple[str, float]:
        """
        x: (25,) float32 vetor de features de um cluster.
        Retorna (outcome_str, confidence).
        """
        if not self.is_trained or self.model is None:
            return "NEUTRAL", 0.5

        try:
            if x.ndim == 1:
                x = x.reshape(1, -1)
            x_sc  = self.scaler.transform(x)
            pred  = int(self.model.predict(x_sc)[0])
            proba = self.model.predict_proba(x_sc)[0]
            outcome    = OUTCOME_NAMES.get(pred, "NEUTRAL")
            confidence = float(proba[pred])
            return outcome, round(confidence, 3)
        except Exception as exc:
            logger.debug(f"Predict error: {exc}")
            return "NEUTRAL", 0.5

    # ─────────────────────────────────────────────────────────────────────────
    # save / load
    # ─────────────────────────────────────────────────────────────────────────
    def save_model(self) -> bool:
        if not self.is_trained:
            return False
        try:
            import pickle
            os.makedirs(os.path.dirname(self.model_path) or ".", exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump({"model": self.model, "scaler": self.scaler,
                             "train_size": self._train_size,
                             "val_accuracy": self._val_accuracy}, f)
            logger.info(f"Model saved: {self.model_path}")
            return True
        except Exception as exc:
            logger.error(f"Save error: {exc}")
            return False

    def load_model(self) -> bool:
        try:
            import pickle
            if not os.path.exists(self.model_path):
                logger.info(f"No model file at {self.model_path}")
                return False
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self.model         = data["model"]
            self.scaler        = data["scaler"]
            self._train_size   = data.get("train_size", 0)
            self._val_accuracy = data.get("val_accuracy", 0.0)
            self.is_trained    = True
            logger.info(
                f"Model loaded: {self.model_path} | "
                f"train_size={self._train_size} | val_acc={self._val_accuracy:.1%}"
            )
            return True
        except Exception as exc:
            logger.error(f"Load error: {exc}")
            return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "is_trained":    self.is_trained,
            "train_size":    self._train_size,
            "val_accuracy":  self._val_accuracy,
            "model_path":    self.model_path,
            "model_type":    type(self.model).__name__ if self.model else "none",
        }


# ── factory de modelo ─────────────────────────────────────────────────────────
def _build_model(n_samples: int) -> Any:
    """Tenta XGBoost, fallback para GradientBoosting."""
    try:
        import xgboost as xgb
        n_est = min(300, max(50, n_samples // 10))
        return xgb.XGBClassifier(
            n_estimators=n_est,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1,
        )
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.multiclass import OneVsRestClassifier
        n_est = min(200, max(50, n_samples // 15))
        logger.info("xgboost not available — using GradientBoostingClassifier")
        return OneVsRestClassifier(
            GradientBoostingClassifier(n_estimators=n_est, max_depth=4, random_state=42)
        )
