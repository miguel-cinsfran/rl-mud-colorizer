import urllib.request
import urllib.parse
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ACC_DIR = BASE_DIR / "accessibility_logs"
ACC_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

ENORTHUS_SOLO = ['55693', '56207', '56212', '57195', '57197', '57232', '57298', '57317']
GENLAE_SOLO = [
    '54151', '54153', '54158', '54169', '54175', '54190', '54198', '54225',
    '54260', '54351', '54364', '54452', '54461', '54512', '54518', '54988',
    '55267', '57125'
]

def fetch_url(url, retries=3):
    time.sleep(0.3)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error fetching {url}: {e}")
                return None
            time.sleep(1.0)

def extract_pre(html):
    if not html:
        return ""
    m = re.search(r'<PRE>(.*?)</PRE>', html, re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else ""

def check_log(lid, player):
    url = f"https://deathlogs.com/list_log.php?m_id=10&l_id={lid}"
    html = fetch_url(url)
    pre = extract_pre(html)
    
    if not pre:
        return False, "No <PRE> content"
        
    # Check if accessibility log: does the PRE content have color tags?
    # In Deathlogs, colored logs use <span style="color: ..."> or <font color="...">
    color_spans = re.findall(r'<span\s+style=[\'"]?color:|font\s+color=', pre, re.IGNORECASE)
    has_colors = len(color_spans) > 5
    
    # Check POV:
    # If the victim is attacking player, e.g. "te ataca"
    # Or player has prompt: "Pvs: ...", player attacks: "Tu ...", "Dices:"
    # Opponent attacking player: "{player} te ataca" -> would mean OPPONENT'S POV!
    opp_pov = bool(re.search(rf"\b{re.escape(player)}\s+te\s+(?:ataca|clava|golpea|corta|desgarra|muerde)\b", pre, re.IGNORECASE))
    
    # First person indicators:
    has_first_person = bool(re.search(r'\b(?:Pvs:\s*\d+|Tu\s+(?:ataque|estocada|golpe|hechizo)|Pronuncias\s+el\s+cántico|Comienzas\s+a\s+formular|Dices(?:\s+en\s+[a-z]+)?:|Estás\s+siendo\s+atacado)\b', pre, re.IGNORECASE))
    
    if opp_pov:
        return False, f"Opponent POV (says '{player} te ...')"
        
    if not has_first_person:
        return False, "No first-person indicators found"
        
    if has_colors:
        return False, f"Has colors ({len(color_spans)} color tags found) - NOT accessibility mode"
        
    # Strip any minor residual HTML like <br />
    plain_text = re.sub(r'<br\s*/?>', '\n', pre)
    plain_text = re.sub(r'<[^>]+>', '', plain_text)
    plain_text = re.sub(r'&gt;', '>', plain_text)
    plain_text = re.sub(r'&lt;', '<', plain_text)
    plain_text = re.sub(r'&amp;', '&', plain_text)
    
    # Save valid plain text log
    target_file = ACC_DIR / f"{player}_{lid}.txt"
    target_file.write_text(plain_text, encoding='utf-8')
    
    return True, f"Valid accessibility log ({len(plain_text.splitlines())} lines, saved to {target_file.name})"

print("=== CHECKING ENORTHUS SOLO VICTORIES ===")
valid_enorthus = []
for lid in ENORTHUS_SOLO:
    ok, reason = check_log(lid, 'Enorthus')
    print(f"[{'VALID' if ok else 'SKIP '}] Enorthus Log {lid}: {reason}")
    if ok:
        valid_enorthus.append(lid)

print("\n=== CHECKING GENLAE SOLO VICTORIES ===")
valid_genlae = []
for lid in GENLAE_SOLO:
    ok, reason = check_log(lid, 'Genlae')
    print(f"[{'VALID' if ok else 'SKIP '}] Genlae Log {lid}: {reason}")
    if ok:
        valid_genlae.append(lid)

print(f"\nSummary:")
print(f"Enorthus valid accessibility logs: {len(valid_enorthus)} -> {valid_enorthus}")
print(f"Genlae valid accessibility logs: {len(valid_genlae)} -> {valid_genlae}")
