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
# ★★★ Redis — Upstash (Fixed) ★★★
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()

# ★ لو مفيش REDIS_URL، استخدم Upstash hardcoded
if not REDIS_URL:
    REDIS_URL = "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379"

# ★ لو لسه فيه رابط قديم Insect/Outsize → استبدله بـ Upstash
if "insect-outsize-shirt" in REDIS_URL or "insect" in REDIS_URL:
    print(f"[!] OLD Redis detected! Switching to Upstash...")
    REDIS_URL = "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379"

if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

# ★ Upstash إجباري TLS
if "upstash.io" in REDIS_URL and REDIS_URL.startswith("redis://"):
    REDIS_URL = REDIS_URL.replace("redis://", "rediss://", 1)

print(f"[+] Redis URL (masked): {REDIS_URL[:30]}...{REDIS_URL[-30:]}")
print(f"[+] Redis host: {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else 'unknown'}")


def _try_redis(url):
    try:
        client = redis.Redis.from_url(
            url, decode_responses=True,
            socket_timeout=15, socket_connect_timeout=15,
            retry_on_timeout=True, health_check_interval=30,
            ssl_cert_reqs=None,
        )
        client.ping()
        # ★ اختبار info
        try:
            info = client.info("server")
            print(f"[+] Redis version: {info.get('redis_version', 'unknown')}")
        except Exception:
            pass
        return client
    except Exception as e:
        print(f"[-] Redis try failed: {e}")
        return None


redis_client = _try_redis(REDIS_URL)

# fallback
if not redis_client:
    fallbacks = [
        "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379",
    ]
    for fb_url in fallbacks:
        redis_client = _try_redis(fb_url)
        if redis_client:
            REDIS_URL = fb_url
            print(f"[+] Fallback worked!")
            break

if redis_client:
    print("[+] config: ✅ Redis connected to Upstash")
    print(f"[+] config: Using: {REDIS_URL.split('@')[-1]}")
else:
    print("[-] config: ❌ Redis FAILED — check Upstash URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
