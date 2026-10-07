"""Sube un log ya coloreado a Deathlogs (Reinos de Leyenda), sin abrir el navegador.

Sin --enviar no publica nada: comprueba el archivo y los jugadores y muestra lo que se
enviaría. Con --enviar lo publica, busca su número en la lista, comprueba en la página
publicada el título, los ganadores, los perdedores y el principio y el final del log, y
agrega el número a OWN_UPLOADS en tools/fetch_reference_logs.py, para que ese log no se use
como referencia de colores.

El archivo es el que genera `engine.py --deathlogs` (o el que copia la página). Los nombres
tienen que existir en la lista de jugadores de Deathlogs; con --crear-jugadores se dan de
alta los que falten, como hace el botón "Add Player".

Ejemplo:
  python engine.py "thyra 2026-10-07.txt" --lines 25840-27614 --deathlogs -o choi.html
  python tools/upload_deathlogs.py choi.html --titulo "Toreando las astas" --ganador Thyra --perdedor Choi
  python tools/upload_deathlogs.py choi.html --titulo "Toreando las astas" --ganador Thyra --perdedor Choi --enviar
"""

import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FETCHER = ROOT / "tools" / "fetch_reference_logs.py"
BASE_URL = "https://deathlogs.com/"
FORM_URL = BASE_URL + "add_log_test.php?level=1&m_id=10"
LIST_URL = BASE_URL + "list_log.php?m_id=10"
USER_AGENT = "rl-mud-colorizer-uploader/1.0"
OPTION_RE = re.compile(r"<option[^>]*value=['\"]?(\d+)['\"]?[^>]*>([^<]*)", re.I)
HIDDEN_RE = re.compile(r"<input[^>]*name=['\"]?(date|ip)['\"]?[^>]*value=['\"]?([^'\"\s>]*)", re.I)
LIST_ENTRY_RE = re.compile(r"l_id=(\d+)\">([^<]*)</A>", re.I)
OWN_UPLOADS_RE = re.compile(r"^OWN_UPLOADS = \{([^}]*)\}", re.M)


