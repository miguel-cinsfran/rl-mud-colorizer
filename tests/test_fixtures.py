"""Expected-output assertions on the curated fixtures (presence/absence of lines and key spans)."""

import re
import unittest

from _common import FIXTURES, fixture_text, make_colorizer, visible_lines
from engine import decode_log_bytes

RED = "color: rgb(255,0,0)"
OLIVE = "color: rgb(113,113,0)"
SALMON = "color: rgb(255,128,128)"
LIGHT_BLUE = "color: rgb(140,196,255)"
BLUE = "color: rgb(8,0,255)"
STATUS_PREFIXES = ("SL:", "PL:", "Jgd:")
LONE_PROMPT = re.compile(r"^[>\]]\s*$")


def preprocessed(name, client=None):
    c = make_colorizer()
    return c.preprocess_text(fixture_text(name), client).split("\n"), c


class StatusDedupeFixtureTest(unittest.TestCase):
    NAME = "vipmud_status_dedupe.txt"

    def test_fixture_is_short_and_has_repeated_blocks(self):
        raw = fixture_text(self.NAME).split("\n")
        self.assertLessEqual(len(raw), 80)
        self.assertGreaterEqual(sum(1 for l in raw if l.startswith("Pv:")), 4)

    def test_client_is_detected_as_vipmud(self):
        _, c = preprocessed(self.NAME)
        self.assertEqual(c.detected_client, "vipmud")

    def test_redundant_status_lines_are_gone(self):
        lines, _ = preprocessed(self.NAME)
        for prefix in STATUS_PREFIXES:
            self.assertFalse([l for l in lines if l.startswith(prefix)], prefix)

    def test_unchanged_values_are_kept_only_once(self):
        lines, _ = preprocessed(self.NAME)
        self.assertEqual([l for l in lines if l.startswith("Pv:")], ["Pv:2841\\2841 Pe:884\\904 Xp:1643412"])
        self.assertEqual([l for l in lines if l.startswith("Pieles:")], ["Pieles:0"])
        self.assertEqual([l for l in lines if l.startswith("Im")], ["Imágenes:9"])

    def test_closing_prompt_only_survives_after_a_block_that_kept_something(self):
        lines, _ = preprocessed(self.NAME)
        self.assertEqual(len([l for l in lines if LONE_PROMPT.match(l)]), 1)

    def test_game_output_is_preserved(self):
        lines, _ = preprocessed(self.NAME)
        for expected in (
            "Y502: Salina abrasada [o,e,s] ",
            "Momia, Cometa de piel y Fantasma están aquí.",
            "Parece que norte no produjo efecto alguno.",
            "o",
        ):
            self.assertIn(expected, lines)

    def test_no_stacked_blank_lines(self):
        lines, _ = preprocessed(self.NAME)
        for a, b in zip(lines, lines[1:]):
            self.assertFalse(a.strip() == "" and b.strip() == "")

    def test_colorized_output_keeps_visible_text_and_colors(self):
        c = make_colorizer()
        out = c.colorize_text(fixture_text(self.NAME))
        visible = visible_lines(out)
        self.assertIn("Pv:2841\\2841 Pe:884\\904 Xp:1643412", visible)
        self.assertIn("Estás siendo atacada por Fantasma.", visible)
        self.assertIn(RED + "; background: rgb(0,0,0); \">Estás siendo atacada por Fantasma.", out)
        self.assertIn(OLIVE, out)  # echoed bare command "o"
        # exits are colorized as room line even with door markers
        self.assertIn("rgb(0,255,255); background: rgb(0,0,0); \">[o,e,so]", out)

    def test_pv_prompt_with_backslash_is_colorized_as_prompt(self):
        c = make_colorizer()
        html_line = c.colorize_line("Pv:2841\\2841 Pe:884\\904 Xp:1643412")
        self.assertEqual(html_line.count("<span"), 1)
        self.assertIn("color: rgb(0,128,0)", html_line)
        self.assertIn("Pv:2841\\2841 Pe:884\\904 Xp:1643412", html_line)


class MidBlockFragmentTest(unittest.TestCase):
    NAME = "vipmud_fragment_midblock.txt"

    def test_fixture_starts_in_the_middle_of_a_status_block(self):
        raw = fixture_text(self.NAME).split("\n")
        self.assertTrue(raw[0].startswith("SL:"))
        self.assertLessEqual(len(raw), 80)

    def test_fragment_is_cleaned_without_banner(self):
        lines, c = preprocessed(self.NAME)
        self.assertEqual(c.detected_client, "vipmud")
        for prefix in STATUS_PREFIXES:
            self.assertFalse([l for l in lines if l.startswith(prefix)])
        # first occurrence in this input is kept (dedupe state starts empty)
        self.assertEqual(lines[0], "Imágenes:9")
        self.assertEqual(lines[1], "Pieles:0")
        self.assertEqual(len([l for l in lines if l.startswith("Pv:")]), 1)

    def test_tiny_fragments_do_not_crash(self):
        c = make_colorizer()
        for text in ("", "\n", "> ", "PL:", "Jgd:Koch (Org)\n> ", "SL: [n]\nPL:\nJgd:\n> \n"):
            c.preprocess_text(text)
            c.colorize_text(text)
        self.assertEqual(c.preprocess_text("Jgd:Koch (Org)\n> \nfoo"), "foo")


