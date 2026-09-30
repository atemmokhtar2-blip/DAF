# phone_search.py
# ============================================================
# محرك البحث بالرقم — v1.0
# دمج: phonenumbers + Truecaller + PhoneInfoga + WhatsApp + Telegram
# ============================================================

import os
import re
import time
import json
import uuid
import random
import requests
import threading
from datetime import datetime

try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone as pn_timezone
    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    print("[PHONE] phonenumbers not installed")

from config import redis_client, bot

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("phone_search")


# ============================================================
# الإعدادات
# ============================================================
DEFAULT_REGION = "EG"
CACHE_TTL = 3600 * 24 * 7   # أسبوع
TRUECALLER_COOKIE = os.getenv("TRUECALLER_COOKIE", "")

# ─── Rate Limiting ───
_last_tc_request = 0
_tc_lock = threading.Lock()
TC_MIN_INTERVAL = 3  # 3 ثواني بين كل طلب


# ============================================================
# [1] التحليل الأساسي — phonenumbers
# ============================================================
def _basic_analysis(phone_number):
    """
    تحليل الرقم: البلد + الشركة + النوع
    مجاني 100% — بدون APIs
    """
    if not PHONENUMBERS_AVAILABLE:
        return None

    try:
        # تأكد من وجود +20 للرقم المصري
        if not phone_number.startswith('+'):
            if phone_number.startswith('0'):
                phone_number = '+20' + phone_number[1:]
            else:
                phone_number = '+20' + phone_number

        parsed = phonenumbers.parse(phone_number, None)

        if not phonenumbers.is_valid_number(parsed):
            return {
                'valid': False,
                'e164': phonenumbers.format_number(
                    parsed,
                    phonenumbers.PhoneNumberFormat.E164
                ),
            }

        # ─── Collect Info ───
        result = {
            'valid': True,
            'e164': phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            ),
            'international': phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
            ),
            'national': phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.NATIONAL
            ),
            'country_code': parsed.country_code,
            'national_number': parsed.national_number,
            'country': geocoder.country_name_for_number(parsed, "ar"),
            'country_en': geocoder.country_name_for_number(parsed, "en"),
            'location': geocoder.description_for_number(parsed, "ar"),
            'location_en': geocoder.description_for_number(parsed, "en"),
            'carrier': carrier.name_for_number(parsed, "en"),
            'carrier_ar': carrier.name_for_number(parsed, "ar"),
            'timezones': list(pn_timezone.time_zones_for_number(parsed)),
        }

        # ─── Type ───
        num_type = phonenumbers.number_type(parsed)
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "موبايل",
            phonenumbers.PhoneNumberType.FIXED_LINE: "أرضي",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "أرضي/موبايل",
            phonenumbers.PhoneNumberType.TOLL_FREE: "مجاني",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "خدمة مدفوعة",
            phonenumbers.PhoneNumberType.VOIP: "VoIP",
            phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "رقم شخصي",
            phonenumbers.PhoneNumberType.PAGER: "بيجر",
            phonenumbers.PhoneNumberType.UAN: "UAN",
            phonenumbers.PhoneNumberType.VOICEMAIL: "بريد صوتي",
            phonenumbers.PhoneNumberType.UNKNOWN: "غير معروف",
        }
        result['type'] = type_map.get(num_type, "غير معروف")

        return result

    except Exception as e:
        logger.warning(f"basic_analysis error: {e}")
        return None


# ============================================================
# [2] Truecaller Search
# ============================================================
def _truecaller_search(phone_number):
    """
    بحث في Truecaller باستخدام Cookie
    يرجع: الاسم + الصورة + Spam Reports
    """
    global _last_tc_request

    if not TRUECALLER_COOKIE:
        logger.info("[Truecaller] No cookie configured")
        return None

    try:
        with _tc_lock:
            # Rate limiting
            elapsed = time.time() - _last_tc_request
            if elapsed < TC_MIN_INTERVAL:
                time.sleep(TC_MIN_INTERVAL - elapsed)
            _last_tc_request = time.time()

        # تأكد من +20
        if not phone_number.startswith('+'):
            if phone_number.startswith('0'):
                phone_number = '+20' + phone_number[1:]
            else:
                phone_number = '+20' + phone_number

        encoded = requests.utils.quote(phone_number)

        url = f"https://search5-noneu.truecaller.com/v2/search?q={encoded}&countryCode=EG&type=4&encoding=json"

        headers = {
            'User-Agent': 'Truecaller/14.7.8 (Android; 13)',
            'Authorization': f'Bearer {TRUECALLER_COOKIE}',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
        }

        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            logger.warning(f"[Truecaller] HTTP {r.status_code}")
            return None

        data = r.json()

        result = {
            'name': None,
            'photo': None,
            'spam': None,
            'spam_score': 0,
            'carrier': None,
            'location': None,
            'phones': [],
            'addresses': [],
        }

        # ─── Parse Data ───
        if data.get('data'):
            entry = data['data'][0]
            result['name'] = entry.get('name')
            result['spam'] = entry.get('spam')
            result['spam_score'] = entry.get('spamScore', 0)
            result['carrier'] = entry.get('carrier')
            result['location'] = entry.get('address')

            if entry.get('image'):
                result['photo'] = entry['image']

            # Additional phones
            for p in entry.get('phones', []):
                if p.get('e164'):
                    result['phones'].append({
                        'e164': p['e164'],
                        'type': p.get('numberType', 'unknown'),
                    })

            for a in entry.get('addresses', []):
                if a.get('address'):
                    result['addresses'].append(a['address'])

        return result

    except Exception as e:
        logger.warning(f"[Truecaller] error: {e}")
        return None


