"""Rate Limiter"""

from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    def is_allowed(self, client_id: str) -> tuple:
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        self.requests[client_id] = [ts for ts in self.requests[client_id] if ts > one_minute_ago]
        
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False, {"remaining": 0}
        
        self.requests[client_id].append(now)
        return True, {"remaining": self.requests_per_minute - len(self.requests[client_id])}
