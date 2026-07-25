"""
Redis helpers: caching + rate limiting. Plain functions, sync redis client.

Interview points:
- Cache-aside pattern: check cache first, on miss compute + store with TTL.
- Rate limiting with a fixed window counter: INCR + EXPIRE. Simple to
  explain. Mention: "a sliding window or token bucket is more accurate,
  fixed window can allow bursts at window boundaries" -- knowing the
  limitation is what impresses interviewers.
"""

import os
import json
import redis

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,  # get strings back instead of bytes
)

CACHE_TTL_SECONDS = 300  # 5 minutes


def cache_get(key):
    value = r.get(key)
    if value is None:
        return None
    return json.loads(value)


def cache_set(key, value, ttl=CACHE_TTL_SECONDS):
    r.set(key, json.dumps(value), ex=ttl)


def is_rate_limited(client_id, limit=20, window_seconds=60):
    """
    Fixed window rate limiter.
    Returns True if the client has exceeded `limit` requests in the window.
    """
    key = f"ratelimit:{client_id}"
    current = r.incr(key)          # atomic increment
    if current == 1:
        r.expire(key, window_seconds)  # start the window on first request
    return current > limit
