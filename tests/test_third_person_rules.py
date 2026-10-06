"""Third-person combat/spell rules: generic names (accents, commas, several words) and no chat leaks."""

import re
import unittest

from _common import make_colorizer
from tools import evaluate as ev

NAMES = ["Zorak", "Esqueleto del Túmulo", "Cvstodes III, el Pecio animado", "Ñandú"]


def colors(colorizer, line):
    """Set of non-default colors in the rendered line."""
    parsed = ev.parse_html_log("<body>" + colorizer.colorize_line(line))[0]
    return {c for ch, c in parsed if not ch.isspace()} - {"#c0c0c0"}


def whole_line_color(colorizer, line):
    parsed = ev.parse_html_log("<body>" + colorizer.colorize_line(line))[0]
    found = {c for ch, c in parsed if not ch.isspace()}
    return found.pop() if len(found) == 1 else None


class Cases:
    """Mixin: subclasses set COLOR, TEMPLATES (with {a} / {b} for names) and NEGATIVES."""

    COLOR = None
    TEMPLATES = ()
    NEGATIVES = ()

    @classmethod
    def setUpClass(cls):
        cls.c = make_colorizer()

    def test_positive_with_several_names(self):
        for tpl in self.TEMPLATES:
            for a in NAMES:
                for b in NAMES:
                    line = tpl.format(a=a, b=b)
                    with self.subTest(line=line):
                        self.assertEqual(whole_line_color(self.c, line), self.COLOR)

    def test_prompt_prefix_does_not_break_it(self):
        line = "> " + self.TEMPLATES[0].format(a=NAMES[1], b=NAMES[2])
        self.assertEqual(colors(self.c, line), {self.COLOR})

    def test_negatives_stay_uncolored_by_this_rule(self):
        for tpl in self.NEGATIVES:
            for a in NAMES[:3]:
                line = tpl.format(a=a, b=NAMES[1])
                with self.subTest(line=line):
                    self.assertNotIn(self.COLOR, colors(self.c, line))


class FatalBlowThird(Cases, unittest.TestCase):
    COLOR = "#00ff00"
    TEMPLATES = ("{a} propina el golpe mortal a {b}.", "{a} se propina el golpe mortal.")
    NEGATIVES = (
        "Dices: '{a} propina el golpe mortal a {b}.'",
        "{a} te dice: {a} propina el golpe mortal a {b}.",
        "[Chat] {a}: {a} se propina el golpe mortal.",
        "Dices a {a}: {a} se propina el golpe mortal.",
    )


class ReflectedSpells(Cases, unittest.TestCase):
    COLOR = "#8cc4ff"
    TEMPLATES = (
        "¡Tu hechizo de devolver conjuro se activa y fuerza al de {a} a cambiar su objetivo hacia si misma!",
        "¡Tu hechizo de devolver conjuro se activa y fuerza al de {a} a cambiar su objetivo hacia si mismo!",
        "¡El Ojo de tu cinturón brilla y fuerza al hechizo de {a} a cambiar su objetivo hacia si misma!",
        "El rayo convocado por {a} se vuelve contra él electrocutándole al impactar sobre su pecho.",
        "La magia de {a} se vuelve contra ella cuando sus 5 misiles mágicos impactan en su cuerpo.",
    )
    NEGATIVES = (
        "Dices: 'El rayo convocado por {a} se vuelve contra él electrocutándole.'",
        "{a} te dice: El rayo convocado por {a} se vuelve contra él.",
        "[Chat] {a}: ¡Tu hechizo de devolver conjuro se activa y fuerza al de {b} a cambiar su objetivo hacia si mismo!",
        "Parece que El rayo convocado por {a} se vuelve contra él electrocutándole. no produjo efecto alguno.",
    )


class ReflectEnds(Cases, unittest.TestCase):
    COLOR = "#808080"
    TEMPLATES = ("Tu hechizo de devolver conjuro llega a su fin.", "Tu hechizo de devolver conjuro mayor llega a su fin.")
    NEGATIVES = (
        "{a} te dice: Tu hechizo de devolver conjuro llega a su fin.",
        "Dices: 'Tu hechizo de devolver conjuro llega a su fin.'",
    )


class RedirectedToYou(Cases, unittest.TestCase):
    COLOR = "#cc6666"
    TEMPLATES = ("¡El hechizo de {a} cambia de objetivo hacia ti!",)
    NEGATIVES = ("{a} te dice: ¡El hechizo de {b} cambia de objetivo hacia ti!",)


class HowlSequence(Cases, unittest.TestCase):
    COLOR = "#cc6666"
    TEMPLATES = (
        "{a} emite un aullido penetrante, demoníaco, infernal, destrozándote los tímpanos.",
        "¡Te retuerces de dolor cuando el atronador aullido de {a} penetra en tu cabeza, destrozándote los timpanos!",
        "{a} parece no ser consciente de los sonidos que le rodean.",
        "¡Tus tímpanos revientan dejándote sorda!",
        "¡UUUUUUUUUOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOORRRRRRH!",
        "De pronto el mundo a tu alrededor queda en silencio.",
    )
    NEGATIVES = (
        "Dices: '{a} emite un aullido penetrante, demoníaco, infernal, destrozándote los tímpanos.'",
        "{a} te dice: ¡Te retuerces de dolor cuando el atronador aullido de {b} penetra en tu cabeza!",
        "[Chat] {a}: {b} parece no ser consciente de los sonidos que le rodean.",
        "{a} emite un cautivador y penetrante aullido que llena el aire diurno con una sinfonía salvaje.",
        "Dices a {a}: ¡Tus tímpanos revientan dejándote sorda!",
    )


class OutputSpacing(unittest.TestCase):
    def test_output_has_no_newline_after_br(self):
        out = make_colorizer().colorize_text("a\nb\nc")
        body = out.split("<body><div>", 1)[1].rsplit("</div></body>", 1)[0]
        self.assertNotIn("<br>\n", body)
        self.assertEqual(len(re.findall("<br>", body)), 3)


if __name__ == "__main__":
    unittest.main()
