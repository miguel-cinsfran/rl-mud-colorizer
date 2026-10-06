"""Type-ahead / mid-login credential leaks, drop_before and drop_secret (Python and JS)."""

import json
import shutil
import subprocess
import unittest

from _common import FIXTURES, ROOT, fixture_text, make_colorizer, visible_lines

SECRETS = ("fakeuser", "fakepass123")
NAMES = (
    "vipmud_login_case_a.txt",
    "vipmud_login_case_b.txt",
    "vipmud_login_case_a_head.txt",
    "vipmud_login_case_c.txt",
    "vipmud_login_case_d.txt",
    "vipmud_login_case_e.txt",
    "vipmud_login_case_f.txt",
    "vipmud_login.txt",
)
NODE = shutil.which("node")


def run(rules, text):
    c = make_colorizer(rules, [])
    return c.preprocess_text(text).split("\n")


class DropBeforeTest(unittest.TestCase):
    RULE = {"id": "b", "kind": "drop_before", "pattern": r"^PROMPT", "candidate": r"^\S{1,10}$", "max_lines": 2}

    def test_removes_preceding_tokens_skipping_blanks(self):
        self.assertEqual(run([self.RULE], "text here\n\nuser\n\npass\nPROMPT\nafter"), ["text here", "", "PROMPT", "after"])

    def test_respects_max_lines(self):
        self.assertEqual(run([self.RULE], "a\nb\nc\nPROMPT"), ["a", "PROMPT"])

    def test_stops_at_first_non_candidate(self):
        self.assertEqual(run([self.RULE], "some prose\nuser\nPROMPT"), ["some prose", "PROMPT"])

    def test_nothing_before_is_fine(self):
        self.assertEqual(run([self.RULE], "PROMPT"), ["PROMPT"])


class DropSecretTest(unittest.TestCase):
    RULES = [
        {"id": "a", "kind": "drop_after", "pattern": r"^PROMPT", "until": r"^SERVER", "record": r"^\S{1,10}$", "login": True},
        {"id": "s", "kind": "drop_secret", "window": 2},
    ]

    def test_recorded_token_is_dropped_inside_the_login_window_only(self):
        text = "PROMPT\npw\nSERVER\npw\nx\ny\npw"
        self.assertEqual(run(self.RULES, text), ["SERVER", "x", "y", "pw"])

    def test_gameplay_commands_equal_to_a_token_are_kept_outside_login(self):
        self.assertEqual(run(self.RULES, "n\ns\nPROMPT\nn\nSERVER\nx\nx\nn"), ["n", "s", "SERVER", "x", "x", "n"])


class TypeAheadFixtureTest(unittest.TestCase):
    def test_python_never_outputs_credentials(self):
        c = make_colorizer()
        for name in NAMES:
            text = fixture_text(name)
            pre = c.preprocess_text(text)
            html_out = c.colorize_text(text)
            for secret in SECRETS:
                self.assertNotIn(secret, pre, name)
                self.assertNotIn(secret, html_out, name)
            for marker in ("Introduce", "LPmud", "recuperar clave", "Los Dioses"):
                self.assertNotIn(marker, pre, name)

    def test_case_a_keeps_game_output(self):
        c = make_colorizer()
        visible = visible_lines(c.colorize_text(fixture_text("vipmud_login_case_a.txt")))
        self.assertIn("Anduar: Plaza Mayor [|so|,s,e,n,o]", [l.rstrip() for l in visible])
        self.assertEqual(visible[-1], "n")

    def test_case_b_keeps_text_before_the_credentials_and_game_output(self):
        c = make_colorizer()
        pre = c.preprocess_text(fixture_text("vipmud_login_case_b.txt")).split("\n")
        self.assertIn("                    posible que el MUD siga mejorando.", pre)
        self.assertEqual([l for l in pre if l][-1], "s")

    def test_fragment_without_end_marker_keeps_game_output(self):
        c = make_colorizer()
        pre = c.preprocess_text(fixture_text("vipmud_login_case_c.txt"))
        self.assertIn(r"Pv:2611\2611 Pe:625\688 Xp:1231367", pre)
        self.assertIn("Estás siendo atacada por Agricultora.", pre)

    def test_head_only_fragment_leaves_nothing(self):
        c = make_colorizer()
        self.assertEqual(c.preprocess_text(fixture_text("vipmud_login_case_a_head.txt")).strip(), "")


@unittest.skipUnless(NODE, "node is not on PATH: skipping JS leak tests")
class TypeAheadFixtureJsTest(unittest.TestCase):
    def test_js_never_outputs_credentials_and_matches_python(self):
        paths = [FIXTURES / n for n in NAMES]
        proc = subprocess.run(
            [NODE, str(ROOT / "tests" / "parity_runner.js"), str(ROOT / "rules.json")] + [str(p) for p in paths],
            capture_output=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout.decode("utf-8"))
        c = make_colorizer()
        for p in paths:
            js = result[str(p)]
            text = fixture_text(p.name)
            self.assertEqual(js["preprocessed"], c.preprocess_text(text), p.name)
            self.assertEqual(js["html"], c.colorize_text(text), p.name)
            for secret in SECRETS:
                self.assertNotIn(secret, js["preprocessed"], p.name)
                self.assertNotIn(secret, js["html"], p.name)


class UnderAttackPromptTest(unittest.TestCase):
    def test_prompt_prefix_is_kept(self):
        c = make_colorizer()
        out = c.colorize_text("> Estás siendo atacada por Momia.")
        self.assertIn("> Estás siendo atacada por Momia.", visible_lines(out))
        self.assertIn("rgb(255,0,0)", out)


if __name__ == "__main__":
    unittest.main()
