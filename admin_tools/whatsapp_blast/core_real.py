# admin_tools/whatsapp_blast/core_real.py
# ============================================================
# WhatsApp Blast — Real Worker Client
# ============================================================

import os
import json
import time
import requests
import threading
from datetime import datetime

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("admin_tools.whatsapp_blast.core_real")


# ─── Worker Config ───
WORKER_URL = os.getenv("WA_WORKER_URL", "").strip()
WORKER_SECRET = os.getenv("WA_WORKER_SECRET", "").strip()


def _worker_headers():
    return {
        "X-Worker-Secret": WORKER_SECRET,
        "Content-Type": "application/json"
    }


def _worker_request(method, path, data=None, timeout=30):
    """HTTP request to worker"""
    if not WORKER_URL:
        return {"error": "WORKER_URL not configured"}

    url = f"{WORKER_URL.rstrip('/')}{path}"

    try:
        if method == "GET":
            r = requests.get(url, headers=_worker_headers(), timeout=timeout)
        else:
            r = requests.post(url, headers=_worker_headers(), json=data, timeout=timeout)

        if r.status_code >= 400:
            return {"error": f"HTTP {r.status_code}", "body": r.text[:500]}

        return r.json()

    except Exception as e:
        logger.exception(f"Worker request failed: {e}")
        return {"error": str(e)}


# ============================================================
# Public API
# ============================================================
def worker_health():
    """فحص الاتصال بالـ worker"""
    return _worker_request("GET", "/health", timeout=10)


def worker_init(session_name="default"):
    """يفعّل الجلسة"""
    return _worker_request("POST", "/init", {"session_name": session_name}, timeout=120)


def worker_get_qr():
    """يرجع الـ QR الحالي"""
    return _worker_request("GET", "/qr", timeout=15)


def worker_get_contacts():
    """يرجع كل جهات الاتصال"""
    return _worker_request("GET", "/contacts", timeout=60)


def worker_send_message(to, message):
    """يبعت رسالة واحدة"""
    return _worker_request("POST", "/send", {"to": to, "message": message})


def worker_send_file(to, file_url, filename=None, caption=None):
    """يبعت ملف"""
    return _worker_request("POST", "/send_file", {
        "to": to,
        "file_url": file_url,
        "filename": filename,
        "caption": caption
    }, timeout=60)


def worker_bulk_blast(contacts, message=None, file_url=None,
                       filename=None, caption=None,
                       delay_min=3000, delay_max=8000,
                       session_id=None):
    """يبعت لعشرات/مئات"""
    return _worker_request("POST", "/blast", {
        "contacts": contacts,
        "message": message,
        "file_url": file_url,
        "filename": filename,
        "caption": caption,
        "delay_min": delay_min,
        "delay_max": delay_max,
        "session_id": session_id
    }, timeout=30)


def worker_blast_status(blast_id):
    """حالة الإرسال"""
    return _worker_request("GET", f"/blast/{blast_id}", timeout=15)


def worker_stop_blast(blast_id):
    """يوقف الإرسال"""
    return _worker_request("POST", f"/blast/{blast_id}/stop")


def worker_logout():
    """تسجيل خروج"""
    return _worker_request("POST", "/logout", timeout=30)


# ============================================================
# Session State Manager
# ============================================================
_sessions = {}
_sessions_lock = threading.Lock()


class RealBlastSession:
    def __init__(self, session_id, admin_id):
        self.session_id = session_id
        self.admin_id = admin_id
        self.created_at = time.time()
        self.status = "waiting_qr"
        self.whatsapp_number = None
        self.contacts = []
        self.blast_id = None
        self.sent = 0
        self.failed = 0
        self.payload_url = None
        self.message_text = None
        self.log = []

    def add_log(self, msg):
        entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-200:]
        logger.info(f"[RealBlast {self.session_id}] {msg}")

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "admin_id": self.admin_id,
            "status": self.status,
            "whatsapp_number": self.whatsapp_number,
            "contacts_count": len(self.contacts),
            "blast_id": self.blast_id,
            "sent": self.sent,
            "failed": self.failed,
            "payload_url": self.payload_url,
            "message_text": (self.message_text or "")[:100],
            "created_at_str": datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "log": self.log[-15:]
        }


def create_real_session(admin_id):
    import uuid
    session_id = uuid.uuid4().hex[:12]
    with _sessions_lock:
        s = RealBlastSession(session_id, admin_id)
        _sessions[session_id] = s
    s.add_log("✅ Session created")
    return s


def get_real_session(session_id):
    with _sessions_lock:
        return _sessions.get(session_id)


def get_admin_real_sessions(admin_id):
    with _sessions_lock:
        return [s for s in _sessions.values() if s.admin_id == admin_id]


def delete_real_session(session_id):
    with _sessions_lock:
        if session_id in _sessions:
            del _sessions[session_id]
            return True
    return False
