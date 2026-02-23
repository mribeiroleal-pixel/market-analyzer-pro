"""ML Config"""

import os

class MLConfig:
    MODELS_DIR = os.environ.get("ML_MODELS_DIR", "models")
    DATA_DIR = os.environ.get("ML_DATA_DIR", "data")
    OUTCOME_ENABLED = os.environ.get("ML_OUTCOME_ENABLED", "False") == "True"
    PATTERN_ENABLED = os.environ.get("ML_PATTERN_ENABLED", "False") == "True"

ml_config = MLConfig()
