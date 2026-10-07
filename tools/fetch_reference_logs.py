"""Descarga de Deathlogs logs de Reinos de Leyenda coloreados por Mudlet, para comparar.

Los logs de un jugador van a cache_reference/<jugador>/<número>.html. Con --recientes N
se bajan además los últimos N logs de RL a cache_reference/recientes/: primero los de la
portada de la lista y después los anteriores, número por número, porque la lista no tiene
más páginas.

Se dejan fuera:
- Los que no son de Mudlet. Mudlet exporta cada tramo de color como
  <span style="color: rgb(...)">, mientras que zMUD usa etiquetas <font color=...>. La
  página de Deathlogs ya trae un <font> propio, así que un log cuenta como de Mudlet
  cuando tiene más de diez veces más tramos <span> con color que etiquetas <font>.
- Los que se hicieron con esta herramienta (OWN_UPLOADS). En Deathlogs quedan iguales que
  los de Mudlet, y compararse con ellos solo probaría que estamos de acuerdo con nosotros
  mismos. Cada vez que se sube uno, hay que agregar su número a OWN_UPLOADS.
- Los que ya están descargados en otra carpeta.

Los números descartados se anotan en recientes/descartados.txt para no volver a pedirlos.
Entre pedido y pedido se espera al menos un segundo.
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
RECENT = "recientes"
SKIPPED_FILE = "descartados.txt"
# Logs uploaded with this tool; Deathlogs stores them exactly like Mudlet's.
OWN_UPLOADS = {"57323", "57324", "57325", "57326", "57327", "57328", "57329", "57330"}
MUDLET_SPAN_RE = re.compile(r'<span style="color: ?rgb', re.I)
FONT_RE = re.compile(r"<font\b", re.I)
RL_TITLE_RE = re.compile(r"<title>[^<]*Reinos de Leyenda", re.I)
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
            print(f"  reintento {attempt}/{retries} de {url}: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    print(f"  no se pudo bajar {url}: {last}", file=sys.stderr)
    return None


def log_ids(page_html):
    """Unique log ids in page order."""
    seen = []
    for lid in LOG_LINK_RE.findall(html.unescape(page_html).replace("&amp;", "&")):
        if lid not in seen:
            seen.append(lid)
    return seen


def fetch_player(player, delay=1.0, cache_dir=CACHE_DIR):
    url = f"{BASE_URL}show_player.php?m_id=10&playername={urllib.parse.quote(player)}"
    print(f"[{player}] buscando sus logs")
    page = fetch(url, delay=delay)
    if page is None:
        return 0, 0, 1
    ids = log_ids(page)
    print(f"[{player}] {len(ids)} logs")
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
        print(f"[{player}] {i}/{len(ids)}: log {lid} guardado")
    print(f"[{player}] {downloaded} nuevos, {skipped} ya estaban, {failed} fallaron")
    return downloaded, skipped, failed


def is_mudlet(page):
    """Mudlet's export is span-per-color; zMUD's is <font> tags (the page itself has one)."""
    return len(MUDLET_SPAN_RE.findall(page)) > 10 * len(FONT_RE.findall(page))


def recent_ids(front_page, count):
    """The front page ids, then older ids one by one, until `count` ids in total."""
    ids = log_ids(front_page)[:count]
    next_id = min(int(i) for i in ids) - 1 if ids else 0
    while len(ids) < count and next_id > 0:
        ids.append(str(next_id))
        next_id -= 1
    return ids


def fetch_recent(count, delay=1.0, cache_dir=CACHE_DIR):
    page = fetch(f"{BASE_URL}list_log.php?m_id=10", delay=delay)
    if page is None:
        return 0, 0, 1
    out_dir = Path(cache_dir) / RECENT
    out_dir.mkdir(parents=True, exist_ok=True)
    skipped_path = out_dir / SKIPPED_FILE
    known_skips = set(skipped_path.read_text(encoding="utf-8").split()) if skipped_path.exists() else set()
    cached = {p.stem for p in Path(cache_dir).rglob("*.html")}
    downloaded = skipped = failed = 0
    new_skips = []
    for lid in recent_ids(page, count):
        if lid in OWN_UPLOADS or lid in cached or lid in known_skips:
            skipped += 1
            continue
        body = fetch(f"{BASE_URL}list_log.php?m_id=10&l_id={lid}", delay=delay)
        if body is None:
            failed += 1
            continue
        if not RL_TITLE_RE.search(body):
            reason = "no es de RL o no existe"
        elif not is_mudlet(body):
            reason = "no es de Mudlet (zMUD u otro cliente)"
        else:
            (out_dir / f"{lid}.html").write_text(body, encoding="utf-8", newline="")
            downloaded += 1
            print(f"[{RECENT}] log {lid} guardado")
            continue
        print(f"[{RECENT}] log {lid} descartado: {reason}")
        new_skips.append(lid)
        skipped += 1
    if new_skips:
        with open(skipped_path, "a", encoding="utf-8") as f:
            f.write("".join(f"{lid}\n" for lid in new_skips))
    print(f"[{RECENT}] {downloaded} nuevos, {skipped} descartados o ya estaban, {failed} fallaron")
    return downloaded, skipped, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jugadores", nargs="*", default=DEFAULT_PLAYERS,
                    help="nombres de jugadores cuyos logs bajar (por defecto: Naghig Kunkh)")
    ap.add_argument("--recientes", type=int, default=0, metavar="N",
                    help="bajar también los últimos N logs de RL")
    ap.add_argument("--espera", type=float, default=1.0, metavar="SEGUNDOS",
                    help="segundos entre pedidos (mínimo 1)")
    args = ap.parse_args(argv)
    delay = max(1.0, args.espera)
    total_failed = 0
    for player in args.jugadores:
        total_failed += fetch_player(player, delay)[2]
    if args.recientes:
        total_failed += fetch_recent(args.recientes, delay)[2]
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
