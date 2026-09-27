# monitoring.py
# ============================================================
# نظام Monitoring مركزي
# ============================================================

import os
import time
import threading
import psutil  # لو مش موجود: pip install psutil
from datetime import datetime
from collections import deque

from flask import Blueprint, jsonify, request

from logging_config import get_logger

logger = get_logger("monitoring")

# ============================================================
# [1] Metrics Store
# ============================================================
class MetricsStore:
    """يخزن الـ metrics في الذاكرة"""

    def __init__(self, max_size=1000):
        self._lock = threading.Lock()
        self._counters = {}
        self._gauges = {}
        self._timings = {}
        self._events = deque(maxlen=max_size)
        self._start_time = time.time()

    def inc_counter(self, name: str, value: int = 1, tags: dict = None):
        """زيادة عداد"""
        key = self._make_key(name, tags)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value

    def set_gauge(self, name: str, value, tags: dict = None):
        """تعيين قيمة حالية"""
        key = self._make_key(name, tags)
        with self._lock:
            self._gauges[key] = value

    def observe_timing(self, name: str, duration_ms: float, tags: dict = None):
        """تسجيل وقت تنفيذ"""
        key = self._make_key(name, tags)
        with self._lock:
            if key not in self._timings:
                self._timings[key] = deque(maxlen=100)
            self._timings[key].append(duration_ms)

    def log_event(self, event_type: str, data: dict = None):
        """تسجيل حدث"""
        with self._lock:
            self._events.append({
                "type": event_type,
                "data": data or {},
                "timestamp": time.time(),
            })

    def _make_key(self, name: str, tags: dict) -> str:
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def snapshot(self) -> dict:
        """يرجع صورة كاملة للـ metrics"""
        with self._lock:
            timings_summary = {}
            for key, values in self._timings.items():
                if values:
                    sorted_v = sorted(values)
                    n = len(sorted_v)
                    timings_summary[key] = {
                        "count": n,
                        "min_ms": round(sorted_v[0], 2),
                        "max_ms": round(sorted_v[-1], 2),
                        "avg_ms": round(sum(sorted_v) / n, 2),
                        "p50_ms": round(sorted_v[n // 2], 2),
                        "p95_ms": round(sorted_v[int(n * 0.95)], 2),
                        "p99_ms": round(sorted_v[int(n * 0.99)], 2),
                    }

            return {
                "uptime_seconds": round(time.time() - self._start_time, 2),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timings": timings_summary,
                "recent_events": list(self._events)[-50:],
            }


# ============================================================
# [2] Global Instance
# ============================================================
metrics = MetricsStore()


# ============================================================
# [3] System Stats
# ============================================================
def get_system_stats() -> dict:
    """يرجع إحصائيات النظام"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu": {
                "percent": cpu_percent,
                "cores": psutil.cpu_count(),
            },
            "memory": {
                "total_mb": round(memory.total / 1024 / 1024, 2),
                "used_mb": round(memory.used / 1024 / 1024, 2),
                "available_mb": round(memory.available / 1024 / 1024, 2),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "percent": disk.percent,
            },
            "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None,
        }
    except Exception as e:
        logger.error(f"system stats error: {e}")
        return {}


# ============================================================
# [4] Blueprint Routes
# ============================================================
monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/_metrics', methods=['GET'])
def metrics_endpoint():
    """Endpoint بيرجع كل الـ metrics"""
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "system": get_system_stats(),
        "metrics": metrics.snapshot(),
    }), 200


@monitoring_bp.route('/_health', methods=['GET'])
def health_endpoint():
    """Health check شامل"""
    from config import redis_client

    checks = {
        "redis": False,
        "bot": False,
    }

    # Redis check
    try:
        if redis_client:
            redis_client.ping()
            checks["redis"] = True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")

    # Bot check
    try:
        from config import bot
        if bot:
            checks["bot"] = True
    except Exception:
        pass

    all_ok = all(checks.values())

    return jsonify({
        "status": "healthy" if all_ok else "degraded",
        "timestamp": time.time(),
        "checks": checks,
    }), 200 if all_ok else 503


@monitoring_bp.route('/_version', methods=['GET'])
def version_endpoint():
    """معلومات النسخة"""
    return jsonify({
        "name": "DAF Bot Controller",
        "version": "6.0.0",
        "build_date": "2025-01-01",
        "python_version": os.sys.version,
    }), 200


# ============================================================
# [5] Periodic Reporter
# ============================================================
def start_metrics_reporter(interval_seconds: int = 300):
    """يطبع تقرير كل فترة"""

    def report_loop():
        while True:
            try:
                time.sleep(interval_seconds)
                snap = metrics.snapshot()
                sys_stats = get_system_stats()

                logger.info(
                    f"📊 Metrics | "
                    f"uptime={snap['uptime_seconds']:.0f}s | "
                    f"CPU={sys_stats.get('cpu', {}).get('percent', 0)}% | "
                    f"RAM={sys_stats.get('memory', {}).get('percent', 0)}% | "
                    f"counters={len(snap['counters'])}"
                )
            except Exception as e:
                logger.error(f"metrics reporter error: {e}")

    thread = threading.Thread(target=report_loop, daemon=True)
    thread.start()
    logger.info(f"[+] Metrics reporter started (interval={interval_seconds}s)")


# ============================================================
# [6] Init Function
# ============================================================
def init_monitoring(app):
    """يسجل الـ blueprint + يشغل الـ reporter"""
    app.register_blueprint(monitoring_bp)
    logger.info("[+] Monitoring routes registered: /_metrics /_health /_version")

    start_metrics_reporter(interval_seconds=300)


# ============================================================
# [7] Helper Decorators
# ============================================================
def track_request(endpoint_name: str):
    """Decorator يتابع الـ requests"""
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start) * 1000

                metrics.inc_counter(
                    "requests_total",
                    tags={"endpoint": endpoint_name, "status": "ok"}
                )
                metrics.observe_timing(
                    "request_duration_ms",
                    elapsed,
                    tags={"endpoint": endpoint_name}
                )
                return result
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                metrics.inc_counter(
                    "requests_total",
                    tags={"endpoint": endpoint_name, "status": "error"}
                )
                metrics.log_event("request_error", {
                    "endpoint": endpoint_name,
                    "error": str(e)[:200],
                    "duration_ms": elapsed,
                })
                raise

        return wrapper
    return decorator
