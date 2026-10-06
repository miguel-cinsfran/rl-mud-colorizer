"""Download colored Mudlet reference logs from Deathlogs into cache_reference/<player>/<l_id>.html."""

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
LOG_LINK_RE = re.compile(r"""list_log\.php\?m_id=\d+(?:&amp;|&)l_id=(\d+)""")


def fetch(url, retries=3, delay=1.0):
    """GET a URL as cp1252 text; returns None after exhausting retries."""
    last = None
    for attempt in range(1, retries + 1):
        time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("cp1252", errors="replace")
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("players", nargs="*", default=DEFAULT_PLAYERS, help="player names (default: Naghig Kunkh)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (min 1.0)")
    args = ap.parse_args(argv)
    delay = max(1.0, args.delay)
    total_failed = 0
    for player in args.players:
        total_failed += fetch_player(player, delay)[2]
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
