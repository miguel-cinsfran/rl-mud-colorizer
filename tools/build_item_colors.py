"""Build item_colors.json from an item catalog with the game's color codes.

Usage: python tools/build_item_colors.py <items.json> [output.json]

The input is the catalog Franco extracts from the Armería de RL
(https://github.com/FrancoMPaniagua/rl-mud-colorizer, items.json): {name: {"raw_short": ...}},
where raw_short carries the game's codes ("%^BOLD%^BLUE%^Espada Azul%^RESET%^").
Output: {name: [[n_chars, "#rrggbb"], ...]}, the color runs over the name, using the colors
Mudlet shows, checked code by code against colored Mudlet logs: BOLD selects the bright
shade, ORANGE is the dark yellow, YELLOW is always bright, and BOLD alone stays silver.
Names that would stay plain silver are left out.

When the colored Mudlet logs of tools/fetch_reference_logs.py are in cache_reference/, an
item they show with other colors (the Armería can lag behind the game) takes the colors
seen there, if it was seen at least MIN_SEEN times after plain silver text and at least
DOMINANCE of those sightings agree.
"""

import json
from collections import Counter
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import ITEM_WORD_RE, item_index  # noqa: E402
from tools.evaluate import CACHE_DIR, line_text, parse_html_log  # noqa: E402

MIN_SEEN = 2
DOMINANCE = 0.8
# Items missing from the Armería whose colors are taken from the reference logs only.
EXTRA_NAMES = ["Bolsita para plantas", "Pin 'Yo escalé el Mallorn'"]
DEFAULT_OUT = ROOT / "item_colors.json"
SILVER = "#c0c0c0"

# (normal, bold) shades for each game color code.
PALETTE = {
    None: (SILVER, SILVER),
    "BLACK": ("#808080", "#808080"),
    "RED": ("#800000", "#ff0000"),
    "GREEN": ("#008000", "#00ff00"),
    "YELLOW": ("#ffff00", "#ffff00"),
    "ORANGE": ("#808000", "#ffff00"),
    "BLUE": ("#000080", "#0000ff"),
    "MAGENTA": ("#800080", "#ff00ff"),
    "CYAN": ("#008080", "#00ffff"),
    "WHITE": (SILVER, "#ffffff"),
}
CONTROL = {"BOLD", "NOBOLD", "RESET", "FLASH", "DIM"}


def name_runs(raw_short, name):
    """[[n, color], ...] for the leading `name` in raw_short, or None if it does not match."""
    color, bold, chars = None, False, []
    # Codes are delimited by "%^" and share delimiters: "%^BOLD%^RED%^Text".
    for part in raw_short.split("%^"):
        if part == "BOLD":
            bold = True
        elif part == "NOBOLD":
            bold = False
        elif part == "RESET":
            color, bold = None, False
        elif part in PALETTE:
            color = part
        elif part not in CONTROL:
            chars += [(ch, PALETTE[color][bold]) for ch in part]
    text = "".join(ch for ch, _ in chars)
    if not text.startswith(name):
        return None
    runs = []
    for ch, c in chars[:len(name)]:
        if runs and runs[-1][1] == c:
            runs[-1][0] += 1
        else:
            runs.append([1, c])
    return runs


def to_runs(colors):
    runs = []
    for c in colors:
        if runs and runs[-1][1] == c:
            runs[-1][0] += 1
        else:
            runs.append([1, c])
    return runs


def fix_mojibake(line):
    """Undo UTF-8 read as Latin-1 ("Ã©" -> "é") in a parsed line, keeping each char's color."""
    out, i = [], 0
    while i < len(line):
        ch, color = line[i]
        if ch in "ÃÂ" and i + 1 < len(line) and "" <= line[i + 1][0] <= "¿":
            try:
                out.append(((ch + line[i + 1][0]).encode("latin-1").decode("utf-8"), color))
                i += 2
                continue
            except UnicodeError:
                pass
        out.append((ch, color))
        i += 1
    return out


def reference_runs(table):
    """{name: runs} for items the reference logs always show, after silver text, with other colors."""
    index = item_index(table)
    seen = {}
    for path in sorted(CACHE_DIR.rglob("*.*")) if CACHE_DIR.exists() else []:
        for line in parse_html_log(path.read_text(encoding="utf-8", errors="replace")):
            line = fix_mojibake(line)
            text = line_text(line)
            for i in range(1, len(text)):
                if ITEM_WORD_RE.match(text[i - 1]) or line[i - 1][1] != SILVER:
                    continue
                for name in index.get(text[i:i + 4], ()):
                    end = i + len(name)
                    if text.startswith(name, i) and (end == len(text) or not ITEM_WORD_RE.match(text[end])):
                        # Spaces take the color of the run they follow, as in the runs we emit.
                        colors = []
                        for ch, c in line[i:end]:
                            colors.append(colors[-1] if ch.isspace() and colors else c)
                        seen.setdefault(name, []).append(json.dumps(to_runs(colors)))
                        break
    out = {}
    for name, variants in seen.items():
        top, n = Counter(variants).most_common(1)[0]
        if n >= MIN_SEEN and n / len(variants) >= DOMINANCE:
            runs = json.loads(top)
            if runs != table[name]:
                out[name] = runs
    return out


def main():
    src = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    catalog = json.loads(src.read_text(encoding="utf-8"))
    table, skipped = {}, 0
    for name, item in sorted(catalog.items()):
        runs = name_runs(item.get("raw_short", ""), name)
        if not runs or all(c == SILVER for _, c in runs) or len(name) < 4:
            skipped += 1
            continue
        table[name] = runs
    for name in EXTRA_NAMES:
        table.setdefault(name, None)
    fixed = reference_runs(table)
    table.update(fixed)
    table = {k: v for k, v in sorted(table.items()) if v and not all(c == SILVER for _, c in v)}
    out_path.write_text(json.dumps(table, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(table)} colored items kept, {skipped} skipped, {len(fixed)} corrected from Mudlet logs"
          f" ({', '.join(sorted(fixed))}) -> {out_path.name}")


if __name__ == "__main__":
    main()
