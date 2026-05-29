import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from app.settings import settings

logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


async def get_cache(key: str) -> Optional[Any]:
    raw = await redis_client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Cache decode failed for key %s", key)
        return None


async def set_cache(key: str, value: Any, ttl: int = 3600) -> None:
    await redis_client.set(key, json.dumps(value), ex=ttl)