# ============================================================
# [3] OSINT Footprints (Google Dorks)
# ============================================================
def _osint_footprints(phone_number):
    """
    روابط بحث جاهزة لكل المنصات
    """
    if not phone_number.startswith('+'):
        if phone_number.startswith('0'):
            phone_number = '+20' + phone_number[1:]
        else:
            phone_number = '+20' + phone_number

    # نسخة بدون + للبحث في المنصات
    digits_only = phone_number.replace('+', '')
    local = '0' + digits_only[2:]  # 01012345678

    return {
        'google': [
            f'"{phone_number}"',
            f'"{local}"',
            f'"{local}" site:facebook.com',
            f'"{local}" site:instagram.com',
            f'"{local}" site:twitter.com',
            f'"{local}" site:tiktok.com',
            f'"{local}" site:linkedin.com',
            f'"{local}" filetype:pdf',
            f'"{local}" filetype:doc',
            f'"{local}" pastebin',
            f'"{local}" -site:facebook.com -site:instagram.com',
        ],
        'facebook_search': f'https://www.facebook.com/search/top?q={local}',
        'instagram_search': f'https://www.instagram.com/{local}',
        'twitter_search': f'https://twitter.com/search?q={local}',
        'tiktok_search': f'https://www.tiktok.com/search/user?q={local}',
        'whatsapp_direct': f'https://wa.me/{digits_only}',
        'telegram_direct': f'https://t.me/{phone_number}',
        'truecaller_web': f'https://www.truecaller.com/search/eg/{digits_only}',
        'sync_me': f'https://sync.me/search/?number={digits_only}',
        'getcontact': f'https://www.getcontact.com/',
    }


# ============================================================
# [4] WhatsApp Check
# ============================================================
def _check_whatsapp(phone_number):
    """
    يفحص هل الرقم نشط على WhatsApp
    (بدون إرسال رسالة — فقط فحص عبر wa.me)
    """
    if not phone_number.startswith('+'):
        if phone_number.startswith('0'):
            phone_number = '+20' + phone_number[1:]
        else:
            phone_number = '+20' + phone_number

    digits_only = phone_number.replace('+', '')

    try:
        r = requests.get(
            f'https://wa.me/{digits_only}',
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'},
            allow_redirects=True,
        )

        if 'api.whatsapp.com' in r.url or 'wa.me' in r.url:
            if 'invalid' not in r.text.lower():
                return True
        return False
    except Exception:
        return None


