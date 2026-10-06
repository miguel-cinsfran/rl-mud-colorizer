"""Guard: coloring never changes the visible text of a line (only colors may differ)."""

import re
import unittest

from _common import ACCESSIBILITY_LOGS, FIXTURES, make_colorizer, visible_lines
from engine import read_text_file


def expected_lines(colorizer, text):
    """Input lines as the engine sees them: preprocessed, blank runs collapsed, entities decoded."""
    pre = colorizer.preprocess_text(text)
    trimmed = pre.replace("\r\n", "\n").rstrip("\n")
    if not trimmed:
        return []
    lines = re.sub(r"\n{3,}", "\n\n", trimmed).split("\n")
    out = []
    for line in lines:
        line = line.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
        out.append("" if not line.strip() else line)
    return out


class VisibleTextTest(unittest.TestCase):
    def check(self, path):
        colorizer = make_colorizer()
        text = read_text_file(path)
        got = visible_lines(colorizer.colorize_text(text))
        want = expected_lines(colorizer, text)
        self.assertEqual(len(got), len(want), path.name)
        for i, (g, w) in enumerate(zip(got, want), 1):
            self.assertEqual(g.rstrip(), w.rstrip(), f"{path.name} line {i}")  # trailing blanks are invisible

    def test_fixtures_keep_visible_text(self):
        for path in sorted(FIXTURES.glob("*.txt")):
            with self.subTest(path.name):
                self.check(path)

    def test_accessibility_logs_keep_visible_text(self):
        for path in sorted(ACCESSIBILITY_LOGS.glob("*.txt")):
            with self.subTest(path.name):
                self.check(path)

    def test_prompt_symbols_are_preserved(self):
        colorizer = make_colorizer()
        for line in ("] sur", "> sur", "]", "> ", "] Pvs: 10/10 (-1) Pe: 1/1 (0)"):
            got = visible_lines(colorizer.colorize_text(line, preprocess=False))
            self.assertEqual([g.rstrip() for g in got], [line.rstrip()])

    def test_inner_spacing_and_trailing_periods_are_preserved(self):
        colorizer = make_colorizer()
        for line in (
            "Elemental Menor de Tierra y  están aquí.",
            "Naghig se va hacia el -| este |-",
            "        [s,e,n,o]",
            "  Pe:597759 Xp:2258502",
            "La magia de tu Espada Azul no es capaz de seguir tus fugaces movimientos, pero pronto te alcanza,",
        ):
            got = visible_lines(colorizer.colorize_text(line, preprocess=False))
            self.assertEqual([g.rstrip() for g in got], [line], line)


if __name__ == "__main__":
    unittest.main()
