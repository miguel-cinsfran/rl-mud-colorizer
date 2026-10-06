"""Mutation review of the login sanitizer.

Each login-related preprocess rule is removed in turn (a "mutant"). The leak
checks below must notice the removal on at least one fixture; a mutant that
survives means that rule is not protected by any test.
"""

import json
import unittest

from _common import ROOT, fixture_text, make_colorizer

LOGIN_FIXTURES = (
    "vipmud_login.txt",
    "vipmud_login_case_a.txt",
    "vipmud_login_case_a_head.txt",
    "vipmud_login_case_b.txt",
    "vipmud_login_case_c.txt",
    "vipmud_login_case_d.txt",  # type-ahead right before the name prompt, no banner
    "vipmud_login_case_e.txt",  # last-connection IP line without the MOTD around it
    "vipmud_login_case_f.txt",  # password retyped after the "copia existente" question
)
# Anything here in the output means credentials or login noise leaked.
LEAK_MARKERS = (
    "fakeuser",
    "fakepass123",
    "192.0.2.1",
    "Introduce",
    "LPmud",
    "recuperar clave",
    "Los Dioses",
)


def preprocess_rules():
    with open(ROOT / "rules.json", encoding="utf-8") as f:
        section = json.load(f)["preprocess"]
    return section["rules"], section["clients"]


def leaks(rules, clients):
    c = make_colorizer(rules, clients)
    found = []
    for name in LOGIN_FIXTURES:
        out = c.preprocess_text(fixture_text(name))
        found += [(name, m) for m in LEAK_MARKERS if m in out]
    return found


class LoginMutationTest(unittest.TestCase):
    def test_original_rules_leak_nothing(self):
        rules, clients = preprocess_rules()
        self.assertEqual(leaks(rules, clients), [])

    def test_every_login_rule_is_load_bearing(self):
        rules, clients = preprocess_rules()
        login_ids = [r["id"] for r in rules if r["id"].startswith("login_")]
        self.assertTrue(login_ids)
        survivors = []
        for rule_id in login_ids:
            mutant = [r for r in rules if r["id"] != rule_id]
            if not leaks(mutant, clients):
                survivors.append(rule_id)
        self.assertEqual(survivors, [], "removing these rules leaks nothing in any fixture")


if __name__ == "__main__":
    unittest.main()
