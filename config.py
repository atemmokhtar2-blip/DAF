# config.py
# ============================================================
# الإعدادات العامة + Redis + bot
# ============================================================

import os
import io
import time
import redis
import telebot

from logging_config import get_logger

logger = get_logger("config")

# ============================================================
# [1] الإعدادات الأساسية
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ★★★ الرابط الجديد ★★★
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://sec.h42536974.workers.dev")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-e34a.up.railway.app")

# ملاحظة: PUBLIC_URL هو الرابط الأساسي (Cloudflare Workers)
# RAILWAY_URL هو رابط Railway للـ APK و LSH
# لو PUBLIC_URL موجود، RAILWAY_URL بيبقى هو نفسه

# ★★★ لو عايز كل حاجة تروح على Railway مباشرة ★★★
# استخدم السطر ده:
# RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-e34a.up.railway.app")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "atmemokhtar2-blip/zxvp")
GITHUB_WORKFLOW_FILE = os.getenv("GITHUB_WORKFLOW_FILE", "build.yml")

# ⚠️ ORIGIN_SECRET لازم يكون من الـ ENV في production
ORIGIN_SECRET = os.getenv("ORIGIN_SECRET", "").strip()
if not ORIGIN_SECRET:
    ORIGIN_SECRET = "dev_" + os.urandom(16).hex()
    logger.warning(
        "⚠️ ORIGIN_SECRET not set in ENV - using random dev value"
    )

logger.info(f"Public URL: {PUBLIC_URL}")
logger.info(f"Railway URL: {RAILWAY_URL}")
logger.info(f"GitHub Repo: {GITHUB_REPO}")
logger.info(f"GitHub Token: {'Set' if GITHUB_TOKEN else 'NOT SET'}")

# ============================================================
# [2] Redis — Upstash
# ============================================================
_UPSTASH_FALLBACK = os.getenv(
    "UPSTASH_URL",
    "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379"
)

REDIS_URL = os.getenv("REDIS_URL", "").strip()

if not REDIS_URL:
    logger.warning("⚠️ REDIS_URL not set - using fallback")
    REDIS_URL = _UPSTASH_FALLBACK

if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

if "upstash.io" in REDIS_URL and REDIS_URL.startswith("redis://"):
    REDIS_URL = REDIS_URL.replace("redis://", "rediss://", 1)


def _try_redis(url, name="primary"):
    """محاولة اتصال بـ Redis"""
    try:
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=15,
            socket_connect_timeout=15,
            retry_on_timeout=True,
            health_check_interval=30,
            max_connections=50,
        )
        client.ping()

        try:
            info = client.info("server")
            ver = info.get('redis_version', 'unknown')
            logger.info(f"Redis ({name}) version: {ver}")
        except Exception:
            pass

        return client
    except Exception as e:
        logger.error(f"Redis ({name}) failed: {e}")
        return None


redis_client = _try_redis(REDIS_URL, "primary")

if not redis_client:
    logger.warning("Retrying with Upstash hardcoded fallback...")
    redis_client = _try_redis(_UPSTASH_FALLBACK, "fallback")
    if redis_client:
        REDIS_URL = _UPSTASH_FALLBACK

if redis_client:
    logger.info("✅ config: Redis connected")
else:
    logger.error("❌ config: Redis FAILED")

# ============================================================
# [3] Bot
# ============================================================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing! Set it in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)
logger.info(f"Bot initialized: {BOT_TOKEN[:15]}...{BOT_TOKEN[-5:]}")