# ============================================================
# [5] Telegram Check
# ============================================================
def _check_telegram(phone_number):
    """
    يفحص هل الرقم نشط على Telegram
    """
    if not phone_number.startswith('+'):
        if phone_number.startswith('0'):
            phone_number = '+20' + phone_number[1:]
        else:
            phone_number = '+20' + phone_number

    # طريقة غير مباشرة: نجرّب t.me/+<number>
    try:
        r = requests.get(
            f'https://t.me/{phone_number}',
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        if r.status_code == 200 and 'tgme_page_title' in r.text:
            return True
        return False
    except Exception:
        return None


# ============================================================
# المحرك الرئيسي
# ============================================================
def search_phone(phone_number, chat_id=None):
    """
    البحث الشامل بالرقم
    يرجع dict فيه كل المعلومات
    """
    # Clean
    clean = re.sub(r'[^0-9+]', '', phone_number)

    if not clean:
        return {'error': 'رقم غير صالح'}

    if len(clean) < 8:
        return {'error': 'الرقم قصير جداً'}

    # ─── Cache ───
    cache_key = f"phone_search:{clean}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"[Phone] Cache hit: {clean}")
                return json.loads(cached)
        except Exception:
            pass

    result = {
        'query': clean,
        'timestamp': time.time(),
        'timestamp_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # ─── [1] Basic ───
    logger.info(f"[Phone] Basic analysis: {clean}")
    basic = _basic_analysis(clean)
    if not basic or not basic.get('valid'):
        return {'error': 'رقم غير صالح', 'basic': basic}

    result['basic'] = basic

    # ─── [2] Truecaller ───
    logger.info(f"[Phone] Truecaller: {clean}")
    tc = _truecaller_search(clean)
    if tc:
        result['truecaller'] = tc

    # ─── [3] OSINT Footprints ───
    result['footprints'] = _osint_footprints(clean)

    # ─── [4] WhatsApp ───
    logger.info(f"[Phone] WhatsApp check: {clean}")
    wa = _check_whatsapp(clean)
    result['whatsapp'] = wa

    # ─── [5] Telegram ───
    logger.info(f"[Phone] Telegram check: {clean}")
    tg = _check_telegram(clean)
    result['telegram'] = tg

    # ─── Cache Result ───
    if redis_client:
        try:
            redis_client.setex(
                cache_key,
                CACHE_TTL,
                json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"Cache save error: {e}")

    # ─── Save History ───
    if chat_id and redis_client:
        try:
            redis_client.lpush(
                f"phone_searches:{chat_id}",
                json.dumps({
                    'phone': clean,
                    'name': (tc or {}).get('name', ''),
                    'timestamp': time.time(),
                }, ensure_ascii=False)
            )
            redis_client.ltrim(f"phone_searches:{chat_id}", 0, 99)
        except Exception:
            pass

    metrics.inc_counter("phone_searches")
    return result


# ============================================================
# تنسيق النتيجة للبوت
# ============================================================
def format_result_for_telegram(result):
    """
    يحوّل نتيجة البحث لرسالة تليجرام منسقة
    """
    if 'error' in result:
        return f"❌ <b>خطأ:</b> {result['error']}"

    basic = result.get('basic', {})
    tc = result.get('truecaller') or {}
    fp = result.get('footprints', {})
    wa = result.get('whatsapp')
    tg = result.get('telegram')

    lines = [
        f"🔎 <b>نتيجة البحث</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"📱 <b>الرقم:</b> <code>{basic.get('e164', result.get('query'))}</code>",
        f"🌍 <b>البلد:</b> {basic.get('country', '?')} ({basic.get('country_en', '?')})",
        f"📡 <b>الشركة:</b> {basic.get('carrier', 'غير معروف')}",
        f"📞 <b>النوع:</b> {basic.get('type', 'غير معروف')}",
        f"🗺️ <b>الموقع:</b> {basic.get('location', 'غير معروف')}",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]

    # ─── Truecaller Info ───
    if tc:
        name = tc.get('name')
        if name:
            lines.append(f"👤 <b>الاسم:</b> <code>{name}</code>")

        spam_score = tc.get('spam_score', 0)
        if spam_score:
            emoji = "⚠️" if spam_score < 50 else "🚨"
            lines.append(f"{emoji} <b>بلاغات Spam:</b> {spam_score}")

        tc_carrier = tc.get('carrier')
        if tc_carrier and tc_carrier != basic.get('carrier'):
            lines.append(f"📡 <b>الشركة (TC):</b> {tc_carrier}")

        tc_location = tc.get('location')
        if tc_location:
            lines.append(f"📍 <b>الموقع (TC):</b> {tc_location}")

        if tc.get('addresses'):
            lines.append(f"")
            lines.append(f"🏠 <b>العناوين:</b>")
            for addr in tc['addresses'][:3]:
                lines.append(f"  • {addr}")

        if tc.get('phones') and len(tc['phones']) > 1:
            lines.append(f"")
            lines.append(f"📞 <b>أرقام إضافية:</b>")
            for p in tc['phones'][:3]:
                if p['e164'] != result.get('query'):
                    lines.append(f"  • <code>{p['e164']}</code>")

        lines.append(f"")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    else:
        lines.append(f"")
        lines.append(f"👤 <b>Truecaller:</b> لا توجد بيانات (مطلوب Cookie)")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")

    # ─── WhatsApp / Telegram ───
    if wa is True:
        lines.append(f"✅ <b>WhatsApp:</b> نشط")
    elif wa is False:
        lines.append(f"❌ <b>WhatsApp:</b> غير نشط")

    if tg is True:
        lines.append(f"✅ <b>Telegram:</b> نشط")
    elif tg is False:
        lines.append(f"❌ <b>Telegram:</b> غير نشط")

    # ─── Google Dorks ───
    lines.append(f"")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🔍 <b>Google Dorks (اضغط للبحث):</b>")

    dorks = fp.get('google', [])
    for i, dork in enumerate(dorks[:5], 1):
        encoded = requests.utils.quote(dork)
        lines.append(f"  {i}. <a href='https://www.google.com/search?q={encoded}'>{dork[:50]}</a>")

    # ─── Direct Links ───
    lines.append(f"")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🔗 <b>روابط مباشرة:</b>")
    lines.append(f"  • <a href='{fp.get('whatsapp_direct', '#')}'>WhatsApp Direct</a>")
    lines.append(f"  • <a href='{fp.get('facebook_search', '#')}'>Facebook Search</a>")
    lines.append(f"  • <a href='{fp.get('truecaller_web', '#')}'>Truecaller Web</a>")
    lines.append(f"  • <a href='{fp.get('sync_me', '#')}'>Sync.me</a>")

    return "\n".join(lines)
