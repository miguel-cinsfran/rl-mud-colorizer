"""Build item_colors.json from the Armería de RL (https://armeria.reinosdeleyenda.es).

Usage: python tools/build_item_colors.py [--from raw.json] [output.json]

Without --from, the whole catalog is downloaded from the Armería's public API, one page of
PAGE_SIZE items at a time with a short pause between pages, and saved to RAW_CACHE (git
ignores it) so --from RAW_CACHE can rebuild without downloading again.

Each item's "short" carries the game's color codes ("%^BOLD%^BLUE%^Espada Azul%^RESET%^").
Output: {name: [[n_chars, "#rrggbb"], ...]}, the color runs over the name, using the colors
Mudlet shows, checked code by code against colored Mudlet logs: BOLD selects the bright
shade, ORANGE is the dark yellow, YELLOW is always bright, and BOLD alone stays silver.
The name drops a trailing note like "( Izquierdo )". Left out: names that would stay plain
silver, and one-word names unless written joined ("RobaAlmas"), since "Agua" or "Perla"
are everyday words. A name with several versions keeps the most common one.

When the colored Mudlet logs of tools/fetch_reference_logs.py are in cache_reference/, an
item they show with other colors (the Armería can lag behind the game) takes the colors
seen there, if it was seen at least MIN_SEEN times after plain silver text and at least
DOMINANCE of those sightings agree.
"""

import json
import re
import sys
import time
import urllib.request
from collections import Counter
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
RAW_CACHE = ROOT / "cache_armeria" / "items.json"
API_URL = "https://armeria.reinosdeleyenda.es/api/items?limit={limit}&offset={offset}"
PAGE_SIZE = 100
PAUSE_SECONDS = 0.5
JOINED_WORD_RE = re.compile(r"[a-záéíóúñü][A-ZÁÉÍÓÚÑÜ]")
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


def decode(raw_short):
    """[(char, color), ...] for the text of raw_short, as Mudlet shows it."""
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
    return chars


def name_runs(raw_short, name):
    """[[n, color], ...] for the leading `name` in raw_short, or None if it does not match."""
    chars = decode(raw_short)
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
        if ch in "\xc3\xc2" and i + 1 < len(line) and "\x80" <= line[i + 1][0] <= "\xbf":
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


def download():
    items, offset = [], 0
    while True:
        req = urllib.request.Request(API_URL.format(limit=PAGE_SIZE, offset=offset),
                                     headers={"User-Agent": "rl-mud-colorizer"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.load(resp)
        items += page["data"]
        print(f"  {len(items)} / {page['meta']['total']}")
        if not page["data"] or len(items) >= page["meta"]["total"]:
            return items
        offset += PAGE_SIZE
        time.sleep(PAUSE_SECONDS)


def item_name(raw_short):
    """The display name: the decoded text without a trailing "( Izquierdo )" note."""
    text = "".join(ch for ch, _ in decode(raw_short)).strip()
    return re.sub(r"\s*\([^)]*\)$", "", text).strip()


def build_table(items):
    """{name: runs} for the colored items, plus the number of colored shorts left out."""
    versions = {}
    for item in items:
        short = (item.get("short") or "").strip()
        if "%^" in short:
            versions.setdefault(item_name(short), Counter())[short] += 1
    table, skipped = {}, 0
    for name, shorts in sorted(versions.items()):
        # Most common version first; ties go to the longest, then alphabetical, so it is stable.
        short = sorted(shorts.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[0][0]
        runs = name_runs(short.lstrip(), name)
        one_word = " " not in name and not JOINED_WORD_RE.search(name)
        if not runs or all(c == SILVER for _, c in runs) or len(name) < 4 or one_word or "  " in name:
            skipped += 1
            continue
        table[name] = runs
    return table, skipped


def main():
    args = sys.argv[1:]
    if args[:1] == ["--from"]:
        items = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        args = args[2:]
    else:
        print("Downloading the Armería catalog...")
        items = download()
        RAW_CACHE.parent.mkdir(exist_ok=True)
        RAW_CACHE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    out_path = Path(args[0]) if args else DEFAULT_OUT
    table, skipped = build_table(items)
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
