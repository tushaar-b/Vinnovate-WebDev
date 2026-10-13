import redis
from app.config import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=3,
    socket_connect_timeout=3,
)


def check_redis_connection() -> bool:
    """Verifies that Redis is reachable and responds to PING."""
    try:
        return bool(redis_client.ping())
    except Exception:
        return False
