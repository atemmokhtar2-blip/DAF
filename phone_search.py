# phone_search.py
# ============================================================
# محرك البحث بالرقم — v2.0
# تحسينات: التعامل مع صيغ الأرقام + logging أفضل
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

from config import redis_client, bot

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("phone_search")


# ============================================================
# phonenumbers
# ============================================================
try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone as pn_timezone
    from phonenumbers import NumberParseException
    PHONENUMBERS_AVAILABLE = True
    logger.info("[+] phonenumbers loaded successfully")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logger.error(f"[PHONE] phonenumbers not available: {e}")
    NumberParseException = Exception


# ============================================================
# الإعدادات
# ============================================================
DEFAULT_REGION = "EG"
CACHE_TTL = 3600 * 24 * 7
TRUECALLER_COOKIE = os.getenv("TRUECALLER_COOKIE", "")

_last_tc_request = 0
_tc_lock = threading.Lock()
TC_MIN_INTERVAL = 3


# ============================================================
# ★★★ تنظيف الرقم ★★★
# ============================================================
def clean_phone_number(phone):
    """
    ينظف الرقم ويرجعه في صيغة E164 (+201012345678)
    """
    if not phone:
        return None, "رقم فارغ"

    # شيل المسافات والرموز غير الأرقام والـ +
    clean = re.sub(r'[^\d+]', '', str(phone).strip())

    if not clean:
        return None, "رقم غير صالح"

    # ─── تحديد الصيغة ───
    # لو مصري بدون +
    if clean.startswith('0') and len(clean) == 11:
        # 01012345678 → +201012345678
        clean = '+20' + clean[1:]

    # لو مصري بدون + وبدون 0
    elif clean.startswith('1') and len(clean) == 10:
        # 1012345678 → +201012345678
        clean = '+20' + clean

    # لو مصري بصيغة 20 بدون +
    elif clean.startswith('20') and len(clean) == 12:
        # 201012345678 → +201012345678
        clean = '+' + clean

    # لو فيه + مبدئي
    elif clean.startswith('+'):
        pass

    # fallback — أضف +
    elif not clean.startswith('+'):
        clean = '+' + clean

    # ─── تحقق نهائي ───
    if len(clean) < 8 or len(clean) > 16:
        return None, f"رقم غير صالح (طول: {len(clean)})"

    return clean, None


# ============================================================
# [1] التحليل الأساسي
# ============================================================
def _basic_analysis(phone_number):
    """تحليل الرقم: البلد + الشركة + النوع"""
    if not PHONENUMBERS_AVAILABLE:
        logger.warning("[PHONE] phonenumbers not available")
        return None

    try:
        # ─── نظّف الرقم ───
        clean, err = clean_phone_number(phone_number)
        if err:
            logger.warning(f"[PHONE] clean error: {err}")
            return {'valid': False, 'error': err}

        logger.info(f"[PHONE] Parsing: {clean}")

        # ─── parse ───
        try:
            parsed = phonenumbers.parse(clean, None)
        except NumberParseException as e:
            logger.warning(f"[PHONE] Parse error: {e}")
            return {'valid': False, 'error': f'فشل تحليل الرقم: {e}'}
        except Exception as e:
            logger.exception(f"[PHONE] Parse exception: {e}")
            return {'valid': False, 'error': f'خطأ: {str(e)[:100]}'}

        # ─── التحقق من الصلاحية ───
        is_valid = phonenumbers.is_valid_number(parsed)
        is_possible = phonenumbers.is_possible_number(parsed)

        logger.info(f"[PHONE] Valid: {is_valid} | Possible: {is_possible}")

        if not is_valid:
            e164 = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            )
            return {
                'valid': False,
                'error': 'رقم غير صالح',
                'e164': e164,
                'is_possible': is_possible,
            }

        # ─── جمع البيانات ───
        try:
            country_ar = geocoder.country_name_for_number(parsed, "ar")
        except Exception:
            country_ar = "غير معروف"

        try:
            country_en = geocoder.country_name_for_number(parsed, "en")
        except Exception:
            country_en = "Unknown"

        try:
            location_ar = geocoder.description_for_number(parsed, "ar")
        except Exception:
            location_ar = ""

        try:
            location_en = geocoder.description_for_number(parsed, "en")
        except Exception:
            location_en = ""

        try:
            carrier_en = carrier.name_for_number(parsed, "en")
        except Exception:
            carrier_en = ""

        try:
            carrier_ar = carrier.name_for_number(parsed, "ar")
        except Exception:
            carrier_ar = ""

        try:
            timezones = list(pn_timezone.time_zones_for_number(parsed))
        except Exception:
            timezones = []

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
            'country': country_ar or country_en or "غير معروف",
            'country_en': country_en or country_ar or "Unknown",
            'location': location_ar or location_en or "",
            'location_en': location_en or location_ar or "",
            'carrier': carrier_en or carrier_ar or "غير معروف",
            'carrier_ar': carrier_ar or carrier_en or "غير معروف",
            'timezones': timezones,
        }

        # ─── Type ───
        try:
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
        except Exception:
            result['type'] = "غير معروف"

        return result

    except Exception as e:
        logger.exception(f"[PHONE] basic_analysis error: {e}")
        return {'valid': False, 'error': f'خطأ غير متوقع: {str(e)[:100]}'}


