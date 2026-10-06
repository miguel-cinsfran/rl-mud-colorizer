"""Build room_map_colors.json from a Mudlet map export (JSON).

Usage: python tools/extract_map_colors.py <map_export.json> [output.json]

Output: {"names": {normalized room name: "#rrggbb"}, "zones": {zone prefix: "#rrggbb"}}
Only the dominant color of each name is kept, and only when it covers at least
DOMINANCE of the rooms sharing that name (same rule for zones, keyed by the
prefix before ":"). Room userData is ignored entirely.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DOMINANCE = 0.80
NO_TERRAIN = (255, 255, 255)
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "room_map_colors.json"

# Mudlet's built-in environment colors (ids 1-16) when not overridden by customEnvColors.
STANDARD_ENV = {
    1: (128, 0, 0), 2: (0, 128, 0), 3: (128, 128, 0), 4: (0, 0, 128),
    5: (128, 0, 128), 6: (0, 128, 128), 7: (192, 192, 192), 8: (128, 128, 128),
    9: (255, 0, 0), 10: (0, 255, 0), 11: (255, 255, 0), 12: (0, 0, 255),
    13: (255, 0, 255), 14: (0, 255, 255), 15: (255, 255, 255), 16: (128, 128, 128),
}


def normalize_title(title):
    """Same normalization as RLColorizer.get_room_color (plus trailing "[exits]" removal)."""
    title = re.sub(r"\s*\[[^\]]*\]\s*$", "", title)
    clean = re.sub(r"\s+", " ", re.sub(r"\s*-\s*", " - ", title)).strip().lower()
    return re.sub(r"\s*:\s*", ": ", clean)


def dominant(counter):
    color, n = counter.most_common(1)[0]
    return color if n / sum(counter.values()) >= DOMINANCE else None


def extract(map_data):
    env = dict(STANDARD_ENV)
    for entry in map_data.get("customEnvColors", []):
        env[entry["id"]] = tuple(entry["color24RGB"][:3])

    by_name = defaultdict(Counter)
    by_zone = defaultdict(Counter)
    for area in map_data.get("areas", []):
        for room in area.get("rooms", []):
            name = room.get("name")
            rgb = env.get(room.get("environment"))
            # White is what the mapper leaves on rooms without a terrain: no data.
            if not name or rgb is None or rgb == NO_TERRAIN:
                continue
            key = normalize_title(name)
            if not key:
                continue
            color = "#%02x%02x%02x" % rgb
            by_name[key][color] += 1
            if ":" in key:
                by_zone[key.split(":")[0].strip()][color] += 1

    names = {k: c for k, v in sorted(by_name.items()) if (c := dominant(v))}
    zones = {k: c for k, v in sorted(by_zone.items()) if k and (c := dominant(v))}
    return {"names": names, "zones": zones}


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    with open(argv[1], encoding="utf-8") as f:
        result = extract(json.load(f))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        f.write("\n")
    print(f"{len(result['names'])} names, {len(result['zones'])} zones -> {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
