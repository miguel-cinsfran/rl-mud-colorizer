"""
Deathlogs Extractor for Reinos de Leyenda (RL)
Downloads POV victory logs from sighted players for rule discovery,
and plain-text logs from blind players for benchmark validation.
"""

import os
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COLORED_DIR = BASE_DIR / "cache_colored"
PLAIN_DIR = BASE_DIR / "cache_plain"
BENCHMARK_DIR = BASE_DIR / "cache_benchmark"

COLORED_DIR.mkdir(parents=True, exist_ok=True)
PLAIN_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

SIGHTED_WHITELIST = ['Kunkh', 'Waka', 'Zirigg', 'Koch', 'Goemoe']
BLIND_PLAYERS = ['Enorthus', 'Zivrindyl', 'Genlae']


def fetch_url(url, retries=3, delay=0.4):
    time.sleep(delay)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt == retries - 1:
                print(f"[ERROR] Failed to fetch {url}: {e}")
                return None
            time.sleep(1.0)


def extract_pre_content(html):
    if not html:
        return None
    match = re.search(r'<PRE>(.*?)</PRE>', html, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None


def is_pov_log(player_name, log_html):
    """
    Checks if a log is from player_name's point of view.
    Rules:
    - If rival attacks player: 'rival te ataca' or '* rival te ...'
    - Player attacks rival: '* Tu golpe...' or 'Pronuncias el cántico...'
    - If the log repeatedly says '{player_name} te ataca', it's from the opponent's POV!
    """
    # Opponent POV check: "{player} te ataca" or "{player} te [daña]"
    opp_pattern = rf"\b{re.escape(player_name)}\s+te\s+(?:ataca|clava|golpea|corta|desgarra|lacera|fustiga|muerde)"
    if re.search(opp_pattern, log_html, re.IGNORECASE):
        return False
    
    # 2nd person indicators of own POV:
    own_indicators = [
        r"\bTu\s+(?:golpe|estocada|hechizo|ataque|corte|puñetazo|patada)\b",
        r"\bPronuncias\s+el\s+cántico\b",
        r"\bComienzas\s+a\s+formular\b",
        r"\bEstás\s+siendo\s+atacada?o?\b",
        r"\bConsigues\s+zafarte\b",
        r"\bPvs:\s*\d+/\d+\b"
    ]
    for ind in own_indicators:
        if re.search(ind, log_html, re.IGNORECASE):
            return True
            
    return True


def get_player_victories(player_name, max_logs=8):
    url = f"https://deathlogs.com/show_player.php?m_id=10&playername={urllib.parse.quote(player_name)}"
    html = fetch_url(url)
    if not html:
        return []
    
    # Find victory rows
    # Example: <td class=listlogs>Victory</td><td class=listlogs align=left><a href=list_log.php?m_id=10&l_id=57258>Killed  Theodric </a></td>
    pattern = r'<td class=(?:mostpoints|listlogs)>Victory</td>\s*<td[^>]*>\s*<a href=[\'"]?list_log\.php\?m_id=10&(?:amp;)?l_id=(\d+)[\'"]?>Killed\s+([^<]+)</a>'
    matches = re.findall(pattern, html, re.IGNORECASE)
    
    valid_logs = []
    for log_id, victims in matches:
        # Check if solo victory (no "with aid from")
        if 'with aid from' in victims.lower():
            continue
        valid_logs.append((log_id, victims.strip()))
        if len(valid_logs) >= max_logs:
            break
            
    print(f"[{player_name}] Found {len(valid_logs)} eligible solo victories (out of {len(matches)} total)")
    return valid_logs


def download_and_cache_log(log_id, player_name=None):
    colored_file = COLORED_DIR / f"{log_id}.html"
    plain_file = PLAIN_DIR / f"{log_id}.txt"
    
    if colored_file.exists() and plain_file.exists():
        colored_content = colored_file.read_text(encoding='utf-8')
        plain_content = plain_file.read_text(encoding='utf-8')
        return colored_content, plain_content
        
    url_colored = f"https://deathlogs.com/list_log.php?m_id=10&l_id={log_id}"
    url_plain = f"https://deathlogs.com/list_log.php?m_id=10&l_id={log_id}&clean=1"
    
    html_colored = fetch_url(url_colored)
    pre_colored = extract_pre_content(html_colored)
    
    if not pre_colored:
        print(f"[WARN] No PRE content in log {log_id}")
        return None, None
        
    if player_name and not is_pov_log(player_name, pre_colored):
        print(f"[SKIP] Log {log_id} is NOT from {player_name}'s POV")
        return None, None
        
    html_plain = fetch_url(url_plain)
    pre_plain = extract_pre_content(html_plain)
    
    # Save both
    colored_file.write_text(pre_colored, encoding='utf-8')
    if pre_plain:
        plain_file.write_text(pre_plain, encoding='utf-8')
    else:
        # Fallback: strip tags from pre_colored
        clean = re.sub(r'<br\s*/?>', '\n', pre_colored)
        clean = re.sub(r'<[^>]+>', '', clean)
        plain_file.write_text(clean, encoding='utf-8')
        
    print(f"[SAVED] Log {log_id} ({len(pre_colored)} bytes colored, {len(pre_plain or '')} bytes plain)")
    return pre_colored, pre_plain


def download_blind_sample(player_name, max_logs=4):
    url = f"https://deathlogs.com/show_player.php?m_id=10&playername={urllib.parse.quote(player_name)}"
    html = fetch_url(url)
    if not html:
        return
        
    pattern = r'href=[\'"]?list_log\.php\?m_id=10&(?:amp;)?l_id=(\d+)[\'"]?'
    log_ids = list(dict.fromkeys(re.findall(pattern, html, re.IGNORECASE)))
    
    count = 0
    for lid in log_ids:
        target = BENCHMARK_DIR / f"{player_name}_{lid}.txt"
        if target.exists():
            count += 1
            continue
            
        url_log = f"https://deathlogs.com/list_log.php?m_id=10&l_id={lid}"
        log_html = fetch_url(url_log)
        pre = extract_pre_content(log_html)
        if pre:
            clean = re.sub(r'<br\s*/?>', '\n', pre)
            clean = re.sub(r'<[^>]+>', '', clean)
            target.write_text(clean, encoding='utf-8')
            print(f"[BENCHMARK] Saved {target.name} ({len(clean)} chars)")
            count += 1
            if count >= max_logs:
                break


def run():
    print("=" * 60)
    print("STEP 1: Downloading Sighted Players Whitelist Victories (POV)")
    print("=" * 60)
    
    total_downloaded = 0
    for player in SIGHTED_WHITELIST:
        victories = get_player_victories(player, max_logs=6)
        for lid, victim in victories:
            colored, plain = download_and_cache_log(lid, player_name=player)
            if colored:
                total_downloaded += 1
                
    print(f"\nTotal training logs downloaded/verified: {total_downloaded}")
    
    print("\n" + "=" * 60)
    print("STEP 2: Downloading Blind Players Benchmark Logs")
    print("=" * 60)
    for player in BLIND_PLAYERS:
        download_blind_sample(player, max_logs=3)
        
    print("\nExtraction complete!")


if __name__ == '__main__':
    run()
