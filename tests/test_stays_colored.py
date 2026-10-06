"""Guard: a line that the previous release colored must never turn fully default.

tests/fixtures/must_stay_colored.txt holds the distinct lines (from the accessibility
logs and fixtures) that bb98508 rendered with at least one non-default color. The
structured rules added later (markers, prompt layout) may recolor a line, but they
must not remove all of its color.
"""

import re
import unittest

from _common import FIXTURES, make_colorizer
from tools import evaluate as ev

DEFAULT = "color: rgb(192,192,192)"


def has_color(rendered):
    return any(DEFAULT not in style for style in re.findall(r'style="([^"]*)"', rendered))


class StaysColoredTest(unittest.TestCase):
    def test_previously_colored_lines_keep_a_colored_span(self):
        colorizer = make_colorizer()
        lines = (FIXTURES / "must_stay_colored.txt").read_text(encoding="utf-8").split("\n")
        lines = [l for l in lines if l.strip()]
        self.assertGreater(len(lines), 1000)
        lost = [l for l in lines if not has_color(colorizer.colorize_line(l))]
        self.assertEqual(lost[:10], [], f"{len(lost)} lines lost all color")

    def test_marker_lines_keep_every_character_that_was_colored(self):
        """`#`, `*` and `+` lines: the marker may change color, the body keeps bb98508's colors.

        marker_line_masks.tsv holds `line<TAB>mask`; `C` marks a character bb98508 rendered
        with a non-default color, `.` anything else.
        """
        colorizer = make_colorizer()
        rows = [r for r in (FIXTURES / "marker_line_masks.tsv").read_text(encoding="utf-8").split("\n") if r]
        self.assertGreater(len(rows), 100)
        broken = []
        for row in rows:
            line, mask = row.split("\t")
            parsed = ev.parse_html_log("<body>" + colorizer.colorize_line(line))[0]
            self.assertEqual("".join(c for c, _ in parsed).rstrip(), line.rstrip(), line)
            for (ch, color), want in zip(parsed, mask):
                if want == "C" and color == "#c0c0c0":
                    broken.append(line)
                    break
        self.assertEqual(broken[:5], [], f"{len(broken)} marker lines lost body color")


if __name__ == "__main__":
    unittest.main()
