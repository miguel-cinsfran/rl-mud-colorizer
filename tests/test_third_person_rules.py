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
    COLOR = "#1a9a1a"  # darker than the own blow ("Propinas el golpe mortal a X", #00ff00)
    TEMPLATES = ("{a} propina el golpe mortal a {b}.", "{a} se propina el golpe mortal.")
    NEGATIVES = (
        "Dices: '{a} propina el golpe mortal a {b}.'",
        "{a} te dice: {a} propina el golpe mortal a {b}.",
        "[Chat] {a}: {a} se propina el golpe mortal.",
        "Dices a {a}: {a} se propina el golpe mortal.",
    )


class HealOther(Cases, unittest.TestCase):
    COLOR = "#ff00f3"  # enemy-spell magenta, apart from our own heal ("Curas ...", #ff0000)
    TEMPLATES = tuple(
        "{a} cura algunas de sus heridas más " + severity + "."
        for severity in ("ligeras", "moderadas", "serias", "críticas")
    )
    NEGATIVES = (
        "Dices: '{a} cura algunas de sus heridas más ligeras.'",
        "{a} te dice: {b} cura algunas de sus heridas más serias.",
        "[Chat] {a}: {b} cura algunas de sus heridas más críticas.",
    )


class EnemyManeuverWarnings(unittest.TestCase):
    """"! X ..." maneuver warnings get the friend's maneuver colors, whatever the verb."""

    @classmethod
    def setUpClass(cls):
        cls.c = make_colorizer()

    def test_new_warnings_match_the_existing_one(self):
        reference = colors(self.c, "! Zorak se prepara para ejecutar tajar sobre ti.")
        for name in NAMES:
            for tail in (
                "comienza a realizar los movimientos rituales movimientos rituales de una maniobra de Khaldar.",
                "comienza a moverse tentativamente a tu alrededor, buscando un flanco desprotegido sobre el que abalanzarse.",
            ):
                line = f"! {name} {tail}"
                with self.subTest(line=line):
                    self.assertEqual(colors(self.c, line), reference)


class TouchCast(Cases, unittest.TestCase):
    COLOR = "#008080"  # same as the "Pronuncias el cántico:" prefix
    TEMPLATES = ("Tocas a {a} mientras formulas el hechizo.",)
    NEGATIVES = (
        "Dices: 'Tocas a {a} mientras formulas el hechizo.'",
        "{a} te dice: Tocas a {b} mientras formulas el hechizo.",
        "[Chat] {a}: Tocas a {b} mientras formulas el hechizo.",
    )

    def test_negatives_stay_uncolored_by_this_rule(self):
        # Chat lines are legitimately teal-prefixed by the chat rules, so check the rule itself.
        rule = next(r for r in self.c.compiled_rules if r["id"] == "spell_touch_cast")
        for tpl in self.NEGATIVES:
            for a in NAMES[:3]:
                line = tpl.format(a=a, b=NAMES[1])
                with self.subTest(line=line):
                    self.assertIsNone(rule["_regex"].match(line))

    def test_same_color_as_chant_prefix(self):
        chant = colors(self.c, "Pronuncias el cántico: 'abc'")
        self.assertIn(self.COLOR, chant)


class EnemyConcentrates(Cases, unittest.TestCase):
    COLOR = "#ff00f3"  # same as "X mueve la boca mientras dice..." (spell_cast_enemy*)
    TEMPLATES = ("{a} se concentra en un hechizo.", "{a} se concentra en un oscuro hechizo.")
    NEGATIVES = (
        "Dices: '{a} se concentra en un hechizo.'",
        "{a} te dice: {b} se concentra en un hechizo.",
        "[Chat] {a}: {b} se concentra en un hechizo.",
        "Una intensa luz desciende hasta la zona y se concentra formando la figura de {a}.",
        "{a} se concentra en una brillante gema que sostiene entre sus manos.",
    )

    def test_same_color_as_friend_enemy_cast(self):
        line = "{a} mueve la boca mientras dice lo que para ti son palabras sin sentido.".format(a=NAMES[1])
        self.assertIn(self.COLOR, colors(self.c, line))


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


