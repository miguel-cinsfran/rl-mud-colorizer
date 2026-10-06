"""Offline tests for tools/evaluate.py (no network, synthetic reference HTML)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import evaluate as ev  # noqa: E402

REFERENCE = (
    '<HTML><BODY><PRE><font color="#cccccc" size="2"><div>'
    '<span style="color:rgb(255,0,0);background:rgb(0,0,0);">ab</span>'
    '<span style="color:#00FF00;background:rgb(0,0,0);">c&gt;</span><br />'
    '<span style="color:rgb(0,0,255);background:rgb(0,0,0);">xy</span> z<br />'
    '</div></font></PRE></BODY></HTML>'
)

# Same text as REFERENCE; ours gets '>' wrong on line 1 and 'y' wrong on line 2.
OURS = (
    "<html><head><style>body { color:rgb(255,255,255); }</style></head><body><div>"
    '<span style="color: rgb(255,0,0); background: rgb(0,0,0); ">ab</span>'
    '<span style="color: rgb(0,255,0); background: rgb(0,0,0); ">c</span>'
    '<span style="color: rgb(1,2,3); background: rgb(0,0,0); ">&gt;</span><br>'
    '<span style="color: rgb(0,0,255); background: rgb(0,0,0); ">x</span>'
    '<span style="color: rgb(9,9,9); background: rgb(0,0,0); ">y</span>'
    '<span style="color: rgb(204,204,204); background: rgb(0,0,0); "> z</span><br>'
    "\n </div></body></html>"
)


class ParseTests(unittest.TestCase):
    def test_normalize_color(self):
        self.assertEqual(ev.normalize_color("rgb(192, 192,192)"), "#c0c0c0")
        self.assertEqual(ev.normalize_color("#00FF00"), "#00ff00")
        self.assertIsNone(ev.normalize_color("red"))

    def test_parse_reference(self):
        lines = ev.parse_html_log(REFERENCE, default_color="#000000")
        self.assertEqual(len(lines), 2)
        self.assertEqual(ev.line_text(lines[0]), "abc>")  # entity decoded
        self.assertEqual([c for _, c in lines[0]], ["#ff0000", "#ff0000", "#00ff00", "#00ff00"])
        self.assertEqual(ev.line_text(lines[1]), "xy z")
        # text outside spans takes the <font color> default
        self.assertEqual(lines[1][2], (" ", "#cccccc"))
        self.assertEqual(lines[1][3], ("z", "#cccccc"))

    def test_parse_our_output_ignores_head_style(self):
        lines = ev.parse_html_log(OURS)
        self.assertEqual([ev.line_text(l) for l in lines], ["abc>", "xy z"])

    def test_segments_are_compact(self):
        lines = ev.parse_html_log(REFERENCE)
        self.assertEqual(ev.segments(lines[0]), "[#ff0000]ab[#00ff00]c>")
        self.assertEqual(ev.segments(lines[1]), "[#0000ff]xy [#cccccc]z")

    def test_shape(self):
        self.assertEqual(ev.line_shape("Pvs: 12/40 Lleva Espada Azul"), "Pvs: N/N X X X")


class ScoreTests(unittest.TestCase):
    def test_known_two_line_example(self):
        ref = ev.parse_html_log(REFERENCE)
        got = ev.parse_html_log(OURS)
        stats = ev.Stats()
        stats.add_log({"ref": ref, "got": got, "fallback": False})
        # non-whitespace chars: abc> (4) + xyz (3) = 7; wrong: '>' and 'y' => 5/7 correct
        self.assertEqual(stats.chars, 7)
        self.assertEqual(stats.correct, 5)
        self.assertEqual(stats.lines, 2)
        self.assertEqual(stats.exact, 0)
        self.assertAlmostEqual(stats.summary()["char_accuracy"], 5 / 7)
        self.assertEqual(stats.confusion[("#00ff00", "#010203")], 1)
        self.assertEqual(stats.confusion[("#0000ff", "#090909")], 1)

    def test_misaligned_text_is_not_scored(self):
        ref = ev.parse_html_log(REFERENCE)
        got = ev.parse_html_log(OURS.replace("ab</span>", "aq</span>"))
        stats = ev.Stats()
        stats.add_log({"ref": ref, "got": got, "fallback": False})
        self.assertEqual(stats.misaligned, 1)
        self.assertEqual(stats.lines, 1)


if __name__ == "__main__":
    unittest.main()
