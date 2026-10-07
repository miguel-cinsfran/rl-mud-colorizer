"""tools/search_logs.py (glory finder and text search) and engine.py --lines."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from _common import ROOT  # noqa: F401  (puts the repo on sys.path)

import engine
from tools import search_logs

LOG = """Choi (Hum) llega desde el noroeste.
Campos de Cultivo [ne,o]
Propinas el golpe mortal a Choi.
Choi ha muerto.
[Obtienes 106 puntos de gloria]
SL: [o,s,e,n]
Thangrim propina el golpe mortal a Zeh.
[Obtienes 20 puntos de gloria]
Exterior de Anduar: Puerta Este [o,s,e,n]
Koch se propina el golpe mortal.
[Obtienes 156 puntos de gloria]
Rhyzan ha muerto.
[Obtienes 5 puntos de gloria]
[Obtienes 7 puntos de gloria]
Choi te dice: voy 1 min, ya vuelvo telepáticamente
"""


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = search_logs.main(argv)
    return code, out.getvalue().splitlines()


class SearchLogsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "thyra 2026-10-07.txt").write_bytes(LOG.replace("\n", "\r\n").encode("cp1252"))
        (self.dir / "telael 2026-10-07.txt").write_text("[Obtienes 1 puntos de gloria]\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_glory_names_the_kill_and_the_room(self):
        code, lines = run(["gloria", "thyra", "--carpeta", str(self.dir)])
        self.assertEqual(code, 0)
        self.assertEqual(lines[:5], [
            "thyra 2026-10-07.txt, línea 5: 106 de gloria, por matar a Choi (Hum), en Campos de Cultivo.",
            "thyra 2026-10-07.txt, línea 8: 20 de gloria, el golpe mortal a Zeh lo dio Thangrim, en Campos de Cultivo.",
            "thyra 2026-10-07.txt, línea 11: 156 de gloria, Koch se dio el golpe mortal a sí mismo"
            ", en Exterior de Anduar: Puerta Este.",
            "thyra 2026-10-07.txt, línea 13: 5 de gloria, murió Rhyzan, sin golpe mortal a la vista"
            ", en Exterior de Anduar: Puerta Este.",
            "thyra 2026-10-07.txt, línea 14: 7 de gloria, no aparece ningún golpe mortal en las líneas de arriba"
            ", en Exterior de Anduar: Puerta Este.",
        ])
        self.assertEqual(lines[-1], "5 veces con gloria en 1 archivo.")

    def test_glory_without_any_death_says_so(self):
        _, lines = run(["gloria", "telael", "--carpeta", str(self.dir)])
        self.assertEqual(lines[0], "telael 2026-10-07.txt, línea 1: 1 de gloria,"
                                   " no aparece ningún golpe mortal en las líneas de arriba.")

    def test_search_ignores_case_and_accents_in_cp1252_logs(self):
        _, lines = run(["buscar", "TELEPATICAMENTE", "thyra", "telael", "--carpeta", str(self.dir)])
        self.assertEqual(lines, ["thyra 2026-10-07.txt, línea 15: Choi te dice: voy 1 min, ya vuelvo telepáticamente",
                                 "1 línea en 2 archivos."])

    def test_unknown_character_fails_cleanly(self):
        code, lines = run(["gloria", "nadie", "--carpeta", str(self.dir)])
        self.assertEqual(code, 1)
        self.assertIn("No hay logs de nadie", lines[0])


class EngineCutOptionTest(unittest.TestCase):
    def test_cut_replaces_ranges_with_notes(self):
        text = "\n".join(f"l{i}" for i in range(1, 11))
        self.assertEqual(engine.select_lines(text, "2-9", [("4-5", "BUSCANDO..."), ("7-7", "// CURANDOME")]),
                         "l2\nl3\n// BUSCANDO...\nl6\n// CURANDOME\nl8\nl9")

    def test_cut_alone_keeps_the_whole_file(self):
        self.assertEqual(engine.select_lines("a\nb\nc", None, [("2-2", "X")]), "a\n// X\nc")

    def test_bad_cuts_are_refused(self):
        text = "\n".join(f"l{i}" for i in range(1, 11))
        for lines, cuts in (("2-9", [("1-3", "x")]), (None, [("2-5", "x"), ("5-6", "y")]), (None, [("5-2", "x")])):
            with self.subTest(lines=lines, cuts=cuts), self.assertRaises(ValueError):
                engine.select_lines(text, lines, cuts)


class EngineLinesOptionTest(unittest.TestCase):
    def test_lines_renders_only_that_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "log.txt"
            src.write_text("uno\nPropinas el golpe mortal a Choi.\n[Obtienes 106 puntos de gloria]\ncuatro\n",
                           encoding="utf-8")
            out = Path(tmp) / "out.html"
            with contextlib.redirect_stderr(io.StringIO()):
                engine.main([str(src), "--lines", "2-3", "-o", str(out)])
            html = out.read_text(encoding="utf-8")
        self.assertIn("Choi", html)
        self.assertIn("106", html)
        self.assertNotIn("uno", html)
        self.assertNotIn("cuatro", html)


if __name__ == "__main__":
    unittest.main()
