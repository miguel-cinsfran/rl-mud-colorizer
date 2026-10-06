"""Room-title colors: legibility of the compiled tables and the map > catalog > fallback order."""

import json
import unittest

from _common import ROOT

import build_rules as br
from engine import RLColorizer


def compiled_colors(config):
    colors = list(config["room_colors"].values())
    colors += list(config["room_map_colors"]["names"].values())
    colors += list(config["room_map_colors"]["zones"].values())
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


if __name__ == "__main__":
    unittest.main()
