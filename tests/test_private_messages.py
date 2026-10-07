"""Private messages (tells, telepathy): removal rules, the option, and Python/JS parity."""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _common import ACCESSIBILITY_LOGS, FIXTURES, ROOT, make_colorizer, visible_lines
from engine import read_text_file

NODE = shutil.which("node")
COLORIZER = make_colorizer()


def pre(text, hide=True, client=None):
    return COLORIZER.preprocess_text(text, client, hide).split("\n")


class IncomingTellTest(unittest.TestCase):
    def test_incoming_tell_is_removed(self):
        self.assertEqual(pre("antes\nZeh te dice: hola\ndespues"), ["antes", "despues"])

    def test_prompt_prefix_and_other_verbs(self):
        text = "> Zeh te dice: hola\n] Koch te pregunta: que tal?\nRhyzan te exclama: no!\nfin"
        self.assertEqual(pre(text), ["fin"])

    def test_numbered_history_lines_are_removed(self):
        self.assertEqual(pre("26: Zeh te dice: aunque muera\nfin"), ["fin"])

    def test_npc_with_several_words_is_removed_too(self):
        self.assertEqual(pre("Gerardo Manteca el tabernero te dice: Veamos\nfin"), ["fin"])

    def test_public_chat_is_kept(self):
        for line in ("[Chat] Braunk: algo que te dice: hola", "Cantas: te dice: x", "Comerciante dice: Siempre"):
            self.assertEqual(pre(line), [line])

    def test_wrapped_continuation_lines_are_removed(self):
        text = "Rhyzan te dice: parte uno\n    parte dos\n        parte tres\nJuego normal"
        self.assertEqual(pre(text), ["Juego normal"])

    def test_invisibility_notice_after_a_tell_is_removed(self):
        text = "Zeh te dice: hola\n             Debido a tu invisibilidad, a Zeh se le mostro solo un mensaje.\n\nfin"
        self.assertEqual([l for l in pre(text) if l.strip()], ["fin"])

    def test_unindented_line_after_a_tell_is_kept(self):
        self.assertEqual(pre("Zeh te dice: hola\nCampos de Cultivo [ne,o]"), ["Campos de Cultivo [ne,o]"])

    def test_indented_exit_line_is_not_a_continuation(self):
        self.assertEqual(pre("Zeh te dice: hola\n        [s,e,n,o]"), ["        [s,e,n,o]"])


class TelepathyNoticeTest(unittest.TestCase):
    def test_notice_is_removed(self):
        text = "> \nZeh contacta telepáticamente con un infiel.\n\nZeh te dice: hola\nfin"
        self.assertNotIn("contacta", "\n".join(pre(text)))
        self.assertEqual([l for l in pre(text) if l.strip()], ["> ", "fin"])

    def test_notice_without_following_tell_is_removed(self):
        self.assertEqual(pre("Zeh contacta telepáticamente con un infiel.\nfin"), ["fin"])


