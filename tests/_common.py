"""Shared helpers for the test suite (stdlib unittest only)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ACCESSIBILITY_LOGS = ROOT / "accessibility_logs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import RLColorizer, read_text_file  # noqa: E402


def make_colorizer(preprocess_rules=None, clients=None):
    """Colorizer built from the real rules.json, optionally overriding the preprocess section."""
    import json

    with open(ROOT / "rules.json", encoding="utf-8") as f:
        config = json.load(f)
    if preprocess_rules is not None:
        config["preprocess"] = {"clients": clients or [], "rules": preprocess_rules}
    return RLColorizer(config=config)


def fixture_text(name):
    return read_text_file(FIXTURES / name)


def visible_lines(html_output):
    """Plain visible text of each rendered output line (tags stripped, entities decoded)."""
    import html

    body = html_output.split("<body><div>", 1)[1].rsplit("</div></body>", 1)[0]
    lines = []
    for chunk in body.split("<br>"):
        text = re.sub(r"<[^>]+>", "", chunk).strip("\n")
        lines.append(html.unescape(text))
    if lines and lines[-1].strip() == "":
        lines.pop()
    return lines
