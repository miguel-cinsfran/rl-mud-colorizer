"""Room-title colors: legibility of the compiled tables and the map > catalog > fallback order."""

import json
import re
import unittest

from _common import ROOT

import build_rules as br
from engine import RLColorizer


def compiled_colors(config):
    colors = list(config["room_colors"].values())
    colors += list(config["room_map_colors"]["names"].values())
    colors += list(config["room_map_colors"]["zones"].values())
    colors += list(config["room_reference_colors"]["zones"].values())
    colors += [c for runs in config["room_reference_colors"]["names"].values() for _, c in runs]
    colors.append(config["room_fallback_color"])
    return colors


class CompiledTablesLegibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ROOT / "rules.json", encoding="utf-8") as f:
            cls.config = json.load(f)
        cls.colors = compiled_colors(cls.config)

    def test_tables_are_not_empty(self):
        self.assertGreater(len(self.config["room_map_colors"]["names"]), 100)
        self.assertGreater(len(self.config["room_colors"]), 100)

    def test_every_color_readable_on_black(self):
        bad = {c for c in self.colors if br.contrast_on_black(c) < br.MIN_CONTRAST}
        self.assertEqual(bad, set())

    def test_no_color_confusable_with_exits(self):
        bad = {c for c in self.colors if br.color_distance(c, br.EXITS_COLOR) < br.MIN_EXITS_DISTANCE}
        self.assertEqual(bad, set())

    def test_make_readable_is_deterministic_and_idempotent(self):
        for raw in ("#000000", "#0000ff", "#00ffff", "#800000", "#ffffff"):
            fixed = br.make_readable(raw)
            self.assertEqual(fixed, br.make_readable(raw))
            self.assertEqual(fixed, br.make_readable(fixed))


class LookupOrder(unittest.TestCase):
    def make(self):
        return RLColorizer(config={
            "rules": [
                {"id": "exits", "type": "composite_room_exits", "priority": 1,
                 "pattern": r"^(?:([>\]])\s*)?(.+?)(\s+)(\[[a-z,]+\])\s*$"},
                {"id": "title", "type": "composite_room_title", "priority": 2,
                 "pattern": r"^(?:([>\]])\s*)?([A-Z][\w ]+:\s+[A-Z][\w ]+)\s*$"},
            ],
            "room_colors": {"plaza: norte": "#ff0000", "plaza: sur": "#00ff00", "bosque": "#ff00ff"},
            "room_map_colors": {"names": {"plaza: norte": "#0000ff"}, "zones": {"mapzone": "#ffff00"}},
            "room_fallback_color": "#ffffff",
        })

    def test_map_beats_catalog(self):
        self.assertEqual(self.make().get_room_color("Plaza: Norte"), ("#0000ff", 12))

    def test_catalog_used_when_map_lacks_it(self):
        self.assertEqual(self.make().get_room_color("Plaza: Sur"), ("#00ff00", 10))

    def test_zone_step_follows_each_source(self):
        c = self.make()
        self.assertEqual(c.get_room_color("MapZone: Algo"), ("#ffff00", 8))
        self.assertEqual(c.get_room_color("Bosque: Claro"), ("#ff00ff", 7))

    def test_unknown_exits_line_gets_white_fallback(self):
        out = self.make().colorize_line("Lugar Raro [norte]")
        self.assertIn('<span style="color: rgb(255,255,255); background: rgb(0,0,0); ">Lugar Raro</span>', out)

    def test_known_title_uses_map_color(self):
        out = self.make().colorize_line("Plaza: Norte [norte]")
        self.assertIn('<span style="color: rgb(0,0,255); background: rgb(0,0,0); ">Plaza: Norte</span>', out)

    def test_title_span_is_emitted_bold_before_normalization(self):
        # Mudlet-style output has no bold attribute; the raw engine span still carries it.
        c = self.make()
        self.assertIn("font-weight: bold", c._room_title_html("Lugar Raro"))
        self.assertIn("font-weight: bold", c._room_title_html("Plaza: Norte"))

    def test_unknown_title_only_line_is_not_a_room(self):
        self.assertIsNone(self.make().get_room_color("Lugar: Raro"))
        self.assertNotIn("font-weight", self.make().colorize_line("Lugar: Raro"))

    def test_known_title_only_line_is_colored(self):
        out = self.make().colorize_line("Plaza: Sur")
        self.assertIn("color: rgb(0,255,0)", out)


