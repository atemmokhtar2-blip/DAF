# bot_handlers/commands/__init__.py
from .start import start_command
from .dashboard import dashboard_command
from .update import update_command
from .silent import silent_command

__all__ = ["start_command", "dashboard_command", "update_command", "silent_command"]