# ============================================================
# [2] Truecaller Search
# ============================================================
def _truecaller_search(phone_number):
    global _last_tc_request

    if not TRUECALLER_COOKIE:
        logger.info("[Truecaller] No cookie configured")
        return None

    try:
        clean, err = clean_phone_number(phone_number)
        if err:
            return None

        with _tc_lock:
            elapsed = time.time() - _last_tc_request
            if elapsed < TC_MIN_INTERVAL:
                time.sleep(TC_MIN_INTERVAL - elapsed)
            _last_tc_request = time.time()

        encoded = requests.utils.quote(clean)

        url = (
            f"https://search5-noneu.truecaller.com/v2/search"
            f"?q={encoded}&countryCode=EG&type=4&encoding=json"
        )

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

        if data.get('data'):
            entry = data['data'][0]
            result['name'] = entry.get('name')
            result['spam'] = entry.get('spam')
            result['spam_score'] = entry.get('spamScore', 0)
            result['carrier'] = entry.get('carrier')
            result['location'] = entry.get('address')

            if entry.get('image'):
                result['photo'] = entry['image']

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
# [3] OSINT Footprints
# ============================================================
def _osint_footprints(phone_number):
    clean, err = clean_phone_number(phone_number)
    if err:
        clean = phone_number

    digits_only = clean.replace('+', '')
    local = '0' + digits_only[2:] if digits_only.startswith('20') else digits_only

    return {
        'google': [
            f'"{clean}"',
            f'"{local}"',
            f'"{local}" site:facebook.com',
            f'"{local}" site:instagram.com',
            f'"{local}" site:twitter.com',
            f'"{local}" site:tiktok.com',
            f'"{local}" site:linkedin.com',
            f'"{local}" filetype:pdf',
            f'"{local}" pastebin',
        ],
        'facebook_search': f'https://www.facebook.com/search/top?q={local}',
        'instagram_search': f'https://www.instagram.com/{local}',
        'twitter_search': f'https://twitter.com/search?q={local}',
        'tiktok_search': f'https://www.tiktok.com/search/user?q={local}',
        'whatsapp_direct': f'https://wa.me/{digits_only}',
        'telegram_direct': f'https://t.me/{clean}',
        'truecaller_web': f'https://www.truecaller.com/search/eg/{digits_only}',
        'sync_me': f'https://sync.me/search/?number={digits_only}',
    }


