# phone_search.py
# ============================================================
# محرك البحث بالرقم — v3.0
# 4 مصادر مجانية + PhoneInfoga integration
# ============================================================

import os
import re
import time
import json
import requests
import threading
from datetime import datetime

from config import redis_client, bot

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("phone_search")


try:
    import phonenumbers
    from phonenumbers import geocoder, carrier
    from phonenumbers import NumberParseException
    PHONENUMBERS_AVAILABLE = True
    logger.info("[+] phonenumbers loaded")
except Exception as e:
    PHONENUMBERS_AVAILABLE = False
    logger.error(f"phonenumbers: {e}")
    NumberParseException = Exception


CACHE_TTL = 3600 * 24 * 7


# ============================================================
# تنظيف الرقم
# ============================================================
def clean_phone_number(phone):
    if not phone:
        return None, "رقم فارغ"
    clean = re.sub(r'[^\d+]', '', str(phone).strip())
    if not clean:
        return None, "رقم غير صالح"

    if clean.startswith('0') and len(clean) == 11:
        clean = '+20' + clean[1:]
    elif clean.startswith('1') and len(clean) == 10:
        clean = '+20' + clean
    elif clean.startswith('20') and len(clean) == 12:
        clean = '+' + clean
    elif not clean.startswith('+'):
        clean = '+' + clean

    if len(clean) < 8 or len(clean) > 16:
        return None, f"رقم غير صالح (طول: {len(clean)})"

    return clean, None


# ============================================================
# [1] التحليل الأساسي
# ============================================================
def _basic_analysis(phone_number):
    if not PHONENUMBERS_AVAILABLE:
        return None

    try:
        clean, err = clean_phone_number(phone_number)
        if err:
            return {'valid': False, 'error': err}

        try:
            parsed = phonenumbers.parse(clean, None)
        except Exception as e:
            return {'valid': False, 'error': f'فشل تحليل الرقم'}

        if not phonenumbers.is_valid_number(parsed):
            return {'valid': False, 'error': 'رقم غير صالح'}

        result = {
            'valid': True,
            'e164': phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            'international': phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            'national': phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
            'country_code': parsed.country_code,
            'country': geocoder.country_name_for_number(parsed, "ar") or "غير معروف",
            'country_en': geocoder.country_name_for_number(parsed, "en") or "Unknown",
            'location': geocoder.description_for_number(parsed, "ar") or "",
            'carrier': carrier.name_for_number(parsed, "en") or "غير معروف",
        }

        num_type = phonenumbers.number_type(parsed)
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "موبايل",
            phonenumbers.PhoneNumberType.FIXED_LINE: "أرضي",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "أرضي/موبايل",
            phonenumbers.PhoneNumberType.VOIP: "VoIP",
            phonenumbers.PhoneNumberType.UNKNOWN: "غير معروف",
        }
        result['type'] = type_map.get(num_type, "غير معروف")

        return result
    except Exception as e:
        logger.exception(f"basic_analysis: {e}")
        return None


# ============================================================
# ★★★ [2] Sync.me — يجيب الاسم بشكل محدود ★★★
# ============================================================
def _syncme_search(phone_number):
    """بحث في Sync.me"""
    clean, err = clean_phone_number(phone_number)
    if err:
        return None

    digits = clean.replace('+', '')

    try:
        url = f"https://sync.me/search/?number={digits}"
        r = requests.get(
            url,
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
        )

        if r.status_code != 200:
            return None

        text = r.text

        # ابحث عن الاسم في HTML
        name_match = re.search(r'<h2[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</h2>', text)
        if not name_match:
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', text)

        spam_match = re.search(r'"spam"\s*:\s*(\d+)', text)

        if not name_match:
            return None

        return {
            'name': name_match.group(1).strip(),
            'spam_score': int(spam_match.group(1)) if spam_match else 0,
            'source': 'sync.me',
        }
    except Exception as e:
        logger.warning(f"sync.me error: {e}")
        return None


# ============================================================
# ★★★ [3] RevealName — Name + Carrier ★★★
# ============================================================
def _revealname_search(phone_number):
    """بحث في RevealName.com"""
    clean, err = clean_phone_number(phone_number)
    if err:
        return None

    digits = clean.replace('+', '')

    try:
        # RevealName بيشتغل بـ POST
        url = "https://www.revealname.com/"

        r = requests.post(
            url,
            data={'phone_number': digits},
            timeout=10,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )

        if r.status_code != 200:
            return None

        text = r.text

        # ابحث عن الاسم
        name_match = re.search(r'<span[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</span>', text)
        if not name_match:
            name_match = re.search(r'Name:\s*<[^>]*>([^<]+)<', text)

        if not name_match:
            return None

        return {
            'name': name_match.group(1).strip(),
            'source': 'revealname',
        }
    except Exception as e:
        logger.warning(f"revealname error: {e}")
        return None


# ============================================================
# ★★★ [4] Whoseno — Name ★★★
# ============================================================
def _whoseno_search(phone_number):
    """بحث في Whoseno.com"""
    clean, err = clean_phone_number(phone_number)
    if err:
        return None

    digits = clean.replace('+', '')

    try:
        url = f"https://www.whoseno.com/{digits}"

        r = requests.get(
            url,
            timeout=8,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
        )

        if r.status_code != 200:
            return None

        text = r.text

        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', text)
        if not name_match:
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', text)

        if not name_match:
            return None

        name = name_match.group(1).strip()
        if name.lower() in ['unknown', 'no data', 'not found']:
            return None

        return {
            'name': name,
            'source': 'whoseno',
        }
    except Exception as e:
        logger.warning(f"whoseno error: {e}")
        return None


