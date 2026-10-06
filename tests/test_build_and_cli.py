"""Compiled rules are up to date, JS/JSON agree, and the CLI works."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _common import FIXTURES, ROOT, visible_lines
import build_rules


class CompiledRulesTest(unittest.TestCase):
    def test_rules_json_is_up_to_date_with_build_rules(self):
        expected = json.loads(build_rules.render_rules_json(build_rules.build_rules_data()))
        actual = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected, "rules.json is stale: run `python build_rules.py`")

    def test_webapp_rules_js_matches_rules_json(self):
        js = (ROOT / "webapp" / "rules.js").read_text(encoding="utf-8")
        prefix = "window.COLORIZER_RULES = "
        payload = js.split(prefix, 1)[1].rstrip().rstrip(";")
        self.assertEqual(
            json.loads(payload),
            json.loads((ROOT / "rules.json").read_text(encoding="utf-8")),
            "webapp/rules.js is stale: run `python build_rules.py`",
        )

    def test_preprocess_section_is_compiled_for_both_engines(self):
        data = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
        kinds = {r["kind"] for r in data["preprocess"]["rules"]}
        self.assertTrue(kinds <= {"drop", "drop_block", "drop_after", "dedupe_on_change", "rewrite", "drop_closer", "drop_before", "drop_secret"})
        self.assertTrue({"drop", "drop_block", "drop_after", "dedupe_on_change", "drop_closer"} <= kinds)
        ids = [r["id"] for r in data["preprocess"]["rules"]]
        self.assertEqual(len(ids), len(set(ids)), "preprocess rule ids must be unique")

    def test_no_hardcoded_author_paths_in_python_sources(self):
        for path in ROOT.glob("*.py"):
            self.assertNotIn("Compu" + "mar", path.read_text(encoding="utf-8"), path.name)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "engine.py"), *args], capture_output=True, timeout=120)

    def test_cli_writes_html_and_reports_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.txt"
            out = Path(tmp) / "out.html"
            raw = (FIXTURES / "vipmud_status_dedupe.txt").read_text(encoding="utf-8").replace("\n", "\r\n")
            src.write_bytes(raw.encode("cp1252"))
            proc = self.run_cli(str(src), "-o", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("VIPMud", proc.stderr.decode("utf-8", "replace"))
            html_out = out.read_text(encoding="utf-8")
            self.assertIn("Estás siendo atacada por Fantasma.", visible_lines(html_out))
            self.assertNotIn("SL:", html_out)

    def test_cli_no_preprocess_keeps_status_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.txt"
            src.write_text("SL: [n]\nfoo\n", encoding="utf-8")
            proc = self.run_cli(str(src), "--no-preprocess")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(b">SL:</span>", proc.stdout)


if __name__ == "__main__":
    unittest.main()
