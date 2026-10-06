"""
Deathlogs Pattern Analyzer for Reinos de Leyenda (RL)
Parses the 26 cached colored logs and extracts grammatical and semantic patterns
associated with colors, mapping them into structured colorizer rules.
"""

import os
import re
import json
from collections import defaultdict, Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COLORED_DIR = BASE_DIR / "cache_colored"
PLAIN_DIR = BASE_DIR / "cache_plain"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_color(color_str):
    if not color_str:
        return None
    color_str = color_str.strip().lower()
    # Check rgb(r, g, b)
    rgb_match = re.search(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_str)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    # Check hex
    if color_str.startswith('#'):
        if len(color_str) == 4:
            return f"#{color_str[1]*2}{color_str[2]*2}{color_str[3]*2}"
        return color_str[:7]
    return color_str


def parse_html_line(line_html):
    """
    Parses a single HTML line into a list of (text, color, extra_styles).
    Supports both <span style="..."> and <font color="...">.
    """
    # Replace <br /> with newline if inside line
    line_html = re.sub(r'<br\s*/?>', '', line_html)
    
    # Extract tags
    # Tokenize by HTML tags
    tokens = []
    # Pattern to match span or font tags and text
    tag_pattern = re.compile(r'(<span[^>]*>|<font[^>]*>|</span>|</font>|[^<]+)', re.IGNORECASE)
    
    current_color = None
    color_stack = []
    
    for match in tag_pattern.finditer(line_html):
        chunk = match.group(0)
        if not chunk:
            continue
            
        lower_chunk = chunk.lower()
        if lower_chunk.startswith('<span'):
            # extract style color
            style_match = re.search(r'color:\s*([^;"]+)', chunk, re.I)
            color = normalize_color(style_match.group(1)) if style_match else current_color
            color_stack.append(color)
            current_color = color
        elif lower_chunk.startswith('<font'):
            color_match = re.search(r'color=[\'"]?([^\'" >]+)', chunk, re.I)
            color = normalize_color(color_match.group(1)) if color_match else current_color
            color_stack.append(color)
            current_color = color
        elif lower_chunk in ('</span>', '</font>'):
            if color_stack:
                color_stack.pop()
            current_color = color_stack[-1] if color_stack else None
        else:
            # Plain text
            text = chunk
            # Unescape basic HTML entities
            text = text.replace('&nbsp;', ' ').replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
            if text:
                tokens.append((text, current_color or '#c0c0c0'))
                
    return tokens