class OutgoingTellTest(unittest.TestCase):
    def test_echo_directly_above_is_removed_with_the_server_line(self):
        text = "antes\nt Koch hola que tal\nDices a Koch:  hola que tal\ndespues"
        self.assertEqual(pre(text), ["antes", "despues"])

    def test_echo_above_keeps_game_output_in_between(self):
        text = "t Koch hola\nTe vas hacia el norte.\n\nOtro mensaje del juego.\nDices a Koch: hola\nfin"
        self.assertEqual(pre(text), ["Te vas hacia el norte.", "", "Otro mensaje del juego.", "fin"])

    def test_echo_three_lines_above(self):
        text = "tell Koch ya voy\nUn goblin te ataca.\nHieres a un goblin.\nDices a Koch: ya voy\nfin"
        self.assertEqual(pre(text), ["Un goblin te ataca.", "Hieres a un goblin.", "fin"])

    def test_any_alias_is_removed(self):
        for alias in ("t", "tell", "r", "telepatia", "xyz", "t2"):
            with self.subTest(alias=alias):
                text = "%s Koch nos vemos\nDices a Koch: nos vemos\nfin" % alias
                self.assertEqual(pre(text), ["fin"])

    def test_del_char_prefix_and_prompt(self):
        self.assertEqual(pre("\x7ftell Koch hola\nDices a Koch: hola\nfin"), ["fin"])
        self.assertEqual(pre("> t Koch hola\nDices a Koch: hola\nfin"), ["fin"])
        self.assertEqual(pre("] r hola\nDices a Koch: hola\nfin"), ["fin"])

    def test_only_the_most_recent_matching_line_is_removed(self):
        text = "t Koch xd\nDices a Koch: xd\nt Koch xd\nDices a Koch: xd\nfin"
        self.assertEqual(pre(text), ["fin"])

    def test_ask_and_exclaim_forms(self):
        text = "t Zeh que haces?\nPreguntas a Zeh:  que haces?\nt Zeh vamos!\nExclamas a Zeh: vamos!\nfin"
        self.assertEqual(pre(text), ["fin"])

    def test_echo_beyond_lookback_is_kept(self):
        filler = "\n".join("linea %d" % i for i in range(16))
        text = "t Koch hola\n" + filler + "\nDices a Koch: hola\nfin"
        out = pre(text)
        self.assertIn("t Koch hola", out)
        self.assertNotIn("Dices a Koch: hola", out)

    def test_server_line_ending_with_the_message_is_not_taken_for_the_command(self):
        text = "Cantas: hola\nDices a Koch: hola\nfin"
        self.assertEqual(pre(text), ["Cantas: hola", "fin"])
        text = "Ves un cartel que dice hola\nDices a Koch: hola\nfin"
        self.assertEqual(pre(text), ["Ves un cartel que dice hola", "fin"])

    def test_message_must_end_the_line_on_a_word_boundary(self):
        self.assertEqual(pre("t Koch ahola\nDices a Koch: hola\nfin"), ["t Koch ahola", "fin"])

    def test_wrapped_outgoing_message_removes_the_whole_thing(self):
        long_typed = "t Zeh " + "palabra " * 12 + "fin"
        shown = "Dices a Zeh: " + "palabra " * 6
        cont = "      " + "palabra " * 6 + "fin"
        out = pre("\n".join(["antes", long_typed, shown, cont, "", "despues"]))
        self.assertEqual([l for l in out if l.strip()], ["antes", "despues"])

    def test_without_an_echo_only_the_server_line_goes(self):
        self.assertEqual(pre("otra cosa\nDices a Koch: hola\nfin"), ["otra cosa", "fin"])

    def test_empty_message_does_not_crash(self):
        self.assertEqual(pre("t Zeh\nDices a Zeh: \nfin"), ["t Zeh", "fin"])

    def test_fragment_starting_with_the_server_line(self):
        self.assertEqual(pre("Dices a Koch: hola\nfin"), ["fin"])

    def test_removed_count(self):
        COLORIZER.preprocess_text("t Koch hola\nDices a Koch: hola\nZeh te dice: x\n  y\nZeh contacta telepáticamente con un infiel.\nfin")
        self.assertEqual(COLORIZER.private_removed, 5)
        COLORIZER.preprocess_text("fin")
        self.assertEqual(COLORIZER.private_removed, 0)


class OptionTest(unittest.TestCase):
    TEXT = (
        "antes\nZeh contacta telepáticamente con un infiel.\n\nZeh te dice: hola\n    mas texto\n"
        "t Zeh adios\nDices a Zeh: adios\ndespues"
    )

    def test_option_off_keeps_everything(self):
        out = pre(self.TEXT, hide=False)
        self.assertEqual(out, self.TEXT.split("\n"))
        self.assertEqual(COLORIZER.private_removed, 0)

    def test_option_on_removes_private_lines_only(self):
        self.assertEqual([l for l in pre(self.TEXT) if l.strip()], ["antes", "despues"])

    def test_colorize_text_honors_the_option(self):
        on = "\n".join(visible_lines(COLORIZER.colorize_text(self.TEXT)))
        off = "\n".join(visible_lines(COLORIZER.colorize_text(self.TEXT, hide_private=False)))
        self.assertNotIn("te dice:", on)
        self.assertNotIn("Dices a ", on)
        self.assertIn("te dice:", off)
        self.assertIn("Dices a ", off)

    def test_default_hides_private_messages(self):
        self.assertEqual(pre(self.TEXT), pre(self.TEXT, hide=True))

    def test_works_for_both_clients(self):
        vip = "Pv:10\\10 Pe:5\\5 Xp:1\nZeh te dice: hola\nfin"
        mudlet = "Pv: 10 Pe: 5\nZeh te dice: hola\nfin"
        for text in (vip, mudlet):
            self.assertNotIn("te dice", "\n".join(pre(text)))
        self.assertEqual(COLORIZER.detected_client, "mudlet")

    def test_cli_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.txt"
            src.write_text("hola\nZeh te dice: secreto\nfin\n", encoding="utf-8")
            engine = str(ROOT / "engine.py")
            import sys

            on = subprocess.run([sys.executable, engine, str(src)], capture_output=True, timeout=120)
            off = subprocess.run([sys.executable, engine, str(src), "--keep-private"], capture_output=True, timeout=120)
            self.assertNotIn(b"secreto", on.stdout)
            self.assertIn(b"Private lines removed: 1", on.stderr)
            self.assertIn(b"secreto", off.stdout)