# ============================================================
# ★★★ [5] PhoneInfoga-style Google Dorks ★★★
# ============================================================
def _osint_footprints(phone_number):
    """Google Dorks (زي PhoneInfoga)"""
    clean, err = clean_phone_number(phone_number)
    if err:
        clean = phone_number

    digits = clean.replace('+', '')
    local = '0' + digits[2:] if digits.startswith('20') else digits

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
            f'"{local}" filetype:doc',
            f'"{local}" pastebin',
            f'"{local}" -site:facebook.com -site:instagram.com',
        ],
        'facebook_search': f'https://www.facebook.com/search/top?q={local}',
        'instagram_search': f'https://www.instagram.com/{local}',
        'twitter_search': f'https://twitter.com/search?q={local}',
        'tiktok_search': f'https://www.tiktok.com/search/user?q={local}',
        'whatsapp_direct': f'https://wa.me/{digits}',
        'telegram_direct': f'https://t.me/{clean}',
        'truecaller_web': f'https://www.truecaller.com/search/eg/{digits}',
        'sync_me': f'https://sync.me/search/?number={digits}',
        'getcontact': 'https://www.getcontact.com/',
        'mobiletracker': f'https://www.emobiletracker.com/number/{digits}',
    }


# ============================================================
# ★★★ [6] WhatsApp/Telegram Check ★★★
# ============================================================
def _check_whatsapp(phone_number):
    clean, err = clean_phone_number(phone_number)
    if err:
        return None
    digits = clean.replace('+', '')
    try:
        r = requests.get(
            f'https://wa.me/{digits}', timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True,
        )
        return 'invalid' not in r.text.lower()
    except Exception:
        return None


def _check_telegram(phone_number):
    clean, err = clean_phone_number(phone_number)
    if err:
        return None
    try:
        r = requests.get(
            f'https://t.me/{clean}', timeout=8,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        return r.status_code == 200 and 'tgme_page_title' in r.text
    except Exception:
        return None


# ============================================================
# ★★★ المحرك الرئيسي ★★★
# ============================================================
def search_phone(phone_number, chat_id=None):
    """البحث الشامل من 6 مصادر"""
    clean, err = clean_phone_number(phone_number)
    if err:
        return {'error': err}

    logger.info(f"[PHONE] Search: {clean}")

    # Cache
    cache_key = f"phone_search:{clean}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    result = {
        'query': clean,
        'timestamp': time.time(),
        'timestamp_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # [1] Basic
    basic = _basic_analysis(clean)
    if not basic or not basic.get('valid'):
        return {'error': basic.get('error', 'رقم غير صالح') if basic else 'خطأ في التحليل'}
    result['basic'] = basic

    # [2-5] مصادر الاسم (بالتوازي)
    name_result = None

    # نجرب المصادر بالترتيب
    for fn in [_syncme_search, _revealname_search, _whoseno_search]:
        try:
            res = fn(clean)
            if res and res.get('name'):
                name_result = res
                logger.info(f"[PHONE] Name found from {res.get('source')}: {res['name']}")
                break
        except Exception as e:
            logger.warning(f"Name source error: {e}")
            continue

    if name_result:
        result['name_info'] = name_result

    # [6] Footprints
    result['footprints'] = _osint_footprints(clean)

    # [7] WhatsApp/Telegram
    result['whatsapp'] = _check_whatsapp(clean)
    result['telegram'] = _check_telegram(clean)

    # Cache
    if redis_client:
        try:
            redis_client.setex(cache_key, CACHE_TTL, json.dumps(result, ensure_ascii=False))
        except Exception:
            pass

    # History
    if chat_id and redis_client:
        try:
            redis_client.lpush(
                f"phone_searches:{chat_id}",
                json.dumps({
                    'phone': clean,
                    'name': (name_result or {}).get('name', ''),
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
    name_info = result.get('name_info') or {}
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

    # ─── الاسم ───
    if name_info.get('name'):
        lines.append(f"👤 <b>الاسم:</b> <code>{name_info['name']}</code>")
        source = name_info.get('source', '')
        if source:
            source_icons = {
                'sync.me': '🔄',
                'revealname': '🔍',
                'whoseno': '📞',
                'truecaller': '☎️',
            }
            lines.append(f"   <i>المصدر: {source_icons.get(source, '🔗')} {source}</i>")

        if name_info.get('spam_score'):
            lines.append(f"🚨 <b>بلاغات Spam:</b> {name_info['spam_score']}")
    else:
        lines.append("👤 <b>الاسم:</b> <i>غير متاح (المصادر المجانية محدودة)</i>")
        lines.append("")
        lines.append("💡 <b>جرّب Truecaller يدوياً:</b>")
        lines.append(f"  <a href='{fp.get('truecaller_web', '#')}'>فتح Truecaller</a>")

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
    for i, dork in enumerate(dorks[:6], 1):
        encoded = requests.utils.quote(dork)
        lines.append(f"  {i}. <a href='https://www.google.com/search?q={encoded}'>{dork[:50]}</a>")

    # ─── Direct Links ───
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔗 <b>روابط مباشرة:</b>")
    lines.append(f"  • <a href='{fp.get('whatsapp_direct', '#')}'>WhatsApp Direct</a>")
    lines.append(f"  • <a href='{fp.get('facebook_search', '#')}'>Facebook Search</a>")
    lines.append(f"  • <a href='{fp.get('truecaller_web', '#')}'>Truecaller Web</a>")
    lines.append(f"  • <a href='{fp.get('sync_me', '#')}'>Sync.me</a>")
    lines.append(f"  • <a href='{fp.get('mobiletracker', '#')}'>eMobileTracker</a>")

    return "\n".join(lines)
