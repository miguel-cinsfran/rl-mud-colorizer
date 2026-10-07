"""Score RLColorizer output against colored Mudlet reference logs (cache_reference/).

Usage: python tools/evaluate.py [--players Naghig Kunkh] [--top 40] [--json out.json]
"""

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import RLColorizer  # noqa: E402

CACHE_DIR = ROOT / "cache_reference"
DEFAULT_PLAYERS = ["Naghig", "Kunkh"]
TAG_RE = re.compile(r"(<[^>]*>)")
RGB_RE = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", re.I)
HEX_RE = re.compile(r"#([0-9a-f]{6})\b", re.I)
STYLE_COLOR_RE = re.compile(r"(?<![-\w])color\s*:\s*([^;\"']+)", re.I)
FONT_COLOR_RE = re.compile(r"<font[^>]*\bcolor\s*=\s*[\"']?([^\"'\s>]+)", re.I)
NAME_RE = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?=\W*$)")


def normalize_color(value):
    """rgb(r,g,b) or #rrggbb -> lowercase #rrggbb; None if unrecognized."""
    if not value:
        return None
    m = RGB_RE.search(value)
    if m:
        return "#%02x%02x%02x" % tuple(min(255, int(g)) for g in m.groups())
    m = HEX_RE.search(value)
    if m:
        return "#" + m.group(1).lower()
    return None


# Colors that a sighted player cannot tell apart count as equal when scoring.
# Each pair maps a shade to its canonical form; add a pair only if the shades are
# visually near-identical on a black background.
COLOR_EQUIVALENTS = {
    # Mudlet's default foreground (204,204,204) vs the standard silver (192,192,192) we emit.
    "#cccccc": "#c0c0c0",
    # Pure blue (0,0,255) vs the (8,0,255) blue used by our rules: 8/255 on one channel.
    "#0800ff": "#0000ff",
}


def canon(color):
    return COLOR_EQUIVALENTS.get(color, color)


def parse_html_log(text, default_color="#c0c0c0"):
    """Parse a Mudlet-style HTML log into lines; each line is a list of (char, color)."""
    start = 0
    m = re.search(r"<pre", text, re.I) or re.search(r"<body", text, re.I)
    if m:
        start = m.start()
    end = len(text)
    m = re.search(r"</pre", text[start:], re.I)
    if m:
        end = start + m.start()
    segment = text[start:end]

    font = FONT_COLOR_RE.search(segment)
    base = (normalize_color(font.group(1)) if font else None) or default_color

    lines = [[]]
    stack = []
    for token in TAG_RE.split(segment):
        if not token:
            continue
        if token.startswith("<"):
            low = token.lower()
            if re.match(r"<br\b", low):
                lines.append([])
            elif re.match(r"<span\b", low):
                sm = STYLE_COLOR_RE.search(token)
                inherited = stack[-1] if stack else base
                stack.append((normalize_color(sm.group(1)) if sm else None) or inherited)
            elif low.startswith("</span") and stack:
                stack.pop()
            continue
        color = stack[-1] if stack else base
        for ch in html.unescape(token).replace("\xa0", " ").replace("\r", "").replace("\n", ""):
            lines[-1].append((ch, color))
    # A trailing <br /> and the closing markup leave blank tail lines; drop them.
    while lines and not line_has_content(lines[-1]):
        lines.pop()
    return lines


def line_text(line):
    return "".join(ch for ch, _ in line)


def line_has_content(line):
    return any(not ch.isspace() for ch, _ in line)


def score_line(expected, got):
    """Return (scored_chars, strict_correct, equivalent_correct, confusion Counter), whitespace ignored.

    The confusion counter only holds mismatches that survive the color equivalences.
    """
    total = strict = equiv = 0
    confusion = Counter()
    for (ch, exp), (_, act) in zip(expected, got):
        if ch.isspace():
            continue
        total += 1
        if exp == act:
            strict += 1
            equiv += 1
        elif canon(exp) == canon(act):
            equiv += 1
        else:
            confusion[(exp, act)] += 1
    return total, strict, equiv, confusion


def segments(line):
    """Compact `[#color]text` form; whitespace never starts a new segment."""
    out = []
    cur = None
    for ch, color in line:
        if ch.isspace() and cur is not None:
            out[-1][1].append(ch)
            continue
        if color != cur:
            out.append((color, []))
            cur = color
        out[-1][1].append(ch)
    return "".join(f"[{c}]{''.join(chars)}" for c, chars in out)


def line_shape(text):
    """Digits -> N; capitalized words (except the first word) -> X."""
    words = re.sub(r"\d+", "N", text.strip()).split(" ")
    return " ".join(w if i == 0 else NAME_RE.sub("X", w) for i, w in enumerate(words))


def collapse_blank_runs(lines):
    """Keep at most one consecutive blank line, mirroring the engine's newline collapsing."""
    out = []
    for line in lines:
        if not line_has_content(line) and out and not line_has_content(out[-1]):
            continue
        out.append(line)
    return out


def has_custom_base_color(lines):
    """True when most of the text is one color other than silver: the player changed Mudlet's
    default foreground (some use green), so the log says nothing about the game's colors."""
    counts = Counter(color for line in lines for ch, color in line if not ch.isspace())
    if not counts:
        return False
    color, n = counts.most_common(1)[0]
    return canon(color) != "#c0c0c0" and n >= 0.5 * sum(counts.values())


def evaluate_log(colorizer, ref_html):
    """Colorize the plain text of one reference log; fall back to no preprocessing if lines are lost."""
    ref_lines = collapse_blank_runs(parse_html_log(ref_html, default_color="#cccccc"))
    plain = "\n".join(line_text(l).rstrip() for l in ref_lines)
    fallback = False
    got_lines = parse_html_log(colorizer.colorize_text(plain, preprocess=True))
    if len(got_lines) != len(ref_lines):
        fallback = True
        got_lines = parse_html_log(colorizer.colorize_text(plain, preprocess=False))
    return {"ref": ref_lines, "got": got_lines, "fallback": fallback}


