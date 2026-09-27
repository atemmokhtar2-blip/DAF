# redis_cleaner.py
# ============================================================
# تنظيف Redis تلقائياً
# ============================================================

import time
import threading
from config import redis_client


def clean_redis():
    if not redis_client:
        return
    
    try:
        cursor = 0
        cleaned = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="victim_data:*", count=100)
            for key in keys:
                try:
                    redis_client.delete(key)
                    cleaned += 1
                except Exception:
                    pass
            if cursor == 0:
                break
        
        if cleaned > 0:
            print(f"[+] Cleaner: removed {cleaned} victim_data keys")
        
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="victim_cmd:*", count=100)
            for key in keys:
                try:
                    length = redis_client.llen(key)
                    if length > 50:
                        redis_client.ltrim(key, 0, 49)
                except Exception:
                    pass
            if cursor == 0:
                break
        
        print("[+] Cleaner: done")
    except Exception as e:
        print(f"[-] Cleaner error: {e}")


def start_cleaner():
    def loop():
        time.sleep(10)
        while True:
            try:
                clean_redis()
            except Exception as e:
                print(f"[-] Cleaner loop error: {e}")
            time.sleep(300)
    
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("[+] Redis Cleaner started")
