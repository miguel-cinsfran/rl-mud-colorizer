"""Build room_reference_colors.json from the colored Mudlet logs in cache_reference/.

Usage: python tools/extract_reference_rooms.py [output.json]

A room title followed by its exits ("Campos de Cultivo [ne,o]") is recorded with the
colors the game actually sent, which can change inside the title ("Campos de " silver,
"Cultivo" yellow). Output:
  {"names": {normalized title: [[n_chars, "#rrggbb"], ...]},  runs covering the whole title
   "zones": {zone prefix: "#rrggbb"}}                          color of the part before ":" or " - "
A title is kept when at least DOMINANCE of its (at least MIN_SEEN) sightings agree, so a
player with a customized palette cannot decide it; a zone when at least MIN_ZONE_TITLES
different titles agree on it and no title disagrees.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evaluate import CACHE_DIR, line_text, parse_html_log  # noqa: E402
from tools.extract_map_colors import normalize_title  # noqa: E402

DEFAULT_OUT = ROOT / "room_reference_colors.json"
MIN_SEEN = 2
DOMINANCE = 0.8
MIN_ZONE_TITLES = 2
DIRS = r"(?:n|s|e|o|ne|no|se|so|ar|ab|dentro|fuera)"
TITLE_EXITS_RE = re.compile(r"^([A-ZÁÉÍÓÚÑÜ][^\[\]<>]*?) \[\|?" + DIRS + r"\|?(?:,\|?" + DIRS + r"\|?)*\]\s*$")


def title_runs(chars):
    """[[n, color], ...] for the title characters; spaces join the run they follow."""
    runs = []
    for ch, color in chars:
        if runs and (ch.isspace() or runs[-1][1] == color):
            runs[-1][0] += 1
        else:
            runs.append([1, color])
    return runs


def zone_of(title):
    """(normalized zone, raw prefix length) for "Zone: room" or "Zone - room", else None."""
    for sep in (":", "-"):
        if sep in title:
            prefix = title[:title.index(sep)].rstrip()
            if prefix:
                return normalize_title(prefix), len(prefix)
    return None


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    seen = defaultdict(lambda: defaultdict(int))
    zones = defaultdict(lambda: defaultdict(set))
    for path in sorted(CACHE_DIR.rglob("*.html")):
        for line in parse_html_log(path.read_text(encoding="utf-8", errors="replace")):
            m = TITLE_EXITS_RE.match(line_text(line))
            if not m:
                continue
            title = m.group(1).rstrip()
            runs = title_runs(line[:len(title)])
            seen[normalize_title(title)][json.dumps(runs)] += 1
            zone = zone_of(title)
            if zone and runs[0][0] >= zone[1]:
                zones[zone[0]][runs[0][1]].add(normalize_title(title))
    table = {}
    for title, variants in sorted(seen.items()):
        runs, n = max(variants.items(), key=lambda kv: (kv[1], kv[0]))
        if n >= MIN_SEEN and n / sum(variants.values()) >= DOMINANCE:
            table[title] = json.loads(runs)
    zone_table = {}
    for zone, colors in sorted(zones.items()):
        if len(colors) == 1:
            (color, titles), = colors.items()
            if len(titles) >= MIN_ZONE_TITLES:
                zone_table[zone] = color
    out = {"names": table, "zones": zone_table}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(seen)} títulos de sala vistos, {len(table)} con colores claros y {len(zone_table)} zonas."
          f" Guardado en {out_path.name}.")


if __name__ == "__main__":
    main()
