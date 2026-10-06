"""Tiered health percentages: group status block and the "Puntos de Vida" line."""

import json
import math
import re
import unittest

from _common import ROOT, make_colorizer, visible_lines
from tools import evaluate as ev

HEADER = "De un fugaz vistazo, examinas el estado de los que te rodean."
GREEN, AMBER, RED = "#5fd75f", "#ffcc4b", "#ea063f"
NAMES = ["Zorak", "Esqueleto del Túmulo", "Cvstodes III, el Pecio animado", "Rothe, el Artista"]


def segs(c, text):
    return [ev.segments(line) for line in ev.parse_html_log(c.colorize_text(text, preprocess=False))]


def colored(c, text):
    """Per output line: list of (substring, color) for non-default colors."""
    out = []
    for line in ev.parse_html_log(c.colorize_text(text, preprocess=False)):
        runs = []
        for ch, col in line:
            if runs and runs[-1][1] == col:
                runs[-1][0] += ch
            else:
                runs.append([ch, col])
        out.append([(t, col) for t, col in runs if col != "#c0c0c0"])
    return out


def tier_colored(c, text):
    """Per output line: the tier-colored runs only (chat colors etc. are ignored)."""
    return [[r for r in runs if r[1] in (GREEN, AMBER, RED)] for runs in colored(c, text)]


class GroupStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = make_colorizer()

    def test_percentage_only_is_colored_with_each_tier(self):
        for pct, color in ((100, GREEN), (70, GREEN), (69, AMBER), (31, AMBER), (30, RED), (13, RED), (0, RED)):
            for name in NAMES:
                text = f"{HEADER}\n{name}         {pct}%"
                with self.subTest(name=name, pct=pct):
                    self.assertEqual(colored(self.c, text)[1], [(f"{pct}%", color)])

    def test_visible_text_and_padding_are_unchanged(self):
        text = HEADER + "\n" + "\n".join(f"{n}         {p}%" for n, p in zip(NAMES, (100, 55, 8, 70)))
        out = visible_lines(self.c.colorize_text(text, preprocess=False))
        self.assertEqual(out[: len(text.split("\n"))], text.split("\n"))

    def test_block_with_several_lines_and_single_space(self):
        text = f"{HEADER}\nBomurg 13%\nMano espectral            100%\n\nPuntos de Vida: 1 de 2 (50%)"
        got = colored(self.c, text)
        self.assertEqual(got[1], [("13%", RED)])
        self.assertEqual(got[2], [("100%", GREEN)])

    def test_prompt_prefix_on_header_keeps_the_context(self):
        got = colored(self.c, f"> {HEADER}\nZorak 90%")
        self.assertEqual(got[1], [("90%", GREEN)])

    def test_without_header_nothing_is_colored(self):
        for line in ("Colgante del Oso 28%", "Zorak          100%", "Rothe, el Artista         100%"):
            self.assertEqual(colored(self.c, line), [[]], line)

    def test_context_ends_at_blank_or_other_line(self):
        self.assertEqual(colored(self.c, f"{HEADER}\n\nZorak 90%")[2], [])
        self.assertEqual(colored(self.c, f"{HEADER}\nZorak 90%\nNo hay nadie.\nZorak 90%")[3], [])

    def test_lines_that_are_not_status_stay_uncolored(self):
        for line in (
            "Dices: 'Zorak 90%'",
            "Zorak te dice: Rothe 90%",
            "[Chat] Zorak: vida 90%",
            "Zorak 90% de acierto",
        ):
            with self.subTest(line=line):
                self.assertFalse(tier_colored(self.c, f"{HEADER}\n{line}")[1])

    def test_vida_energia_lines_tier_only_the_vida_percentage(self):
        for pct, color in ((100, GREEN), (48, AMBER), (25, RED)):
            for name in NAMES:
                text = f"{HEADER}\n{name}                  Vida: {pct}% Energía: 4%"
                with self.subTest(name=name, pct=pct):
                    self.assertEqual(colored(self.c, text)[1], [(f"{pct}%", color)])
                    self.assertEqual(visible_lines(self.c.colorize_text(text, preprocess=False))[1], text.split("\n")[1])

    def test_vida_energia_line_needs_the_header(self):
        self.assertEqual(colored(self.c, "Zeh Vida: 48% Energía: 2%"), [[]])

    def test_context_does_not_leak_between_texts(self):
        self.c.colorize_text(HEADER, preprocess=False)
        self.assertEqual(colored(self.c, "Zorak 90%"), [[]])


class VitalsLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = make_colorizer()

    def test_numbers_and_percentage_take_the_tier_color(self):
        for line, color, parts in (
            ("Puntos de Vida: 4132 de 4336 (95%)", GREEN, ["4132", "4336", "95%"]),
            ("Puntos de Vida: 1500 de 4336 (35%)", AMBER, ["1500", "4336", "35%"]),
            ("Puntos de Vida: 100 de 4336 (2%)", RED, ["100", "4336", "2%"]),
        ):
            with self.subTest(line=line):
                got = colored(self.c, line)[0]
                self.assertEqual(got, [(p, color) for p in parts])

    def test_bar_format_colors_numbers_and_percentage(self):
        for line, color, parts in (
            ("Puntos de Vida        : [################### ] (9655/10000) (96%)", GREEN, ["9655", "10000", "96%"]),
            ("Puntos de Vida        : [########            ] (21637/50601) (42%)", AMBER, ["21637", "50601", "42%"]),
            ("Puntos de Vida        : [##                  ] (900/50601) (2%)", RED, ["900", "50601", "2%"]),
        ):
            with self.subTest(line=line):
                self.assertEqual(colored(self.c, line)[0], [(p, color) for p in parts])
                self.assertEqual(visible_lines(self.c.colorize_text(line, preprocess=False))[0], line)

    def test_other_bars_stay_default(self):
        for line in ("Puntos de Energía     : [################### ] (9572/10000) (95%)",
                     "Puntos Sociales       : [####################] (2000/2000) (100%)"):
            self.assertFalse(tier_colored(self.c, line)[0], line)

    def test_not_a_vitals_line(self):
        for line in ("Dices: 'Puntos de Vida: 1 de 2 (50%)'", "Zorak te dice: Puntos de Vida: 1 de 2 (50%)"):
            self.assertFalse(tier_colored(self.c, line)[0], line)


class TierPalette(unittest.TestCase):
    def test_tiers_are_distinct_and_readable(self):
        with open(ROOT / "rules.json", encoding="utf-8") as f:
            data = json.load(f)
        tiers = {t["color"] for r in data["rules"] if r.get("tiers") for t in r["tiers"]}
        self.assertEqual(tiers, {GREEN, AMBER, RED})
        skip = {"room_colors", "room_map_colors", "preprocess"}
        others = set(re.findall(r"#[0-9a-f]{6}", json.dumps({k: v for k, v in data.items() if k not in skip}).lower()))
        others |= set(re.findall(r"#[0-9a-f]{6}", (ROOT / "engine.py").read_text(encoding="utf-8").lower()))
        others -= tiers

        def rgb(c):
            return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))

        def contrast(c):
            def lin(v):
                v /= 255
                return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            r, g, b = (lin(v) for v in rgb(c))
            return (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05) / 0.05

        for t in tiers:
            self.assertGreaterEqual(contrast(t), 4.5, t)
            for o in others:
                self.assertGreaterEqual(math.dist(rgb(t), rgb(o)), 60, (t, o))


if __name__ == "__main__":
    unittest.main()