class LoginSanitizationTest(unittest.TestCase):
    NAME = "vipmud_login.txt"
    SECRETS = ("fakeuser", "fakepass123")
    LOGIN_MARKERS = (
        "Introduce",
        "recuperar clave",
        "LPmud",
        "Mudlib",
        "Los Dioses",
        "Foro oficial",
        "Normas",
        "Comunidad y recursos",
        "192.0.2.1",
        "Eireapedia",
        "orbita a Eirea",
    )

    def test_credentials_and_login_region_never_reach_the_output(self):
        c = make_colorizer()
        cleaned = c.preprocess_text(fixture_text(self.NAME))
        html_out = c.colorize_text(fixture_text(self.NAME))
        for token in self.SECRETS + self.LOGIN_MARKERS:
            self.assertNotIn(token, cleaned, token)
            self.assertNotIn(token, html_out, token)

    def test_game_output_after_the_motd_survives(self):
        lines, _ = preprocessed(self.NAME)
        self.assertIn("Anduar: Plaza Mayor [|so|,s,e,n,o]", [l.rstrip() for l in lines])
        self.assertIn("[Chat] Eldhana: hola", lines)
        self.assertIn("Zeh (Mdro), Koch (Org) y Zrunk (Org) están aquí.", lines)

    def test_login_rules_do_not_depend_on_client_detection(self):
        text = 'Introduce el nombre de tu personaje:<VERSION>\n\nfakeuser\nfakepass123\nEscribe "recuperar clave" si has olvidado tu clave.\nIntroduce la clave de tu ficha o de tu cuenta: \nfakepass123\n\nTu personaje ya se encuentra en Reinos de Leyenda.\nCamino de Amonmen [se,no]'
        c = make_colorizer()
        self.assertEqual(
            c.preprocess_text(text).split("\n"),
            ["Tu personaje ya se encuentra en Reinos de Leyenda.", "Camino de Amonmen [se,no]"],
        )

    def test_echo_after_password_prompt_is_dropped_even_without_banner_or_motd(self):
        text = "Introduce la clave de tu ficha o de tu cuenta: \nfakepass123\nfakeuser\n\n            Los Dioses te dan la bienvenida a sus Reinos de Leyenda, Fakechar.\nfoo"
        c = make_colorizer()
        out = c.preprocess_text(text)
        for token in self.SECRETS:
            self.assertNotIn(token, out)
        self.assertNotIn("Introduce", out)

    def test_truncated_motd_is_kept_but_last_connection_ip_is_dropped(self):
        text = "- Tu última conexión fue el 24-Sep-26 (1:25) desde la IP 192.0.2.1\n- Tienes 1 correo sin leer.\nfoo"
        c = make_colorizer()
        self.assertEqual(c.preprocess_text(text), "- Tienes 1 correo sin leer.\nfoo")

    def test_unterminated_banner_is_not_swallowed(self):
        lines = ["LPmud version: fluffos 063a160d RLII."] + ["Algo de salida del juego %d." % i for i in range(120)]
        c = make_colorizer()
        out = c.preprocess_text("\n".join(lines)).split("\n")
        self.assertEqual(len(out), len(lines))


class PvpCombatFixtureTest(unittest.TestCase):
    NAME = "vipmud_pvp_combat.txt"

    def setUp(self):
        self.c = make_colorizer()
        self.out = self.c.colorize_text(fixture_text(self.NAME))
        self.visible = visible_lines(self.out)

    def test_fixture_size(self):
        self.assertLessEqual(len(fixture_text(self.NAME).split("\n")), 80)

    def test_combat_prompt_is_kept_and_deltas_colored(self):
        self.assertIn("Pvs: 1676/2611 (-935) Pe: 398/688 (-18)", self.visible)
        self.assertIn(RED + "; background: rgb(0,0,0); \">-935</span>", self.out)

    def test_status_noise_removed(self):
        for prefix in STATUS_PREFIXES:
            self.assertFalse([l for l in self.visible if l.startswith(prefix)])
        self.assertEqual(len([l for l in self.visible if l.startswith("Pv:")]), 2)  # 1611 and 1676 differ

    def test_other_player_uses_race_color(self):
        self.assertIn("Mortas (Hum) se va hacia norte.", self.visible)
        self.assertIn("color: rgb(255,255,0); background: rgb(0,0,0); \">Mortas (Hum)", self.out)

    def test_spell_messages(self):
        self.assertIn("Pronuncias el cántico: 'majos areos corrosiv'", self.visible)
        self.assertIn(SALMON + "; background: rgb(0,0,0); \">El destino de tu hechizo está fuera de alcance.", self.out)

    def test_echoed_commands_are_command_colored(self):
        for cmd in ("f1", "n", "ne", "e"):
            self.assertIn(OLIVE + "; background: rgb(0,0,0); \">%s</span>" % cmd, self.out)


