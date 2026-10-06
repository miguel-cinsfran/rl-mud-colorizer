"""
Mines all room names and their colors from 136 sighted logs and 26 accessibility logs.
Extracts full room titles (before [exits] or (exits)) supporting both <font color> and <span style="color">.
"""
import re
import html
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent
COLORED_DIR = BASE_DIR / "cache_colored"
ACC_DIR = BASE_DIR / "accessibility_logs"

NAMED_COLORS = {
    'green': '#008000',
    'darkgreen': '#008000',
    'yellow': '#ffff00',
    'cyan': '#00ffff',
    'blue': '#0000ff',
    'red': '#ff0000',
    'white': '#ffffff',
    'gray': '#808080',
    'grey': '#808080',
    'magenta': '#ff00ff',
    'teal': '#008080',
    'silver': '#c0c0c0',
}


def normalize_color(col_str):
    if not col_str:
        return "#008000"
    col_str = col_str.strip().lower()
    if col_str in NAMED_COLORS:
        return NAMED_COLORS[col_str]
    m_rgb = re.search(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', col_str)
    if m_rgb:
        r, g, b = int(m_rgb.group(1)), int(m_rgb.group(2)), int(m_rgb.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    if col_str.startswith('#'):
        if len(col_str) == 4:
            return f"#{col_str[1]*2}{col_str[2]*2}{col_str[3]*2}"
        if col_str == '#008888':
            return '#008080'
        return col_str[:7]
    return "#008000"


def clean_room_name(raw_name):
    t = re.sub(r'<[^>]+>', '', raw_name)
    t = html.unescape(t)
    t = re.sub(r'.*extract from Reinos de Leyenda profile\s*', '', t, flags=re.I)
    t = re.sub(r'\[Viajar aqu[íi]\]\s*:\s*', '', t, flags=re.I)
    t = re.sub(r'^\s*[\d\w:.-]*\s*[>\]]\s*', '', t)
    t = re.sub(r'^\s*\d+\s*', '', t)
    t = re.sub(r'^[>\]]\s*', '', t)
    t = re.sub(r'\s*-\s*', ' - ', t)
    t = re.sub(r'\s*:\s*', ': ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


tag_token_re = re.compile(r'(<[^>]+>|[^<]+)')
color_attr_re = re.compile(r'(?:color=[\'\"]?([^\'\"\s>]+)[\'\"]?|color:\s*([^;\'\"\s>]+))', re.I)
exit_regex = re.compile(r'[\[\(]([a-zA-ZáéíóúÁÉÍÓÚ,\|\s-]+)[\]\)]')
valid_dirs = {'n', 's', 'e', 'o', 'ne', 'no', 'se', 'so', 'ar', 'ab', 'arriba', 'abajo', 'norte', 'sur', 'este', 'oeste', 'sudoeste', 'sudeste', 'noreste', 'noroeste', 'entrar', 'salir', 'subir', 'bajar'}


def parse_styled_spans(chunk_html):
    color_stack = []
    spans = []
    for token in tag_token_re.findall(chunk_html):
        if token.startswith('<'):
            if token.startswith('</'):
                if color_stack:
                    color_stack.pop()
            elif token.startswith('<font') or token.startswith('<span'):
                m = color_attr_re.search(token)
                if m:
                    col = normalize_color(m.group(1) or m.group(2))
                    color_stack.append(col)
                else:
                    color_stack.append(color_stack[-1] if color_stack else None)
        else:
            text = html.unescape(token)
            if text:
                spans.append((color_stack[-1] if color_stack else None, text))
    return spans


def mine_rooms():
    html_files = sorted(COLORED_DIR.glob("*.html"))
    print(f"Mining rooms from {len(html_files)} sighted HTML logs...")

    room_colors = {} # canonical_name_lower -> Counter(colors)
    room_casing = {} # canonical_name_lower -> canonical_name

    for f in html_files:
        content = f.read_text(encoding='utf-8')
        chunks = re.split(r'<br\s*/?>|\n', content)
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or ('[' not in chunk and '(' not in chunk):
                continue
            m_exit = exit_regex.search(chunk)
            if not m_exit:
                continue
            exits_raw = m_exit.group(1).strip()
            exit_tokens = [x.strip('|- ') for x in exits_raw.split(',')]
            if not any(t.lower() in valid_dirs for t in exit_tokens if t):
                continue

            before_exits_html = chunk[:m_exit.start()]
            full_title = clean_room_name(before_exits_html)

            if len(full_title) < 4 or len(full_title) > 90:
                continue
            if full_title.endswith(':') or '->' in full_title or '- >' in full_title or full_title.lower() == 'sl':
                continue
            if any(w in full_title.lower() for w in ['obtienes', 'puntos de', 'experiencia', 'daña', 'golpea', 'ataca', 'pvs:', 'hp:', 'dices en', 'bloqueo', 'salidas']):
                continue

            spans = parse_styled_spans(before_exits_html)
            room_color = None
            for col, txt in spans:
                letters = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜËë]', '', txt)
                if len(letters) >= 3 and col:
                    room_color = col
                    break
            if not room_color:
                room_color = '#008000'

            key = full_title.lower()
            room_colors.setdefault(key, Counter())[room_color] += 1
            room_casing[key] = full_title

    sighted_count = len(room_colors)
    print(f"Extracted {sighted_count} unique room titles from sighted logs!")

    # Also parse accessibility logs for extra room names
    acc_files = sorted(ACC_DIR.glob("*.txt"))
    acc_count = 0
    for f in acc_files:
        lines = f.read_text(encoding='utf-8', errors='replace').splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = exit_regex.search(line)
            if m and (line.endswith(']') or line.endswith('] ') or line.endswith(')') or line.endswith(') ')):
                exits_raw = m.group(1).strip()
                exit_tokens = [x.strip('|- ') for x in exits_raw.split(',')]
                if not any(t.lower() in valid_dirs for t in exit_tokens if t):
                    continue
                before_exits = line[:m.start()]
                full_title = clean_room_name(before_exits)
                if len(full_title) < 4 or len(full_title) > 90:
                    continue
                if full_title.endswith(':') or '->' in full_title or '- >' in full_title or full_title.lower() == 'sl':
                    continue
                if any(w in full_title.lower() for w in ['obtienes', 'puntos de', 'experiencia', 'daña', 'golpea', 'ataca', 'pvs:', 'hp:', 'dices en', 'bloqueo', 'salidas']):
                    continue
                key = full_title.lower()
                if key not in room_colors:
                    room_colors[key] = Counter({'#008000': 1})
                    room_casing[key] = full_title
                    acc_count += 1

    print(f"Added {acc_count} extra rooms from accessibility logs!")
    print(f"Total catalog: {len(room_colors)} unique rooms!")

    catalog = {}
    for key, counter in room_colors.items():
        canonical_name = room_casing[key]
        best_color, count = counter.most_common(1)[0]
        catalog[canonical_name] = best_color

    out_file = BASE_DIR / "rooms.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(catalog)} rooms to {out_file}")

    print("\nColor distribution:")
    for col, cnt in Counter(catalog.values()).most_common():
        print(f"  {col}: {cnt} rooms")

    print("\nSample rooms from catalog (first 30):")
    for r, col in sorted(list(catalog.items()))[:30]:
        print(f"  {r:<50} -> {col}")


if __name__ == '__main__':
    mine_rooms()