class ReferenceTitleRuns(unittest.TestCase):
    """Titles seen in colored Mudlet logs keep the game's colors, even mixed inside the title."""

    def make(self):
        return RLColorizer(config={
            "rules": [
                {"id": "exits", "type": "composite_room_exits", "priority": 1,
                 "pattern": r"^(?:([>\]])\s*)?(.+?)(\s+)(\[[a-z,]+\])\s*$"},
            ],
            "room_colors": {"campos de cultivo": "#ff0000"},
            "room_map_colors": {"names": {"ciudad: calle": "#eac6a6"}, "zones": {}},
            "room_reference_colors": {
                "names": {"campos de cultivo": [[10, "#c0c0c0"], [7, "#ffff00"]],
                          "ciudad: plaza": [[13, "#c0c0c0"]]},
                "zones": {"ciudad": "#c0c0c0"},
            },
            "room_fallback_color": "#ffffff",
        })

    def test_mixed_title_keeps_each_run(self):
        out = self.make().colorize_line("Campos de Cultivo [ne,o]")
        self.assertIn('<span style="color: rgb(192,192,192); background: rgb(0,0,0); ">Campos de </span>'
                      '<span style="color: rgb(255,255,0); background: rgb(0,0,0); ">Cultivo</span>', out)

    def test_reference_zone_beats_map_name(self):
        self.assertEqual(self.make().get_room_runs("Ciudad: Calle"), [(7, "#c0c0c0")])

    def test_silver_titles_of_a_silver_zone_look_alike(self):
        c = self.make()
        self.assertEqual(c.get_room_runs("Ciudad: Plaza"), c.get_room_runs("Ciudad: Calle"))

    def test_runs_ignored_when_length_differs(self):
        self.assertEqual(self.make().get_room_runs("Campos  de Cultivo"), [(18, "#ff0000")])


class SilverTitlesTurnWhite(unittest.TestCase):
    def make(self, color):
        return RLColorizer(config={
            "rules": [
                {"id": "exits", "type": "composite_room_exits", "priority": 1,
                 "pattern": r"^(?:([>\]])\s*)?(.+?)(\s+)(\[[a-z,]+\])\s*$"},
            ],
            "room_colors": {"plaza: norte": color, "bosque": color},
            "room_fallback_color": "#ffffff",
        })

    def title_color(self, color, line="Plaza: Norte [norte]"):
        out = self.make(color).colorize_line(line)
        return re.search(r"color: rgb\((\d+,\d+,\d+)\)[^>]*>(?:Plaza|Bosque)", out).group(1)

    def test_exact_silver_title_is_white(self):
        self.assertEqual(self.title_color("#c0c0c0"), "255,255,255")

    def test_near_silver_title_is_white(self):
        for near in ("#cacdbe", "#bbb7aa", "#b9b9b9"):
            with self.subTest(color=near):
                self.assertEqual(self.title_color(near), "255,255,255")

    def test_distinct_colors_are_kept(self):
        self.assertEqual(self.title_color("#eac6a6"), "234,198,166")
        self.assertEqual(self.title_color("#ff0000"), "255,0,0")

    def test_zone_prefix_match_turns_white_too(self):
        out = self.make("#c0c0c0").colorize_line("Bosque: Claro [norte]")
        self.assertIn('<span style="color: rgb(255,255,255); background: rgb(0,0,0); ">Bosque:</span>', out)


if __name__ == "__main__":
    unittest.main()
