# fake_sites/core/__init__.py
# ============================================================
# الطبقة الأساسية — مشتركة لكل المواقع
# ============================================================

import os

from flask import render_template_string

from logging_config import get_logger

logger = get_logger("fake_sites.core")

# مسار قوالب core
CORE_DIR = os.path.dirname(os.path.abspath(__file__))


def render_template_with_core(template_name, **kwargs):
    """
    يقرأ قالب من مجلد core أو من القسم
    """
    # ابحث في core
    path = os.path.join(CORE_DIR, 'templates', template_name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template_string(content, **kwargs)

    return None


__all__ = ['render_template_with_core', 'CORE_DIR']
