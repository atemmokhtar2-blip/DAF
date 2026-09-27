# rate_limiter.py
# ============================================================
# نظام Rate Limiting للمسارات الحساسة
# ============================================================

import time
import threading
from collections import defaultdict, deque
from functools import wraps
from flask import request, jsonify

from logging_config import get_logger

logger = get_logger("rate_limiter")


# ============================================================
# [1] In-Memory Rate Limiter
# ============================================================
class RateLimiter:
    """
    Rate limiter بسيط في الذاكرة
    بيستخدم sliding window algorithm
    """

    def __init__(self):
        self._requests = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple:
        """
        يتحقق لو الطلب مسموح
        Returns: (allowed: bool, remaining: int, retry_after: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            queue = self._requests[key]

            # شيل الطلبات القديمة
            while queue and queue[0] < window_start:
                queue.popleft()

            current_count = len(queue)

            if current_count >= max_requests:
                # احسب امتى هيسمح تاني
                oldest = queue[0] if queue else now
                retry_after = int(oldest + window_seconds - now) + 1
                return (False, 0, retry_after)

            queue.append(now)
            remaining = max_requests - len(queue)
            return (True, remaining, 0)

    def cleanup(self, max_age_seconds: int = 3600):
        """ينظف الطلبات القديمة"""
        now = time.time()
        cutoff = now - max_age_seconds

        with self._lock:
            empty_keys = []
            for key, queue in self._requests.items():
                while queue and queue[0] < cutoff:
                    queue.popleft()
                if not queue:
                    empty_keys.append(key)

            for key in empty_keys:
                del self._requests[key]


# ============================================================
# [2] Global Instance
# ============================================================
_limiter = RateLimiter()


# ============================================================
# [3] Helper - تحديد الـ Client
# ============================================================
def get_client_key() -> str:
    """يرجع مفتاح فريد للعميل"""
    # Cloudflare
    ip = request.headers.get('CF-Connecting-IP')
    if not ip:
        # X-Forwarded-For
        xff = request.headers.get('X-Forwarded-For', '')
        if xff:
            ip = xff.split(',')[0].strip()
    if not ip:
        ip = request.remote_addr or 'unknown'
    return f"{ip}:{request.path}"


# ============================================================
# [4] Decorator
# ============================================================
def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    per_endpoint: bool = True,
):
    """
    Decorator لتحديد rate limit على route

    Args:
        max_requests: عدد الطلبات المسموح بيها
        window_seconds: في كم ثانية
        per_endpoint: لو True، كل endpoint له حد منفصل
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if per_endpoint:
                key = get_client_key()
            else:
                ip = (
                    request.headers.get('CF-Connecting-IP') or
                    request.remote_addr or
                    'unknown'
                )
                key = ip

            allowed, remaining, retry_after = _limiter.is_allowed(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )

            if not allowed:
                logger.warning(
                    f"🚫 Rate limit exceeded: {key} | "
                    f"retry_after={retry_after}s"
                )
                response = jsonify({
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests",
                    "retry_after": retry_after,
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(retry_after)
                return response

            # ضيف headers مفيدة
            response = func(*args, **kwargs)

            # لو response هو tuple من Flask
            if isinstance(response, tuple):
                return response

            try:
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Limit'] = str(max_requests)
            except Exception:
                pass

            return response

        return wrapper

    return decorator


# ============================================================
# [5] Background Cleanup
# ============================================================
def start_cleanup_thread():
    """يشغل thread لتنظيف الـ limiter كل ساعة"""
    def cleanup_loop():
        while True:
            try:
                time.sleep(3600)  # كل ساعة
                _limiter.cleanup(max_age_seconds=3600)
                logger.debug("🧹 Rate limiter cleaned up")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    logger.info("[+] Rate limiter cleanup thread started")


# ============================================================
# [6] Presets
# ============================================================
# حدود جاهزة للاستخدام

LIMIT_PUBLIC = rate_limit(max_requests=30, window_seconds=60)      # 30/دقيقة
LIMIT_LSH = rate_limit(max_requests=120, window_seconds=60)         # 120/دقيقة (LSH عايز ping كتير)
LIMIT_APK = rate_limit(max_requests=60, window_seconds=60)          # 60/دقيقة
LIMIT_SENSITIVE = rate_limit(max_requests=10, window_seconds=60)    # 10/دقيقة
LIMIT_AUTH = rate_limit(max_requests=5, window_seconds=60)          # 5/دقيقة (للتسجيل)
