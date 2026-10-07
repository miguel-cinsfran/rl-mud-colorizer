"""Busca en los logs de VIPMud o Mudlet de uno o varios personajes.

Los logs se buscan en la carpeta de --carpeta, o en la de la variable de entorno RL_LOGS si
no se indica; los archivos se reconocen por el nombre del personaje al principio
("thyra 2026-10-07.txt"). Se leen en UTF-8 o Windows-1252, así que los acentos y las eñes
se encuentran sin convertir nada.

Dos órdenes:

  gloria   Cada "[Obtienes N puntos de gloria]" con su archivo y línea, a quién mataste
           (de "Propinas el golpe mortal a X" en las líneas de arriba) y la última sala.
           Si el golpe mortal lo dio otro, o no aparece, lo dice igual.
  buscar   Las líneas que contienen un texto, sin distinguir mayúsculas ni acentos.

Ejemplos:
  python tools/search_logs.py gloria thyra telael --carpeta "C:/Users/yo/Documents/VIP Mud/logs"
  python tools/search_logs.py buscar "voy 1 min" thyra --fecha 2026-10-07
"""

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import read_text_file  # noqa: E402

GLORY_RE = re.compile(r"\[Obtienes (\d+) puntos? de gloria\]")
OWN_KILL_RE = re.compile(r"^(?:[>\]]\s*)?Propinas el golpe mortal a (.+?)\.\s*$")
OTHER_KILL_RE = re.compile(r"^(?:[>\]]\s*)?(.+?) propina el golpe mortal a (.+?)\.\s*$")
SELF_KILL_RE = re.compile(r"^(?:[>\]]\s*)?(.+?) se propina el golpe mortal\.\s*$")
DIED_RE = re.compile(r"^(?:[>\]]\s*)?(.+?) ha muerto\.\s*$")
# A room title with its exits; "SL: [o,s,e,n]" in VIPMud's status block is not one.
ROOM_RE = re.compile(r"^(?:[>\]]\s*)?(?!SL:)([A-ZÁÉÍÓÚÑÜ][^\[\]]*?)\s+\[[a-z|,]+\]\s*$")
KILL_LOOKBACK = 12
ROOM_LOOKBACK = 400


def log_files(folder, characters, date=None):
    """Log files of the given characters, oldest first."""
    wanted = {c.lower() for c in characters}
    files = []
    for path in Path(folder).glob("*.txt"):
        name = path.stem.lower()
        if name.split(" ")[0] in wanted and (not date or date in name):
            files.append(path)
    return sorted(files, key=lambda p: (p.stem.split(" ")[-1], p.stem))


def fold(text):
    """Lowercase without accents, so "telepatico" finds "telepático"."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def glory_events(lines):
    """(line number, points, kill description, room) for every glory line."""
    for i, line in enumerate(lines):
        m = GLORY_RE.search(line)
        if not m:
            continue
        # Only the lines since the previous glory line belong to this one.
        above = []
        for back in lines[max(0, i - KILL_LOOKBACK):i][::-1]:
            if GLORY_RE.search(back):
                break
            above.append(back)
        kill = "no aparece ningún golpe mortal en las líneas de arriba"
        for back in above:
            own, other, self_kill = OWN_KILL_RE.match(back), OTHER_KILL_RE.match(back), SELF_KILL_RE.match(back)
            if own:
                kill = f"por matar a {own.group(1)}"
            elif self_kill:
                kill = f"{self_kill.group(1)} se dio el golpe mortal a sí mismo"
            elif other:
                kill = f"el golpe mortal a {other.group(2)} lo dio {other.group(1)}"
            else:
                continue
            break
        else:
            died = next((d for d in map(DIED_RE.match, above) if d), None)
            if died:
                kill = f"murió {died.group(1)}, sin golpe mortal a la vista"
        room = next((r.group(1) for r in (ROOM_RE.match(b) for b in lines[max(0, i - ROOM_LOOKBACK):i][::-1]) if r),
                    None)
        yield i + 1, int(m.group(1)), kill, room


def files_text(n):
    return f"{n} {'archivo' if n == 1 else 'archivos'}"


def cmd_glory(files):
    total = 0
    for path in files:
        for number, points, kill, room in glory_events(read_text_file(path).splitlines()):
            where = f" ({room})" if room else ""
            print(f"{path.name}, línea {number}: {points} de gloria, {kill}{where}.")
            total += 1
    print(f"{total} {'vez' if total == 1 else 'veces'} con gloria en {files_text(len(files))}.")


def cmd_search(files, text, limit):
    needle = fold(text)
    found = 0
    for path in files:
        for number, line in enumerate(read_text_file(path).splitlines(), 1):
            if needle in fold(line):
                found += 1
                if found <= limit:
                    print(f"{path.name}, línea {number}: {line.strip()}")
    if found > limit:
        print(f"... y {found - limit} más. Usa --max para ver más o --fecha para acotar.")
    print(f"{found} {'línea' if found == 1 else 'líneas'} en {files_text(len(files))}.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--carpeta", default=os.environ.get("RL_LOGS", "."),
                        help="carpeta de los logs (por defecto, la variable RL_LOGS o la carpeta actual)")
    common.add_argument("--fecha", help="solo los archivos cuyo nombre contiene esta fecha, por ejemplo 2026-10-07")
    g = sub.add_parser("gloria", parents=[common], help="lista las veces que se obtuvo gloria")
    g.add_argument("personajes", nargs="+")
    b = sub.add_parser("buscar", parents=[common], help="busca un texto")
    b.add_argument("texto")
    b.add_argument("personajes", nargs="+")
    b.add_argument("--max", type=int, default=50, help="máximo de líneas a mostrar (por defecto 50)")
    args = ap.parse_args(argv)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    files = log_files(args.carpeta, args.personajes, args.fecha)
    if not files:
        print(f"No hay logs de {', '.join(args.personajes)} en {args.carpeta}.")
        return 1
    if args.orden == "gloria":
        cmd_glory(files)
    else:
        cmd_search(files, args.texto, args.max)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