class NoTellsSurviveTest(unittest.TestCase):
    TELL = re.compile(r"(?:^|[ >\]:])te (?:dice|pregunta|exclama):|^(?:Dices|Preguntas|Exclamas) a |contacta telepáticamente")

    def test_fixtures_and_accessibility_logs_have_no_private_lines_left(self):
        found = 0
        for path in sorted(FIXTURES.glob("*.txt")) + sorted(ACCESSIBILITY_LOGS.glob("*.txt")):
            text = read_text_file(path)
            raw_hits = sum(1 for l in text.split("\n") if self.TELL.search(l))
            found += raw_hits
            for line in visible_lines(COLORIZER.colorize_text(text)):
                self.assertNotIn("te dice:", line, path.name)
                self.assertNotIn("Dices a ", line, path.name)
                self.assertNotIn("contacta telepáticamente", line, path.name)
        self.assertGreater(found, 30, "the corpus must actually contain tells")


@unittest.skipUnless(NODE, "node is not on PATH: skipping Python/JS parity tests")
class PrivateParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        sample = Path(cls.tmp.name) / "private_sample.txt"
        sample.write_text(
            "Pv:10\\10 Pe:5\\5 Xp:1\nSL: [n]\n> \nZeh contacta telepáticamente con un infiel.\n\n"
            "Zeh te dice: hola\n    mas texto\n\x7ftell Zeh que tal\nTe vas al norte.\nDices a Zeh:  que tal\n\n"
            "Pvs: 1/1\nt Zeh largo " + "palabra " * 6 + "fin\nDices a Zeh: largo " + "palabra " * 3
            + "\n      " + "palabra " * 3 + "fin\nPreguntas a Zeh: \nCantas: hola\nDices a Koch: hola\n",
            encoding="utf-8",
            newline="",
        )
        cls.paths = [sample] + sorted(FIXTURES.glob("*.txt")) + sorted(ACCESSIBILITY_LOGS.glob("*.txt"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_node(self, keep_private):
        cmd = [NODE, str(ROOT / "tests" / "parity_runner.js")]
        if keep_private:
            cmd.append("--keep-private")
        cmd += [str(ROOT / "rules.json")] + [str(p) for p in self.paths]
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
        return json.loads(proc.stdout.decode("utf-8"))

    def check(self, keep_private):
        js = self.run_node(keep_private)
        py = make_colorizer()
        for path in self.paths:
            with self.subTest(file=path.name, keep_private=keep_private):
                text = read_text_file(path)
                hide = not keep_private
                py_pre = py.preprocess_text(text, None, hide)
                py_html = py.colorize_text(text, hide_private=hide)
                removed = py.private_removed
                self.assertEqual(py_pre, js[str(path)]["preprocessed"])
                self.assertEqual(py_html, js[str(path)]["html"])
                self.assertEqual(removed, js[str(path)]["removed"])

    def test_parity_with_the_option_on(self):
        self.check(False)

    def test_parity_with_the_option_off(self):
        self.check(True)

    def test_sample_really_removes_lines(self):
        js = self.run_node(False)
        self.assertGreaterEqual(js[str(self.paths[0])]["removed"], 8)
        self.assertNotIn("te dice", js[str(self.paths[0])]["preprocessed"])


if __name__ == "__main__":
    unittest.main()
