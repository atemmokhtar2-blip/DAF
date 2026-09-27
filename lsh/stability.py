# lsh/stability.py
# ============================================================
# طبقة الاستقرار v6 — Circuit Breaker + Health Monitoring
# ============================================================

import time
import threading

from .config import (
    sessions, sessions_lock, redis_client, LSH_CONFIG,
)
from .session_mgr import (
    get_all_sessions, delete_session, refresh_session_ttl,
    list_live_sessions,
)
from .commands import is_session_active

from logging_config import get_logger

logger = get_logger("lsh.stability")


# ============================================================
# Global
# ============================================================
_stability_stats = {
    "started_at": time.time(),
    "checks": 0,
    "restarts": 0,
    "errors": 0,
    "circuit_breakers": {},
}

_threads = []
_shutdown_flag = threading.Event()


# ============================================================
# Init
# ============================================================
def init_stability(bot=None):
    """بدء خدمات الاستقرار"""
    logger.info("LSH Stability: Initializing...")

    loops = [
        ("session_checker", _session_checker_loop),
        ("redis_monitor", _redis_monitor_loop),
        ("stale_cleaner", _stale_cleaner_loop),
        ("active_refresher", _active_refresher_loop),
        ("stats_reporter", _stats_reporter_loop),
    ]

    for name, target in loops:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        _threads.append(t)
        logger.info(f"LSH Stability: {name} started")

    logger.info("LSH Stability: ✅ All services running")


def shutdown_stability():
    """إيقاف خدمات الاستقرار"""
    logger.info("LSH Stability: Shutting down...")
    _shutdown_flag.set()
    for t in _threads:
        t.join(timeout=2)
    logger.info("LSH Stability: Stopped")


# ============================================================
# Loops
# ============================================================
def _session_checker_loop():
    """فحص الجلسات كل 30 ثانية"""
    while not _shutdown_flag.is_set():
        try:
            _shutdown_flag.wait(LSH_CONFIG["health_check_interval"] / 1000)
            if _shutdown_flag.is_set():
                break
            check_all_sessions()
        except Exception as e:
            logger.exception(f"session_checker error: {e}")
            _stability_stats["errors"] += 1


def _redis_monitor_loop():
    """فحص Redis كل دقيقة"""
    while not _shutdown_flag.is_set():
        try:
            _shutdown_flag.wait(60)
            if _shutdown_flag.is_set():
                break

            import lsh.config as cfg

            if not cfg.redis_client:
                continue

            try:
                cfg.redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis died: {e} - attempting reconnect")
                new_client = cfg._try_redis(cfg.REDIS_URL, "reconnect")
                if new_client:
                    cfg.redis_client = new_client
                    logger.info("Redis reconnected")
                else:
                    _stability_stats["errors"] += 1

        except Exception as e:
            logger.exception(f"redis_monitor error: {e}")


def _stale_cleaner_loop():
    """تنظيف كل 5 دقائق"""
    while not _shutdown_flag.is_set():
        try:
            _shutdown_flag.wait(300)
            if _shutdown_flag.is_set():
                break
            _cleanup_stale()
        except Exception as e:
            logger.exception(f"stale_cleaner error: {e}")


def _active_refresher_loop():
    """تجديد الجلسات النشطة كل دقيقة"""
    while not _shutdown_flag.is_set():
        try:
            _shutdown_flag.wait(60)
            if _shutdown_flag.is_set():
                break
            _refresh_active()
        except Exception as e:
            logger.exception(f"active_refresher error: {e}")


def _stats_reporter_loop():
    """تقرير كل 5 دقائق"""
    while not _shutdown_flag.is_set():
        try:
            _shutdown_flag.wait(300)
            if _shutdown_flag.is_set():
                break

            report = get_stability_report()
            logger.info(
                f"Stability: {report.get('live_sessions', 0)} live | "
                f"{report.get('total_sessions', 0)} total | "
                f"checks={report.get('checks', 0)} | "
                f"errors={report.get('errors', 0)}"
            )
        except Exception as e:
            logger.exception(f"stats_reporter error: {e}")


# ============================================================
# Check
# ============================================================
def check_all_sessions():
    """فحص كل الجلسات"""
    try:
        _stability_stats["checks"] += 1
        all_sessions = get_all_sessions()
        now = time.time()

        alive = 0
        idle = 0
        stale = 0

        with sessions_lock:
            for session in all_sessions:
                last_seen = session.get("last_seen", now)
                idle_time = now - last_seen

                if idle_time < 60:
                    session["stability"] = "stable"
                    session["presence"] = "online"
                    alive += 1
                elif idle_time < 300:
                    session["stability"] = "idle"
                    session["presence"] = "idle"
                    idle += 1
                elif idle_time < 1800:
                    session["stability"] = "slow"
                    session["presence"] = "away"
                    stale += 1
                else:
                    session["stability"] = "stale"
                    session["presence"] = "offline"
                    stale += 1

        return {
            "alive": alive,
            "idle": idle,
            "stale": stale,
            "total": len(all_sessions)
        }

    except Exception as e:
        logger.exception(f"check_all_sessions error: {e}")
        return {"alive": 0, "idle": 0, "stale": 0, "total": 0}


# ============================================================
# Cleanup
# ============================================================
def _cleanup_stale():
    """حذف الجلسات الميتة"""
    try:
        now = time.time()
        to_delete = []

        with sessions_lock:
            for sid, sess in list(sessions.items()):
                last_seen = sess.get("last_seen", now)
                if now - last_seen > LSH_CONFIG["session_max_idle"]:
                    to_delete.append(sid)

        for sid in to_delete:
            try:
                delete_session(sid)
                logger.info(f"Stability: deleted stale {sid[:8]}")
            except Exception as e:
                logger.warning(f"Delete stale error for {sid[:8]}: {e}")

        if to_delete:
            _stability_stats["restarts"] += len(to_delete)

    except Exception as e:
        logger.exception(f"_cleanup_stale error: {e}")


# ============================================================
# Refresh
# ============================================================
def _refresh_active():
    """تجديد الجلسات النشطة في Redis"""
    try:
        live = list_live_sessions()
        for session in live:
            sid = session.get("session_id")
            if sid and is_session_active(sid):
                refresh_session_ttl(sid)
    except Exception as e:
        logger.exception(f"_refresh_active error: {e}")


# ============================================================
# Report
# ============================================================
def get_stability_report():
    """تقرير الحالة"""
    try:
        all_sessions = get_all_sessions()
        live = [
            s for s in all_sessions
            if time.time() - s.get("last_seen", 0) < 60
        ]

        return {
            "started_at": _stability_stats["started_at"],
            "uptime": time.time() - _stability_stats["started_at"],
            "checks": _stability_stats["checks"],
            "restarts": _stability_stats["restarts"],
            "errors": _stability_stats["errors"],
            "total_sessions": len(all_sessions),
            "live_sessions": len(live),
            "redis_connected": bool(redis_client),
        }

    except Exception as e:
        logger.exception(f"get_stability_report error: {e}")
        return {}
