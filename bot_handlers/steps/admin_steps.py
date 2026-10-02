# bot_handlers/steps/admin_steps.py
# ============================================================
# Steps الخاصة بالأدمن (رسائل نصية)
# ============================================================

import time

from config import bot
from imports_manager import (
    is_admin,
    get_all_users, get_user,
    get_or_create_user, save_user,
    ban_user, unban_user, delete_user,
    build_user_info_text, build_user_detail_keyboard,
)
from logging_config import get_logger

from ..helpers import h

logger = get_logger("bot_handlers.steps.admin")


def admin_search_handler(message):
    if not is_admin(message.chat.id):
        return

    query = (message.text or "").strip().lstrip("@")
    users = get_all_users()

    found = [
        u for u in users
        if str(u.get("user_id")) == query
        or (u.get("username", "") or "").lower() == query.lower()
    ]

    if not found:
        bot.send_message(
            message.chat.id,
            f"❌ لم يُعثر على: <code>{h(query)}</code>",
            parse_mode="HTML"
        )
        return

    for u in found:
        uid = u.get("user_id")
        bot.send_message(
            message.chat.id,
            build_user_info_text(uid, u),
            reply_markup=build_user_detail_keyboard(uid, u),
            parse_mode="HTML"
        )


def admin_broadcast_handler(message):
    if not is_admin(message.chat.id):
        return

    text = message.text
    if not text:
        return

    users = get_all_users()
    success = failed = 0

    status_msg = bot.send_message(
        message.chat.id,
        f"📢 جاري الإرسال لـ {len(users)}..."
    )

    for u in users:
        uid = u.get("user_id")
        if u.get("is_banned"):
            continue
        try:
            bot.send_message(
                uid,
                f"📢 <b>رسالة من الإدارة:</b>\n\n{h(text)}",
                parse_mode="HTML"
            )
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    try:
        bot.edit_message_text(
            f"✅ <b>تم!</b>\n✔️ {success}\n❌ {failed}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            parse_mode="HTML"
        )
    except Exception:
        pass


def admin_ban_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    ban_user(uid)
    bot.send_message(message.chat.id, f"🚫 تم حظر <code>{uid}</code>", parse_mode="HTML")


def admin_unban_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    unban_user(uid)
    bot.send_message(message.chat.id, f"✅ تم فك حظر <code>{uid}</code>", parse_mode="HTML")


def admin_delete_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    delete_user(uid)
    bot.send_message(message.chat.id, f"🗑️ تم حذف <code>{uid}</code>", parse_mode="HTML")


def admin_grant_vip_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return

    u = get_or_create_user(uid)
    u["is_vip"] = True
    save_user(uid, u)

    bot.send_message(
        message.chat.id,
        f"💎 تم منح VIP لـ <code>{uid}</code>",
        parse_mode="HTML"
    )

    try:
        bot.send_message(uid, "💎 <b>تهانينا!</b> VIP مُفعّل 🚀", parse_mode="HTML")
    except Exception:
        pass


def admin_give_stars_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        parts = (message.text or "").split("|")
        uid = int(parts[0].strip())
        amount = int(parts[1].strip())
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ صيغة خاطئة")
        return

    u = get_or_create_user(uid)
    u["total_stars_spent"] = max(0, u.get("total_stars_spent", 0) - amount)
    save_user(uid, u)

    bot.send_message(
        message.chat.id,
        f"⭐ تم إعطاء <code>{amount}</code> نجمة لـ <code>{uid}</code>",
        parse_mode="HTML"
    )


def admin_msg_user_handler(message, uid):
    if not is_admin(message.chat.id):
        return
    try:
        bot.send_message(
            uid,
            f"📨 <b>من الإدارة:</b>\n\n{h(message.text)}",
            parse_mode="HTML"
        )
        bot.send_message(message.chat.id, "✅ تم الإرسال", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {h(str(e))}", parse_mode="HTML")