class OwnDefenseOn(Cases, unittest.TestCase):
    COLOR = "#8cc4ff"
    TEMPLATES = (
        "Eres rodeada por un globo de protección.",
        "Eres rodeado por un intenso aura blanquecino de protección.",
        "Eres envuelta por una protección invisible.",
        "Eres envuelto por una protección invisible.",
        "Eres cubierta por un aura roja brillante.",
        "Un campo de energía forma un escudo mágico ante ti.",
        "Un aura protectora empieza a formarse a tu alrededor.",
    )
    NEGATIVES = (
        "Dices: 'Eres rodeada por un globo de protección.'",
        "{a} te dice: Un campo de energía forma un escudo mágico ante ti.",
        "[Chat] {a}: Eres envuelta por una protección invisible.",
        "Un aura protectora empieza a formarse alrededor de {a}.",
        "Eres rodeada por un grupo de orcos.",
    )


class OwnDamageSpell(Cases, unittest.TestCase):
    COLOR = "#8cc4ff"
    TEMPLATES = (
        "Trazas con ambas manos un rectángulo en el aire y una enorme ventana aparece justo detrás de {a} entre una gran humareda chispeante.",
        "¡Cierras con fuerza sendos puños y una ráfaga mágica sale disparada en dirección a {a}!",
        "¡{a} sale disparada contra la ventana y la revienta estruendosamente, volando 6 metros antes de caer malherida al suelo!",
        "¡{a} sale disparado contra la ventana y la revienta estruendosamente, volando 1 metro antes de caer malherido al suelo!",
        "Tu aura brilla castigando a {a} con el mismo dolor.",
    )
    NEGATIVES = (
        "Dices: 'Tu aura brilla castigando a {a} con el mismo dolor.'",
        "{a} te dice: ¡Cierras con fuerza sendos puños y una ráfaga mágica sale disparada en dirección a {b}!",
        "[Chat] {a}: Trazas con ambas manos un rectángulo en el aire y una enorme ventana aparece justo detrás de {b} entre una gran humareda chispeante.",
        "{a} dice: ¡{b} sale disparada contra la ventana y la revienta estruendosamente, volando 6 metros antes de caer malherida al suelo!",
    )


class DispelledOnYou(Cases, unittest.TestCase):
    COLOR = "#cc6666"
    TEMPLATES = (
        "Sientes como un poder mágico sin igual choca contigo y hace añicos la magia que te rodeaba mientras {a} finaliza su hechizo.",
        "Sientes como un poder mágico sin igual choca contigo y hace añicos la magia que te rodeaba.",
    )
    NEGATIVES = (
        "Dices: 'Sientes como un poder mágico sin igual choca contigo y hace añicos la magia que te rodeaba.'",
        "{a} te dice: Sientes como un poder mágico sin igual choca contigo y hace añicos la magia que te rodeaba mientras {b} finaliza su hechizo.",
        "[Chat] {a}: Sientes como un poder mágico sin igual choca contigo y hace añicos la magia que te rodeaba.",
    )


class EffectEnds(Cases, unittest.TestCase):
    COLOR = "#808080"
    TEMPLATES = (
        "Tu globo de invulnerabilidad empieza a parpadear hasta que desaparece.",
        "Tu escudo de protección se desvanece.",
        "Tu armadura espiritual se desvanece.",
        "El globo que rodea a {a} empieza a parpadear hasta que desaparece.",
        "La regeneración mágica de {a} termina.",
        "{a} parece menos decidido que antes cuando su sortilegio llega a su fin.",
        "{a} parece menos decidida que antes cuando su sortilegio llega a su fin.",
        "Notas como tu hechizo de precognición llega a su fin.",
    )
    NEGATIVES = (
        "Dices: 'La regeneración mágica de {a} termina.'",
        "{a} te dice: {b} parece menos decidido que antes cuando su sortilegio llega a su fin.",
        "[Chat] {a}: La regeneración mágica de {b} termina.",
        "Dices: 'Tu globo de invulnerabilidad empieza a parpadear hasta que desaparece.'",
        "{a} te dice: El globo que rodea a {b} empieza a parpadear hasta que desaparece.",
    )


class OutputSpacing(unittest.TestCase):
    def test_lines_end_like_mudlet_copy_as_html(self):
        # Mudlet's TBuffer::bufferToHtml ends every line with "<br>\n"; Deathlogs accepts that format.
        out = make_colorizer().colorize_text("a\nb\nc")
        body = out.split("<body><div>", 1)[1].rsplit("</div></body>", 1)[0]
        self.assertEqual(len(re.findall("<br>\n", body)), 3)
        self.assertTrue(out.endswith("<br>\n </div></body>\n</html>"))


if __name__ == "__main__":
    unittest.main()
