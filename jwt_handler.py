"""JWT Handler"""

import jwt
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class JWTHandler:
    def __init__(self, secret_key: str = None, expiration_hours: int = 24):
        self.secret_key = secret_key or os.environ.get("JWT_SECRET_KEY", "dev-key")
        self.expiration_hours = expiration_hours

    def create_token(self, user_id: str) -> str:
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=self.expiration_hours),
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> tuple:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return True, payload
        except:
            return False, None
