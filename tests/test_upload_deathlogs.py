"""tools/upload_deathlogs.py without touching the network: form parsing, dry run, OWN_UPLOADS."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _common import ROOT  # noqa: F401  (puts the repo on sys.path)

from tools import upload_deathlogs as up

FORM = """<FORM METHOD="POST" ACTION="add_log_test.php" name=fo>
<select name=sel><option value=0>Choi</option><option value=1>Thyra</option><option value=2>Zellor</option></select>
<INPUT TYPE="hidden" name="date" VALUE="07.10.2026"><INPUT TYPE="hidden" name="ip" VALUE="1.2.3.4">
</FORM>"""
LOG = ('<!DOCTYPE html>\n<html><head></head>\n  <body><div><span style="color: rgb(255,255,0); ">Choi (Hum)</span>'
       '<span style="color: rgb(192,192,192); "> llega desde el noroeste.</span>\n'
       '<span style="color: rgb(192,192,192); ">[Obtienes 106 puntos de gloria]</span>\n </div></body>\n</html>')


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = up.main(argv)
    return code, out.getvalue()


class UploadDeathlogsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "log.html"
        self.log.write_text(LOG, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_form_reads_players_and_hidden_fields(self):
        players, hidden = up.parse_form(FORM)
        self.assertEqual(players, {"choi": "Choi", "thyra": "Thyra", "zellor": "Zellor"})
        self.assertEqual(hidden, {"date": "07.10.2026", "ip": "1.2.3.4"})

    def test_published_breaks_count_as_line_ends(self):
        page = "<PRE><div><span>Choi llega.</span><br /><span>[Obtienes 1 puntos de gloria]</span><br />"
        self.assertEqual(up.visible_lines(page), ["Choi llega.", "[Obtienes 1 puntos de gloria]"])

    def test_dry_run_posts_nothing(self):
        with mock.patch.object(up, "request", return_value=FORM) as req:
            code, out = run([str(self.log), "--titulo", "Toreando las astas", "--ganador", "thyra",
                             "--perdedor", "CHOI"])
        self.assertEqual(code, 0)
        self.assertTrue(all(c.args[1:] == () for c in req.call_args_list))  # GETs only
        self.assertIn("Ganadores: Thyra. Perdedores: Choi.", out)
        self.assertIn('de "Choi (Hum) llega desde el noroeste." a "[Obtienes 106 puntos de gloria]"', out)
        self.assertIn("No se envió nada", out)

    def test_unknown_player_stops_before_sending(self):
        with mock.patch.object(up, "request", return_value=FORM):
            code, out = run([str(self.log), "--titulo", "x", "--ganador", "Thyra", "--perdedor", "Nadie", "--enviar"])
        self.assertEqual(code, 1)
        self.assertIn("No están en la lista de Deathlogs: Nadie", out)

    def test_single_line_log_is_refused(self):
        self.log.write_text(LOG.replace("\n", ""), encoding="utf-8")
        code, out = run([str(self.log), "--titulo", "x", "--ganador", "Thyra"])
        self.assertEqual(code, 1)
        self.assertIn("una sola línea", out)

    def test_add_own_upload_keeps_ids_sorted_and_unique(self):
        fetcher = Path(self.tmp.name) / "fetch.py"
        fetcher.write_text('X = 1\nOWN_UPLOADS = {"57323", "57325"}\nY = 2\n', encoding="utf-8")
        with mock.patch.object(up, "FETCHER", fetcher):
            up.add_own_upload("57324")
            up.add_own_upload("57325")
        self.assertEqual(fetcher.read_text(encoding="utf-8"),
                         'X = 1\nOWN_UPLOADS = {"57323", "57324", "57325"}\nY = 2\n')


if __name__ == "__main__":
    unittest.main()
