"""Item names keep the game's colors inside plain text, run by run."""

import json
import unittest

from _common import ROOT

from engine import RLColorizer
from tools.build_item_colors import name_runs


def span(rgb, text):
    return f'<span style="color: rgb({rgb}); background: rgb(0,0,0); ">{text}</span>'


class ItemOverlay(unittest.TestCase):
    def make(self):
        return RLColorizer(config={
            "rules": [
                {"id": "hit", "priority": 1, "pattern": r"^(Te golpea .*)$",
                 "replace": '<span style="color: #ff0000;">$1</span>'},
            ],
            "item_colors": {
                "Capucha Tenebrosa": [[8, "#c0c0c0"], [9, "#800080"]],
                "Espada Azul": [[11, "#0000ff"]],
                "Espada Azul Larga": [[17, "#00ff00"]],
                "Pin 'Yo'": [[4, "#ffff00"], [4, "#00ff00"]],
            },
        })

    def test_runs_inside_plain_line(self):
        out = self.make().colorize_line(" * Cabeza:  Capucha Tenebrosa.")
        self.assertEqual(out, span("192,192,192", " * Cabeza:  Capucha ") + span("128,0,128", "Tenebrosa")
                         + span("192,192,192", "."))

    def test_longest_name_wins(self):
        out = self.make().colorize_line("Empuñas tu Espada Azul Larga.")
        self.assertIn(span("0,255,0", "Espada Azul Larga"), out)

    def test_name_must_stand_alone(self):
        out = self.make().colorize_line("Espada Azules y MiEspada Azul.")
        self.assertEqual(out, span("192,192,192", "Espada Azules y MiEspada Azul."))

    def test_escaped_characters_survive(self):
        out = self.make().colorize_line("Usando: Pin 'Yo' & <nada>.")
        self.assertIn(span("0,255,0", "&#x27;Yo&#x27;"), out)
        self.assertIn("&amp; &lt;nada&gt;.", out)

    def test_lines_colored_by_rules_are_left_alone(self):
        out = self.make().colorize_line("Te golpea con su Espada Azul.")
        self.assertEqual(out, span("255,0,0", "Te golpea con su Espada Azul."))


class CatalogConversion(unittest.TestCase):
    def test_bold_gives_bright_and_reset_goes_back_to_silver(self):
        raw = "%^RED%^P%^BOLD%^eto%^RESET%^ x"
        self.assertEqual(name_runs(raw, "Peto x"), [[1, "#800000"], [3, "#ff0000"], [2, "#c0c0c0"]])

    def test_codes_share_delimiters(self):
        self.assertEqual(name_runs("%^BOLD%^BLUE%^Espada Azul%^RESET%^", "Espada Azul"), [[11, "#0000ff"]])

    def test_orange_and_yellow_as_mudlet_shows_them(self):
        self.assertEqual(name_runs("%^ORANGE%^Hoja", "Hoja"), [[4, "#808000"]])
        self.assertEqual(name_runs("%^YELLOW%^Faja", "Faja"), [[4, "#ffff00"]])

    def test_compiled_rules_carry_the_items(self):
        with open(ROOT / "rules.json", encoding="utf-8") as f:
            items = json.load(f)["item_colors"]
        self.assertGreater(len(items), 2000)
        self.assertEqual(items["Espada Azul"], [[11, "#0000ff"]])


if __name__ == "__main__":
    unittest.main()
