# logging_config.py
# ============================================================
# نظام Logging مركزي لكل المكونات
# ============================================================

import os
import sys
import logging
import logging.handlers
from datetime import datetime

# ============================================================
# [1] الإعدادات
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))  # 10MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"

# ============================================================
# [2] إنشاء مجلد الـ logs
# ============================================================
if LOG_TO_FILE:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        print(f"[-] Failed to create log dir: {e}")
        LOG_TO_FILE = False

# ============================================================
# [3] Formatters
# ============================================================
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
FILE_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)-20s | "
    "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

console_formatter = logging.Formatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT)
file_formatter = logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT)

# ============================================================
# [4] Handlers
# ============================================================
handlers = []

if LOG_TO_CONSOLE:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

if LOG_TO_FILE:
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(LOG_DIR, "bot.log"),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

        error_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(LOG_DIR, "errors.log"),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        error_handler.setFormatter(file_formatter)
        error_handler.setLevel(logging.ERROR)
        handlers.append(error_handler)
    except Exception as e:
        print(f"[-] Failed to setup file logging: {e}")

# ============================================================
# [5] إعداد الـ Root Logger
# ============================================================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=handlers,
    force=True,
)

# ============================================================
# [6] تقليل ضوضاء مكتبات خارجية
# ============================================================
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("telebot").setLevel(logging.INFO)
logging.getLogger("redis").setLevel(logging.WARNING)

# ============================================================
# [7] دوال مساعدة
# ============================================================
def get_logger(name: str) -> logging.Logger:
    """يرجع logger باسم معين"""
    return logging.getLogger(name)


def log_startup_info():
    """يطبع معلومات البداية"""
    logger = get_logger("startup")
    logger.info("=" * 60)
    logger.info("🚀 Starting DAF Bot Controller")
    logger.info(f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📊 Log level: {LOG_LEVEL}")
    logger.info(f"📁 Log dir: {LOG_DIR if LOG_TO_FILE else 'disabled'}")
    logger.info("=" * 60)


def log_shutdown_info():
    """يطبع معلومات الإغلاق"""
    logger = get_logger("shutdown")
    logger.info("=" * 60)
    logger.info("🛑 Shutting down DAF Bot Controller")
    logger.info("=" * 60)


# ============================================================
# [8] Exception Hook
# ============================================================
def setup_exception_hook():
    """يلتقط أي exception غير معالج ويسجله"""
    logger = get_logger("uncaught")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception


# ============================================================
# [9] Decorator للـ Timing
# ============================================================
def log_execution_time(func):
    """Decorator يقيس وقت تنفيذ الدالة"""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            if elapsed > 1.0:  # لو خدت أكتر من ثانية
                logger.warning(
                    f"⚠️ {func.__name__} took {elapsed:.2f}s"
                )
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(
                f"❌ {func.__name__} failed after {elapsed:.2f}s: {e}"
            )
            raise

    return wrapper