def analyze_logs():
    files = list(COLORED_DIR.glob("*.html"))
    print(f"Analyzing {len(files)} colored log files...")
    
    color_counter = Counter()
    pattern_categories = {
        'prompt': [],
        'combat_player_hit': [],
        'combat_player_miss': [],
        'combat_enemy_hit': [],
        'combat_special_crit': [],
        'combat_death': [],
        'spells_chant': [],
        'spells_cast': [],
        'spells_effect': [],
        'movement': [],
        'room_exits': [],
        'channels': [],
        'system_exp': [],
        'system_lock': [],
        'system_info': [],
        'skills': [],
        'player_commands': []
    }
    
    # Store line examples with their token color breakdown
    category_samples = defaultdict(list)
    
    for file_path in files:
        html = file_path.read_text(encoding='utf-8')
        # Split lines by <br /> or newlines
        lines = re.split(r'<br\s*/?>|\n', html)
        
        for raw_line in lines:
            if not raw_line.strip():
                continue
            tokens = parse_html_line(raw_line)
            if not tokens:
                continue
                
            plain_line = "".join(t[0] for t in tokens).strip()
            if not plain_line:
                continue
                
            dominant_color = Counter(t[1] for t in tokens).most_common(1)[0][0]
            color_counter[dominant_color] += 1
            
            # Categorize by regex
            categorized = False
            
            # 1. Prompts
            if re.search(r'Pvs:\s*\d+/\d+', plain_line):
                category_samples['prompt'].append((plain_line, tokens))
                categorized = True
                
            # 2. Combat
            elif re.search(r'^(?:\*|#)?\s*(?:Tu|Muerdes|Pateas|Golpeas|Desgarras|Atraviesas|Clavas|Rajás|Cortas|Aplastas)\s+', plain_line, re.I):
                if 'esquiva tu ataque' in plain_line or 'fallas tu ataque' in plain_line or 'bloquea tu' in plain_line:
                    category_samples['combat_player_miss'].append((plain_line, tokens))
                else:
                    category_samples['combat_player_hit'].append((plain_line, tokens))
                categorized = True
                
            elif re.search(r'^(?:\*|#)?\s*[A-Z][a-z0-9\'-]+\s+te\s+(?:corta|desgarra|lacera|fustiga|clava|golpea|rasguña|entierra|muerde|patea|raja|aplasta|arremete)', plain_line):
                category_samples['combat_enemy_hit'].append((plain_line, tokens))
                categorized = True
                
            elif re.search(r'eviscera|desgarrador|boquete|cae al suelo sin vida|muerto|golpe mortal', plain_line, re.I):
                category_samples['combat_special_crit'].append((plain_line, tokens))
                categorized = True
                
            # 3. Spells
            elif 'Pronuncias el cántico:' in plain_line or 'Dices en ' in plain_line:
                category_samples['spells_chant'].append((plain_line, tokens))
                categorized = True
                
            elif 'Comienzas a formular el hechizo' in plain_line or 'formula un hechizo' in plain_line:
                category_samples['spells_cast'].append((plain_line, tokens))
                categorized = True
                
            elif re.search(r'^(?:¡Invocas|Un rayo de|Tu hechizo termina|Invocas fervientemente|Curas algunas)', plain_line):
                category_samples['spells_effect'].append((plain_line, tokens))
                categorized = True
                
            # 4. Movement & Exits
            elif re.search(r'\b(?:se va hacia|llega desde|huye hacia|se dirige a)\b', plain_line):
                category_samples['movement'].append((plain_line, tokens))
                categorized = True
                
            elif re.search(r'^\[(?:n|s|e|o|ne|no|se|so)(?:,[a-z]+)*\]$|Puedes ver (?:dos|tres|cuatro|[a-z]+) salidas:', plain_line):
                category_samples['room_exits'].append((plain_line, tokens))
                categorized = True
                
            # 5. Channels & Systems
            elif re.search(r'^\[[A-Za-z0-9_-]+\]\s+[A-Za-z0-9_-]+:', plain_line):
                category_samples['channels'].append((plain_line, tokens))
                categorized = True
                
            elif 'Obtienes' in plain_line and ('puntos de experiencia' in plain_line or 'puntos de gloria' in plain_line):
                category_samples['system_exp'].append((plain_line, tokens))
                categorized = True
                
            elif 'El bloqueo' in plain_line and 'termina' in plain_line:
                category_samples['system_lock'].append((plain_line, tokens))
                categorized = True
                
            elif plain_line.startswith('[INFO]:') or plain_line.startswith('[AYUDA]:') or plain_line.startswith('[Tiradas]'):
                category_samples['system_info'].append((plain_line, tokens))
                categorized = True
                
            elif re.search(r'^(?:Empiezas a|Intentas|Logras|Finalmente logras|Consigues zafarte)', plain_line):
                category_samples['skills'].append((plain_line, tokens))
                categorized = True

    print("\nTop colors detected across all logs:")
    for c, count in color_counter.most_common(12):
        print(f"  {c}: {count} occurrences")
        
    print("\nSamples collected per category:")
    for cat, samples in category_samples.items():
        print(f"  {cat}: {len(samples)} lines")
        
    # Write sample analysis summary
    summary_path = OUTPUT_DIR / "analysis_summary.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=== DEATHLOGS PATTERN ANALYSIS REPORT ===\n\n")
        for cat, samples in category_samples.items():
            f.write(f"--- CATEGORY: {cat.upper()} (Sample count: {len(samples)}) ---\n")
            for text, tokens in samples[:5]:
                f.write(f"Line: {text}\n")
                f.write(f"Tokens: {tokens}\n\n")
            f.write("\n")
            
    print(f"\nSaved analysis summary to: {summary_path}")
    return category_samples


if __name__ == '__main__':
    analyze_logs()
