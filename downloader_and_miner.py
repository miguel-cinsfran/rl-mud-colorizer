"""
Download all solo victory logs for sighted whitelist players and extract rooms + colors.
"""
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COLORED_DIR = BASE_DIR / "cache_colored"
COLORED_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
WHITELIST = ['Waka', 'Kunkh', 'Zirigg', 'Koch', 'Goemoe', 'Velkyn', 'Thildarg']


def fetch_url(url, retries=3, delay=0.25):
    time.sleep(delay)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt == retries - 1:
                print(f"[ERROR] Failed {url}: {e}")
                return None
            time.sleep(1.0)


def extract_pre_content(html):
    if not html:
        return None
    match = re.search(r'<PRE>(.*?)</PRE>', html, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None


def get_player_solo_victories(player_name):
    url = f"https://deathlogs.com/show_player.php?m_id=10&playername={urllib.parse.quote(player_name)}"
    html = fetch_url(url, delay=0.3)
    if not html:
        return []
    pattern = r'<td class=(?:mostpoints|listlogs)>Victory</td>\s*<td[^>]*>\s*<a href=[\'"]?list_log\.php\?m_id=10&(?:amp;)?l_id=(\d+)[\'"]?>Killed\s+([^<]+)</a>'
    matches = re.findall(pattern, html, re.IGNORECASE)
    solo_victories = []
    for log_id, victims in matches:
        if 'with aid from' not in victims.lower():
            solo_victories.append((log_id, victims.strip()))
    return solo_victories


def download_all():
    print("=" * 60)
    print("PHASE 1: Downloading all solo victory logs for sighted whitelist")
    print("=" * 60)
    
    total_needed = 0
    downloaded_new = 0
    already_cached = 0
    
    for player in WHITELIST:
        victories = get_player_solo_victories(player)
        print(f"[{player}] Total solo victories on deathlogs: {len(victories)}")
        for log_id, victim in victories:
            total_needed += 1
            fpath = COLORED_DIR / f"{log_id}.html"
            if fpath.exists() and fpath.stat().st_size > 500:
                already_cached += 1
                continue
                
            url = f"https://deathlogs.com/list_log.php?m_id=10&l_id={log_id}"
            html = fetch_url(url, delay=0.25)
            pre = extract_pre_content(html)
            if pre:
                fpath.write_text(pre, encoding='utf-8')
                downloaded_new += 1
                if downloaded_new % 10 == 0:
                    print(f"  Downloaded {downloaded_new} new logs... (latest: {log_id})")
            else:
                print(f"  [WARN] No PRE content for log {log_id}")
                
    print(f"\nDownload summary: {downloaded_new} downloaded, {already_cached} already cached. Total: {total_needed}")


if __name__ == '__main__':
    download_all()