class NewColorizingRulesTest(unittest.TestCase):
    def setUp(self):
        self.c = make_colorizer()

    def line(self, text):
        return self.c.colorize_line(text)

    def test_under_attack_accepts_both_genders(self):
        for text in ("Estás siendo atacada por Ahogada.", "Estás siendo atacado por Ahogado."):
            self.assertIn(RED, self.line(text))

    def test_projectile_conjuring_messages(self):
        for text in (
            "Conjuras un arco envuelto en llamas, y las bocanadas ígneas que de él brotan dan forma a una flecha.",
            "Tu arco desaparece en una nube de humo sulfuroso.",
            "La flecha que lanzaste a Momia se desmaterializa.",
        ):
            self.assertIn(LIGHT_BLUE, self.line(text), text)

    def test_spell_preparation(self):
        self.assertIn(BLUE, self.line("Preparas los componentes del hechizo."))
        self.assertIn("rgb(0,255,255)", self.line("Te concentras en el hechizo 'armadura espiritual'."))

    def test_spell_failure_messages(self):
        self.assertIn(SALMON, self.line("Has agotado la energía necesaria para formular 'Toque vampirico' y debes descansar."))

    def test_spell_completion_quotes(self):
        out = self.line("Finalizas el hechizo 'disipar magia' y destruyes los hechizos que te afectaban.")
        self.assertIn("rgb(0,255,255)", out)

    def test_marker_symbol_is_colored_by_kind_and_body_keeps_its_rule_colors(self):
        hit = self.line("# Pinchas con fuerza en el pecho a Redrich (120-159)")
        self.assertIn('rgb(0,128,0); background: rgb(0,0,0); ">#</span>', hit)
        self.assertIn("rgb(0,255,0)", hit)  # body keeps the combat green
        self.assertIn("rgb(255,0,0)", hit)  # and the damage number highlight
        miss = self.line("# Zhobirat esquiva tu ataque con un rápido giro del cuerpo.")
        self.assertIn('rgb(128,0,128); background: rgb(0,0,0); ">#</span>', miss)
        self.assertIn("rgb(128,128,128)", miss)  # dodge body keeps the gray
        incoming = self.line("* Greszhx te golpea con sus garras.")
        self.assertIn('rgb(128,0,0); background: rgb(0,0,0); ">*</span>', incoming)
        self.assertIn("rgb(204,102,102)", incoming)

    def test_imagenes_counter_like_pieles(self):
        out = self.line("Imágenes:9")
        self.assertIn("rgb(255,255,0)", out)
        self.assertEqual(out, self.line("Pieles:9").replace("Pieles:", "Imágenes:"))

    def test_bare_commands(self):
        for cmd in ("enterrar cuerpos", "f12", "ven 3", "seguir koch", "fu"):
            self.assertEqual(self.line(cmd).count(OLIVE), 1, cmd)

    def test_bare_command_rule_does_not_color_game_prose(self):
        for text in ("Cartel.", "El trigo es mecido por el suave viento de la zona.", "segundos."):
            self.assertNotIn(OLIVE, self.line(text), text)


class DecodingTest(unittest.TestCase):
    def test_utf8_is_preferred(self):
        self.assertEqual(decode_log_bytes("Estás aquí".encode("utf-8")), "Estás aquí")

    def test_cp1252_fallback(self):
        raw = "Estás siendo atacada\r\nImágenes:3\r\n".encode("cp1252")
        self.assertEqual(decode_log_bytes(raw), "Estás siendo atacada\r\nImágenes:3\r\n")

    def test_utf8_bom_is_removed(self):
        self.assertEqual(decode_log_bytes(b"\xef\xbb\xbfhola"), "hola")

    def test_cp1252_crlf_log_end_to_end(self):
        text = "Pv:1\\1 Pe:2\\2 Xp:3\r\nSL: [n]\r\nPL:\r\nJgd:\r\n> \r\nEstás siendo atacada por Momia.\r\n"
        c = make_colorizer()
        out = c.colorize_text(decode_log_bytes(text.encode("cp1252")))
        self.assertIn("Estás siendo atacada por Momia.", visible_lines(out))
        self.assertNotIn("\r", out)


class MudletFixtureTest(unittest.TestCase):
    NAME = "mudlet_excerpt.txt"

    def test_mudlet_text_is_not_altered_by_preprocess(self):
        c = make_colorizer()
        text = fixture_text(self.NAME)
        self.assertEqual(c.preprocess_text(text), text.replace("\r\n", "\n"))
        self.assertIsNone(c.detected_client)

    def test_output_identical_with_and_without_preprocess(self):
        c = make_colorizer()
        text = fixture_text(self.NAME)
        self.assertEqual(c.colorize_text(text), c.colorize_text(text, preprocess=False))

    def test_fixture_dir_has_no_obvious_secrets(self):
        for path in FIXTURES.glob("*.txt"):
            content = path.read_text(encoding="utf-8")
            self.assertNotRegex(content, r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b(?<!192\.0\.2\.1)", path.name)


if __name__ == "__main__":
    unittest.main()
