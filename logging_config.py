"""Logging Configuration"""

import logging
import os

def setup_logging(log_dir="logs", log_level=None):
    if log_level is None:
        log_level = os.environ.get("LOG_LEVEL", "INFO")
    
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='[%(asctime)s] [%(levelname)-8s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "backend.log"), encoding='utf-8')
        ]
    )