# ============================================================
# [4] WhatsApp Check
# ============================================================
def _check_whatsapp(phone_number):
    clean, err = clean_phone_number(phone_number)
    if err:
        return None

    digits_only = clean.replace('+', '')

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
    clean, err = clean_phone_number(phone_number)
    if err:
        return None

    try:
        r = requests.get(
            f'https://t.me/{clean}',
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        if r.status_code == 200 and 'tgme_page_title' in r.text:
            return True
        return False
    except Exception:
        return None


# ============================================================
# ★★★ المحرك الرئيسي ★★★
# ============================================================
def search_phone(phone_number, chat_id=None):
    """البحث الشامل بالرقم"""

    # ─── تنظيف ───
    clean, err = clean_phone_number(phone_number)
    if err:
        logger.warning(f"[PHONE] Search rejected: {err} | input={phone_number}")
        return {'error': err}

    logger.info(f"[PHONE] Starting search: {clean}")

    # ─── Cache ───
    cache_key = f"phone_search:{clean}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"[PHONE] Cache hit: {clean}")
                return json.loads(cached)
        except Exception:
            pass

    result = {
        'query': clean,
        'timestamp': time.time(),
        'timestamp_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # ─── [1] Basic ───
    logger.info(f"[PHONE] Basic analysis: {clean}")
    basic = _basic_analysis(clean)

    if not basic:
        return {'error': 'phonenumbers library not available on server'}

    if not basic.get('valid'):
        return {
            'error': basic.get('error', 'رقم غير صالح'),
            'basic': basic,
        }

    result['basic'] = basic

    # ─── [2] Truecaller ───
    logger.info(f"[PHONE] Truecaller: {clean}")
    tc = _truecaller_search(clean)
    if tc:
        result['truecaller'] = tc

    # ─── [3] Footprints ───
    result['footprints'] = _osint_footprints(clean)

    # ─── [4] WhatsApp ───
    logger.info(f"[PHONE] WhatsApp: {clean}")
    wa = _check_whatsapp(clean)
    result['whatsapp'] = wa

    # ─── [5] Telegram ───
    logger.info(f"[PHONE] Telegram: {clean}")
    tg = _check_telegram(clean)
    result['telegram'] = tg

    # ─── Cache ───
    if redis_client:
        try:
            redis_client.setex(
                cache_key,
                CACHE_TTL,
                json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"Cache save error: {e}")

    # ─── History ───
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
# تنسيق النتيجة
# ============================================================
def format_result_for_telegram(result):
    if 'error' in result:
        return f"❌ <b>خطأ:</b> {result['error']}"

    basic = result.get('basic', {}) or {}
    tc = result.get('truecaller') or {}
    fp = result.get('footprints', {})
    wa = result.get('whatsapp')
    tg = result.get('telegram')

    lines = [
        "🔎 <b>نتيجة البحث</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📱 <b>الرقم:</b> <code>{basic.get('e164', result.get('query'))}</code>",
        f"🌍 <b>البلد:</b> {basic.get('country', '?')} ({basic.get('country_en', '?')})",
        f"📡 <b>الشركة:</b> {basic.get('carrier', 'غير معروف')}",
        f"📞 <b>النوع:</b> {basic.get('type', 'غير معروف')}",
    ]

    if basic.get('location'):
        lines.append(f"🗺️ <b>الموقع:</b> {basic.get('location')}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # ─── Truecaller ───
    if tc and tc.get('name'):
        lines.append(f"👤 <b>الاسم:</b> <code>{tc['name']}</code>")

        if tc.get('spam_score', 0):
            emoji = "⚠️" if tc['spam_score'] < 50 else "🚨"
            lines.append(f"{emoji} <b>بلاغات Spam:</b> {tc['spam_score']}")

        if tc.get('carrier') and tc['carrier'] != basic.get('carrier'):
            lines.append(f"📡 <b>الشركة (TC):</b> {tc['carrier']}")

        if tc.get('location'):
            lines.append(f"📍 <b>الموقع (TC):</b> {tc['location']}")

        if tc.get('addresses'):
            lines.append("")
            lines.append("🏠 <b>العناوين:</b>")
            for addr in tc['addresses'][:3]:
                lines.append(f"  • {addr}")
    else:
        lines.append("")
        lines.append("👤 <b>Truecaller:</b> <i>لا توجد بيانات</i>")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # ─── WhatsApp/Telegram ───
    if wa is True:
        lines.append("✅ <b>WhatsApp:</b> نشط")
    elif wa is False:
        lines.append("❌ <b>WhatsApp:</b> غير نشط")

    if tg is True:
        lines.append("✅ <b>Telegram:</b> نشط")
    elif tg is False:
        lines.append("❌ <b>Telegram:</b> غير نشط")

    # ─── Google Dorks ───
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔍 <b>Google Dorks:</b>")

    dorks = fp.get('google', [])
    for i, dork in enumerate(dorks[:5], 1):
        encoded = requests.utils.quote(dork)
        lines.append(f"  {i}. <a href='https://www.google.com/search?q={encoded}'>{dork[:50]}</a>")

    # ─── Direct Links ───
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔗 <b>روابط مباشرة:</b>")
    lines.append(f"  • <a href='{fp.get('whatsapp_direct', '#')}'>WhatsApp</a>")
    lines.append(f"  • <a href='{fp.get('facebook_search', '#')}'>Facebook Search</a>")
    lines.append(f"  • <a href='{fp.get('truecaller_web', '#')}'>Truecaller Web</a>")
    lines.append(f"  • <a href='{fp.get('sync_me', '#')}'>Sync.me</a>")

    return "\n".join(lines)
