"""Python vs JavaScript engine parity: outputs must be byte-for-byte identical.

Requires `node` on PATH (skipped otherwise).
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _common import ACCESSIBILITY_LOGS, FIXTURES, ROOT, make_colorizer
from engine import read_text_file

NODE = shutil.which("node")


def run_node(paths):
    proc = subprocess.run(
        [NODE, str(ROOT / "tests" / "parity_runner.js"), str(ROOT / "rules.json")] + [str(p) for p in paths],
        capture_output=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError("node failed: " + proc.stderr.decode("utf-8", "replace"))
    return json.loads(proc.stdout.decode("utf-8"))


def first_difference(a, b):
    a_lines, b_lines = a.split("\n"), b.split("\n")
    for i, (x, y) in enumerate(zip(a_lines, b_lines)):
        if x != y:
            return "line %d:\n  PY: %s\n  JS: %s" % (i + 1, x[:300], y[:300])
    return "different line counts: %d vs %d" % (len(a_lines), len(b_lines))


@unittest.skipUnless(NODE, "node is not on PATH: skipping Python/JS parity tests")
class EngineParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)

        # cp1252 + CRLF copy of the login fixture: exercises decoding in both engines
        cp1252 = tmp / "vipmud_login_cp1252.txt"
        cp1252.write_bytes(read_text_file(FIXTURES / "vipmud_login.txt").replace("\n", "\r\n").encode("cp1252"))

        # all fixtures concatenated: several clients' state machines in one input
        combined = tmp / "combined.txt"
        combined.write_text(
            "\n".join(read_text_file(p) for p in sorted(FIXTURES.glob("*.txt"))), encoding="utf-8", newline=""
        )

        cls.paths = sorted(FIXTURES.glob("*.txt")) + [cp1252, combined]
        cls.paths += sorted(ACCESSIBILITY_LOGS.glob("*.txt"))
        cls.node_results = run_node(cls.paths)
        cls.py = make_colorizer()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_input_matches(self):
        self.assertGreaterEqual(len(self.paths), 7)
        for path in self.paths:
            with self.subTest(file=path.name):
                text = read_text_file(path)
                py_pre = self.py.preprocess_text(text)
                py_client = self.py.detected_client
                py_html = self.py.colorize_text(text)
                js = self.node_results[str(path)]
                self.assertEqual(py_client, js["client"], "detected client differs")
                self.assertEqual(py_pre, js["preprocessed"], first_difference(py_pre, js["preprocessed"]))
                self.assertEqual(py_html, js["html"], first_difference(py_html, js["html"]))

    def test_vipmud_fixtures_exercise_the_preprocess_layer(self):
        for name in ("vipmud_login.txt", "vipmud_status_dedupe.txt", "vipmud_pvp_combat.txt"):
            self.assertEqual(self.node_results[str(FIXTURES / name)]["client"], "vipmud")
        self.assertIsNone(self.node_results[str(FIXTURES / "mudlet_excerpt.txt")]["client"])


if __name__ == "__main__":
    unittest.main()
