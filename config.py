# config.py
# ============================================================
# الإعدادات العامة + Redis + bot
# ============================================================

import os
import io
import time
import redis
import telebot

# ============================================================
# الإعدادات الأساسية
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://sec.h42536974.workers.dev")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")
RAILWAY_URL = PUBLIC_URL

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "atmemokhtar2-blip/zxvp")
GITHUB_WORKFLOW_FILE = os.getenv("GITHUB_WORKFLOW_FILE", "build.yml")

ORIGIN_SECRET = os.getenv("ORIGIN_SECRET", "a7f3k9x2m5p8q1w4e6r0t3y7u2i5o8s1")

print(f"[+] Public URL: {PUBLIC_URL}")
print(f"[+] GitHub Repo: {GITHUB_REPO}")
print(f"[+] GitHub Token: {'Set' if GITHUB_TOKEN else 'NOT SET'}")


# ============================================================
# Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

print(f"[+] Redis URL: {REDIS_URL[:45]}...")


def _try_redis(url):
    try:
        client = redis.Redis.from_url(
            url, decode_responses=True,
            socket_timeout=10, socket_connect_timeout=10,
            retry_on_timeout=True, health_check_interval=30,
        )
        client.ping()
        return client
    except Exception as e:
        print(f"[-] Redis try failed: {e}")
        return None


redis_client = _try_redis(REDIS_URL)

if not redis_client and REDIS_URL.startswith("redis://"):
    tls_url = REDIS_URL.replace("redis://", "rediss://", 1)
    redis_client = _try_redis(tls_url)
    if redis_client:
        REDIS_URL = tls_url
        print("[+] TLS connection succeeded!")

if not redis_client and REDIS_URL.startswith("rediss://"):
    non_tls = REDIS_URL.replace("rediss://", "redis://", 1)
    redis_client = _try_redis(non_tls)
    if redis_client:
        REDIS_URL = non_tls
        print("[+] Non-TLS succeeded!")

if redis_client:
    print("[+] config: Redis connected")
else:
    print("[-] config: Redis FAILED")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
