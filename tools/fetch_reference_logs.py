"""Download colored Mudlet reference logs from Deathlogs into cache_reference/<player>/<l_id>.html.

With --recent, the logs on the front page of the RL list (the latest 50) go to
cache_reference/recent/ instead, skipping zMUD logs (<font> markup, not Mudlet's colors),
logs already cached under another folder, and the logs made with this tool (OWN_UPLOADS):
Deathlogs stores them exactly like Mudlet's, and comparing against our own output would
only prove we agree with ourselves. Add every upload made with this tool to OWN_UPLOADS.
"""

import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache_reference"
BASE_URL = "https://deathlogs.com/"
USER_AGENT = "rl-mud-colorizer-reference-fetcher/1.0 (accessibility tooling; polite, cached)"
DEFAULT_PLAYERS = ["Naghig", "Kunkh"]
RECENT = "recent"
OWN_UPLOADS = {"57323", "57324", "57325"}
MUDLET_SPAN_RE = re.compile(r'<span style="color: ?rgb', re.I)
FONT_RE = re.compile(r"<font", re.I)
LOG_LINK_RE = re.compile(r"""list_log\.php\?m_id=\d+(?:&amp;|&)l_id=(\d+)""")


def fetch(url, retries=3, delay=1.0):
    """GET a URL as text (UTF-8, as Deathlogs serves it; cp1252 if that fails); None after retries."""
    last = None
    for attempt in range(1, retries + 1):
        time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("cp1252", errors="replace")
        except Exception as exc:  # network errors vary widely
            last = exc
            print(f"  retry {attempt}/{retries} for {url}: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    print(f"  FAILED {url}: {last}", file=sys.stderr)
    return None


def log_ids(player_page_html):
    """Unique log ids in page order."""
    seen = []
    for lid in LOG_LINK_RE.findall(html.unescape(player_page_html).replace("&amp;", "&")):
        if lid not in seen:
            seen.append(lid)
    return seen


def fetch_player(player, delay=1.0, cache_dir=CACHE_DIR):
    url = f"{BASE_URL}show_player.php?m_id=10&playername={urllib.parse.quote(player)}"
    print(f"[{player}] listing {url}")
    page = fetch(url, delay=delay)
    if page is None:
        return 0, 0, 1
    ids = log_ids(page)
    print(f"[{player}] {len(ids)} logs found")
    out_dir = Path(cache_dir) / player
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0
    for i, lid in enumerate(ids, 1):
        target = out_dir / f"{lid}.html"
        if target.exists() and target.stat().st_size > 0:
            skipped += 1
            continue
        body = fetch(f"{BASE_URL}list_log.php?m_id=10&l_id={lid}", delay=delay)
        if body is None:
            failed += 1
            continue
        target.write_text(body, encoding="utf-8", newline="")
        downloaded += 1
        print(f"[{player}] {i}/{len(ids)} saved {lid} ({len(body)} chars)")
    print(f"[{player}] downloaded={downloaded} cached={skipped} failed={failed}")
    return downloaded, skipped, failed


def is_mudlet(page):
    """Mudlet's export is span-per-color; zMUD's is <font> tags (the page itself has one)."""
    return len(MUDLET_SPAN_RE.findall(page)) > 10 * len(FONT_RE.findall(page))


def fetch_recent(delay=1.0, cache_dir=CACHE_DIR):
    page = fetch(f"{BASE_URL}list_log.php?m_id=10", delay=delay)
    if page is None:
        return 0, 0, 1
    cached = {p.stem for p in Path(cache_dir).rglob("*.html")}
    out_dir = Path(cache_dir) / RECENT
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0
    for lid in log_ids(page):
        if lid in OWN_UPLOADS or lid in cached:
            skipped += 1
            continue
        body = fetch(f"{BASE_URL}list_log.php?m_id=10&l_id={lid}", delay=delay)
        if body is None:
            failed += 1
        elif not is_mudlet(body):
            print(f"[{RECENT}] {lid} is not a Mudlet log, skipped")
            skipped += 1
        else:
            (out_dir / f"{lid}.html").write_text(body, encoding="utf-8", newline="")
            downloaded += 1
            print(f"[{RECENT}] saved {lid} ({len(body)} chars)")
    print(f"[{RECENT}] downloaded={downloaded} skipped={skipped} failed={failed}")
    return downloaded, skipped, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("players", nargs="*", default=DEFAULT_PLAYERS, help="player names (default: Naghig Kunkh)")
    ap.add_argument("--recent", action="store_true", help="also fetch the latest logs of the RL list")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (min 1.0)")
    args = ap.parse_args(argv)
    delay = max(1.0, args.delay)
    total_failed = 0
    for player in args.players:
        total_failed += fetch_player(player, delay)[2]
    if args.recent:
        total_failed += fetch_recent(delay)[2]
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
