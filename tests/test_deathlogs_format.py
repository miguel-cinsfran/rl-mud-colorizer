"""The version pasted into Deathlogs (to_deathlogs / toDeathlogs).

Observed on a real upload (log 57323): Deathlogs turns every newline of the pasted log into a
<br> and keeps the <br> already there, and it rejects a log pasted as a single line. So the
pasted lines are separated by the newline alone, while the downloaded file keeps Mudlet's
"<br>\\n" format.
"""

import json
import re
import shutil
import subprocess
import unittest

from _common import FIXTURES, ROOT, fixture_text, make_colorizer
from engine import main, to_deathlogs

NODE = shutil.which("node")
TEXT = "Koch (Org) está aquí.\nCampos de Cultivo [so,e]\nKoch se propina el golpe mortal."


def body(html):
    return html.split("<body><div>", 1)[1].rsplit("</div></body>", 1)[0]


def as_stored_by_deathlogs(pasted):
    """What Deathlogs keeps: the body, with each newline turned into a <br>."""
    return body(pasted).replace("\n", "<br>")


class DeathlogsVersion(unittest.TestCase):
    def setUp(self):
        self.mudlet = make_colorizer().colorize_text(TEXT)
        self.pasted = to_deathlogs(self.mudlet)

    def test_one_line_per_log_line_and_no_br(self):
        self.assertNotIn("<br>", self.pasted)
        self.assertEqual(body(self.pasted).count("\n"), 3)

    def test_header_and_footer_stay_as_mudlet(self):
        self.assertEqual(self.pasted.split("<body><div>")[0], self.mudlet.split("<body><div>")[0])
        self.assertTrue(self.pasted.endswith("\n </div></body>\n</html>"))

    def test_stored_log_has_single_line_breaks(self):
        stored = as_stored_by_deathlogs(self.pasted)
        self.assertNotIn("<br><br>", stored)
        self.assertEqual(stored.count("<br>"), 3)

    def test_mudlet_format_would_double_the_spacing(self):
        # Documents why the conversion exists: pasting the Mudlet format doubles every break.
        self.assertIn("<br><br>", as_stored_by_deathlogs(self.mudlet))

    def test_visible_spans_are_unchanged(self):
        self.assertEqual(re.findall(r"<span[^>]*>.*?</span>", self.pasted),
                         re.findall(r"<span[^>]*>.*?</span>", self.mudlet))


class Cli(unittest.TestCase):
    def test_deathlogs_flag(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.html"
            main([str(FIXTURES / "vipmud_pvp_combat.txt"), "-o", str(out), "--deathlogs"])
            html = out.read_text(encoding="utf-8")
        self.assertNotIn("<br>", html)
        self.assertGreater(body(html).count("\n"), 5)


@unittest.skipUnless(NODE, "node is not on PATH: skipping JS parity for toDeathlogs")
class JsParity(unittest.TestCase):
    def test_js_to_deathlogs_matches_python(self):
        names = ["vipmud_pvp_combat.txt", "vipmud_status_dedupe.txt", "mudlet_excerpt.txt"]
        script = (
            "const fs=require('fs');const path=require('path');"
            "const {RLColorizerJS,toDeathlogs}=require(path.join(process.argv[1],'webapp','engine.js'));"
            "const rules=JSON.parse(fs.readFileSync(path.join(process.argv[1],'rules.json'),'utf8'));"
            "const files=JSON.parse(process.argv[2]);const out={};"
            "for(const f of files){out[f]=toDeathlogs(new RLColorizerJS(rules).colorizeText(fs.readFileSync(f,'utf8')));}"
            "process.stdout.write(JSON.stringify(out));"
        )
        paths = [str(FIXTURES / n) for n in names]
        res = subprocess.run([NODE, "-e", script, str(ROOT), json.dumps(paths)],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        js = json.loads(res.stdout)
        for name, path in zip(names, paths):
            with self.subTest(name=name):
                py = to_deathlogs(make_colorizer().colorize_text(fixture_text(name)))
                self.assertEqual(js[path], py)


if __name__ == "__main__":
    unittest.main()