def request(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_form(page):
    """(players {lowercase name: (name, option value)}, hidden fields {date, ip}) from the form page."""
    select = page[page.find("name=sel"):]
    select = select[:select.find("</select>")]
    players = {}
    for value, name in OPTION_RE.findall(select):
        name = html.unescape(name).strip()
        if name:
            players[name.lower()] = (name, value)
    hidden = {k: v for k, v in HIDDEN_RE.findall(page)}
    return players, hidden


def visible_lines(log_html):
    """Plain text lines of the log body, to check the published copy."""
    body = log_html[log_html.find("<div>"):] if "<div>" in log_html else log_html
    # The published page writes line breaks as "<br />".
    text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", body, flags=re.I)))
    return [line.strip() for line in text.splitlines() if line.strip()]


def multipart(fields):
    """Encode [(name, value), ...] as multipart/form-data, like the browser does."""
    boundary = "----rl" + uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")
    parts.append(f"--{boundary}--\r\n")
    return "".join(parts).encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def add_own_upload(log_id):
    source = FETCHER.read_text(encoding="utf-8")
    m = OWN_UPLOADS_RE.search(source)
    ids = sorted({i.strip().strip('"') for i in m.group(1).split(",") if i.strip()} | {log_id}, key=int)
    FETCHER.write_text(source[:m.start()] + "OWN_UPLOADS = {" + ", ".join(f'"{i}"' for i in ids) + "}"
                       + source[m.end():], encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", help="HTML generado con engine.py --deathlogs")
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--ganador", action="append", default=[], help="se puede repetir")
    ap.add_argument("--perdedor", action="append", default=[], help="se puede repetir")
    ap.add_argument("--crear-jugadores", action="store_true", help="dar de alta los jugadores que falten")
    ap.add_argument("--enviar", action="store_true", help="publicar de verdad; sin esto solo se muestra")
    args = ap.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    log = Path(args.archivo).read_text(encoding="utf-8")
    lines = visible_lines(log)
    if log.count("\n") < 2 or not lines:
        print("El archivo no parece un log: Deathlogs rechaza un log en una sola línea.")
        return 1
    if not args.ganador and not args.perdedor:
        print("Falta al menos un --ganador o un --perdedor.")
        return 1

    players, hidden = parse_form(request(FORM_URL))
    missing = [n for n in args.ganador + args.perdedor if n.lower() not in players]
    if missing and not args.crear_jugadores:
        print(f"No están en la lista de Deathlogs: {', '.join(missing)}. Revisa cómo se escriben o usa --crear-jugadores.")
        return 1
    winners = [players.get(n.lower(), (n, ""))[0] for n in args.ganador]
    losers = [players.get(n.lower(), (n, ""))[0] for n in args.perdedor]
    # The browser also sends the player left selected in the list: the last one added.
    selected = players.get((args.perdedor or args.ganador)[-1].lower(), ("", "0"))[1]

    print(f"Título: {args.titulo}")
    print(f"Ganadores: {', '.join(winners) or 'ninguno'}. Perdedores: {', '.join(losers) or 'ninguno'}.")
    if missing:
        print(f"Se darán de alta: {', '.join(missing)}.")
    print(f"Log: {len(lines)} líneas, de \"{lines[0][:70]}\" a \"{lines[-1][:70]}\".")
    if not args.enviar:
        print("No se envió nada. Agrega --enviar para publicarlo.")
        return 0

    for name in missing:
        body, ctype = multipart([("m_id", "10"), ("level", "2"), ("newname", name), ("add", "Add Player")])
        request(BASE_URL + "add_log_test.php", body, {"Content-Type": ctype})
    before = {int(i) for i, _ in LIST_ENTRY_RE.findall(request(LIST_URL))}
    # As a browser does: textareas go with CRLF line ends, and the unchecked "alternate"
    # box (an alternative log, without winners or losers) is not sent at all.
    body, ctype = multipart([
        ("qu", ""), ("sel", selected), ("winners", "".join(n + "\r\n" for n in winners)),
        ("loosers", "".join(n + "\r\n" for n in losers)),
        ("level", "2"), ("m_id", "10"), ("logtitle", args.titulo),
        ("date", hidden.get("date", "")), ("ip", hidden.get("ip", "")),
        ("log", log.replace("\r\n", "\n").replace("\n", "\r\n")),
    ])
    request(BASE_URL + "add_log_test.php", body, {"Content-Type": ctype})

    time.sleep(2)
    new = [(int(i), html.unescape(t).strip()) for i, t in LIST_ENTRY_RE.findall(request(LIST_URL))]
    match = [i for i, t in new if i not in before and t == args.titulo]
    if not match:
        print("Se envió, pero el log no aparece en la lista. Revísalo en Deathlogs antes de volver a enviarlo.")
        return 1
    log_id = str(max(match))
    page = request(f"{LIST_URL}&l_id={log_id}")
    published = visible_lines(page)
    checks = {
        "el título": args.titulo in html.unescape(page),
        "los ganadores": all(f"playername={urllib.parse.quote(n)}" in page or f"playername={n}" in page for n in winners),
        "los perdedores": all(f"playername={urllib.parse.quote(n)}" in page or f"playername={n}" in page for n in losers),
        "el principio del log": lines[0] in published,
        "el final del log": lines[-1] in published,
    }
    add_own_upload(log_id)
    print(f"Publicado: {LIST_URL}&l_id={log_id}")
    failed = [k for k, ok in checks.items() if not ok]
    print("Comprobado en la página: todo bien." if not failed else f"Revisa en la página: {', '.join(failed)}.")
    print(f"El número {log_id} quedó en OWN_UPLOADS; falta guardar ese cambio en git.")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