class Stats:
    def __init__(self):
        self.chars = self.correct = self.eq_correct = 0
        self.lines = self.exact = self.eq_exact = 0
        self.misaligned = 0
        self.logs = self.fallbacks = self.unaligned_logs = 0
        self.custom_base = 0
        self.confusion = Counter()
        self.shapes = {}
        self.text_diffs = {}

    def add_log(self, result):
        self.logs += 1
        ref, got = result["ref"], result["got"]
        self.fallbacks += result["fallback"]
        if len(ref) != len(got):
            self.unaligned_logs += 1
            self.misaligned += len(ref)
            return
        for r, g in zip(ref, got):
            if line_text(r).rstrip() != line_text(g).rstrip():
                self.misaligned += 1
                key = (line_shape(line_text(r)), line_shape(line_text(g)))
                entry = self.text_diffs.setdefault(key, {"count": 0, "example": (line_text(r).rstrip(), line_text(g).rstrip())})
                entry["count"] += 1
                continue
            if not line_has_content(r):
                continue
            total, strict, equiv, conf = score_line(r, g)
            self.chars += total
            self.correct += strict
            self.eq_correct += equiv
            self.lines += 1
            self.exact += total == strict
            self.eq_exact += total == equiv
            self.confusion.update(conf)
            if total != equiv:
                entry = self.shapes.setdefault(
                    line_shape(line_text(r)), {"count": 0, "example": (segments(r), segments(g))})
                entry["count"] += 1

    def summary(self):
        return {
            "logs": self.logs,
            "fallback_logs": self.fallbacks,
            "unaligned_logs": self.unaligned_logs,
            "misaligned_lines": self.misaligned,
            "scored_lines": self.lines,
            "scored_chars": self.chars,
            "char_accuracy_strict": self.correct / self.chars if self.chars else 0.0,
            "line_exact_rate_strict": self.exact / self.lines if self.lines else 0.0,
            "char_accuracy": self.eq_correct / self.chars if self.chars else 0.0,
            "line_exact_rate": self.eq_exact / self.lines if self.lines else 0.0,
        }


def pct(x):
    return f"{100 * x:.2f}%"


def print_summary(label, stats):
    s = stats.summary()
    print(f"{label}: logs={s['logs']} scored_lines={s['scored_lines']} scored_chars={s['scored_chars']} "
          f"char_accuracy={pct(s['char_accuracy'])} (strict {pct(s['char_accuracy_strict'])}) "
          f"line_exact_match={pct(s['line_exact_rate'])} (strict {pct(s['line_exact_rate_strict'])}) "
          f"misaligned_lines={s['misaligned_lines']} unaligned_logs={s['unaligned_logs']} "
          f"preprocess_fallback_logs={s['fallback_logs']} custom_base_color_logs_skipped={stats.custom_base}")


def run(players, cache_dir=CACHE_DIR):
    colorizer = RLColorizer()
    per_player = {}
    overall = Stats()
    for player in players:
        stats = Stats()
        for path in sorted((Path(cache_dir) / player).glob("*.html"), key=lambda p: p.name):
            text = path.read_text(encoding="utf-8", errors="replace")
            if has_custom_base_color(parse_html_log(text)):
                stats.custom_base += 1
                overall.custom_base += 1
                continue
            result = evaluate_log(colorizer, text)
            stats.add_log(result)
            overall.add_log(result)
        per_player[player] = stats
    return overall, per_player


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--players", nargs="+", default=DEFAULT_PLAYERS)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--json", help="write full results to this JSON file")
    args = ap.parse_args(argv)

    overall, per_player = run(args.players)
    if not overall.logs:
        print("No reference logs found. Run: python tools/fetch_reference_logs.py")
        return 1

    print_summary("OVERALL", overall)
    for player, stats in per_player.items():
        print_summary(player, stats)

    print(f"\nTop {args.top} color confusions (expected -> got, characters; equivalent shades excluded):")
    for (exp, act), n in overall.confusion.most_common(args.top):
        print(f"{exp} -> {act}: {n}")

    print(f"\nTop {args.top} failing line shapes:")
    ranked = sorted(overall.shapes.items(), key=lambda kv: -kv[1]["count"])[: args.top]
    for i, (shape, entry) in enumerate(ranked, 1):
        print(f"{i}. x{entry['count']} shape: {shape}")
        print(f"   expected: {entry['example'][0]}")
        print(f"   got:      {entry['example'][1]}")

    print(f"\nTop {min(args.top, 15)} lines whose visible text differs (not scored):")
    diffs = sorted(overall.text_diffs.values(), key=lambda v: -v["count"])[: min(args.top, 15)]
    for i, entry in enumerate(diffs, 1):
        print(f"{i}. x{entry['count']}")
        print(f"   reference: {entry['example'][0]}")
        print(f"   ours:      {entry['example'][1]}")

    if args.json:
        data = {
            "overall": overall.summary(),
            "players": {p: s.summary() for p, s in per_player.items()},
            "confusion": [{"expected": e, "got": g, "chars": n} for (e, g), n in overall.confusion.most_common()],
            "text_diffs": [{"count": v["count"], "reference": v["example"][0], "ours": v["example"][1]}
                           for v in sorted(overall.text_diffs.values(), key=lambda v: -v["count"])],
            "shapes": [{"shape": s, "count": v["count"], "expected": v["example"][0], "got": v["example"][1]}
                       for s, v in sorted(overall.shapes.items(), key=lambda kv: -kv[1]["count"])],
        }
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
