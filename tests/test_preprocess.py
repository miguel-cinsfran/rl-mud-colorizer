"""Unit tests for each preprocess rule kind and for client detection."""

import unittest

from _common import make_colorizer

CLIENTS = [
    {"id": "alpha", "label": "Alpha", "signatures": [r"^ALPHA:"]},
    {"id": "beta", "label": "Beta", "signatures": [r"^BETA:", r"^BETA2:"]},
]


def run(rules, text, client=None, clients=CLIENTS):
    c = make_colorizer(rules, clients)
    return c.preprocess_text(text, client).split("\n"), c


class DropTest(unittest.TestCase):
    def test_drop_removes_matching_lines_only(self):
        out, _ = run([{"id": "d", "kind": "drop", "pattern": r"^SL:"}], "a\nSL: [n]\nb")
        self.assertEqual(out, ["a", "b"])

    def test_drop_is_anchored_by_pattern(self):
        out, _ = run([{"id": "d", "kind": "drop", "pattern": r"^SL:"}], "xSL: [n]")
        self.assertEqual(out, ["xSL: [n]"])


class DropBlockTest(unittest.TestCase):
    RULE = {"id": "b", "kind": "drop_block", "start": r"^START", "end": r"^END", "include_end": True}

    def test_drops_region_including_end(self):
        out, _ = run([self.RULE], "a\nSTART\nx\ny\nEND\nb")
        self.assertEqual(out, ["a", "b"])

    def test_keeps_end_line_when_include_end_false(self):
        rule = dict(self.RULE, include_end=False)
        out, _ = run([rule], "a\nSTART\nx\nEND\nb")
        self.assertEqual(out, ["a", "END", "b"])

    def test_unterminated_block_is_kept(self):
        out, _ = run([self.RULE], "a\nSTART\nx\ny")
        self.assertEqual(out, ["a", "START", "x", "y"])

    def test_max_lines_limits_search_for_end(self):
        rule = dict(self.RULE, max_lines=2)
        out, _ = run([rule], "START\nx\ny\nEND\nz")
        self.assertEqual(out, ["START", "x", "y", "END", "z"])
        out, _ = run([rule], "START\nx\nEND\nz")
        self.assertEqual(out, ["z"])

    def test_two_blocks_in_one_input(self):
        out, _ = run([self.RULE], "START\nEND\nmid\nSTART\nq\nEND\ntail")
        self.assertEqual(out, ["mid", "tail"])


class DropAfterTest(unittest.TestCase):
    RULE = {"id": "a", "kind": "drop_after", "pattern": r"^PROMPT:", "until": r"^SERVER", "max_lines": 4}

    def test_drops_prompt_and_echoed_lines_until_server_line(self):
        out, _ = run([self.RULE], "x\nPROMPT: \nfakeuser\nfakepass123\nSERVER says hi\ny")
        self.assertEqual(out, ["x", "SERVER says hi", "y"])

    def test_include_until_drops_the_terminator_too(self):
        rule = dict(self.RULE, include_until=True)
        out, _ = run([rule], "PROMPT: \nfoo\nSERVER says hi\ny")
        self.assertEqual(out, ["y"])

    def test_max_lines_bounds_the_damage_when_until_never_appears(self):
        out, _ = run([self.RULE], "PROMPT: \n1\n2\n3\n4\n5\n6")
        self.assertEqual(out, ["5", "6"])

    def test_fragment_ending_right_after_prompt(self):
        out, _ = run([self.RULE], "ok\nPROMPT: \nfakeuser")
        self.assertEqual(out, ["ok"])


class DedupeTest(unittest.TestCase):
    def test_default_key_is_whole_line(self):
        rule = {"id": "p", "kind": "dedupe_on_change", "pattern": r"^Pv:"}
        out, _ = run([rule], "Pv:1\nPv:1\nPv:2\nPv:2\nPv:1")
        self.assertEqual(out, ["Pv:1", "Pv:2", "Pv:1"])

    def test_key_group(self):
        rule = {"id": "i", "kind": "dedupe_on_change", "pattern": r"^Img:(\d+) .*$", "key_group": 1}
        out, _ = run([rule], "Img:5 a\nImg:5 b\nImg:6 c")
        self.assertEqual(out, ["Img:5 a", "Img:6 c"])

    def test_key_template(self):
        rule = {"id": "k", "kind": "dedupe_on_change", "pattern": r"^(\w+) (\w+) (\w+)$", "key": "$1|$3"}
        out, _ = run([rule], "a x b\na y b\na y c")
        self.assertEqual(out, ["a x b", "a y c"])

    def test_scopes_are_independent(self):
        rules = [
            {"id": "a", "kind": "dedupe_on_change", "pattern": r"^A:(\d+)", "key_group": 1, "scope_id": "a"},
            {"id": "b", "kind": "dedupe_on_change", "pattern": r"^B:(\d+)", "key_group": 1, "scope_id": "b"},
        ]
        out, _ = run(rules, "A:1\nB:1\nA:1\nB:1\nB:2")
        self.assertEqual(out, ["A:1", "B:1", "B:2"])

    def test_shared_scope_between_rules(self):
        rules = [
            {"id": "a", "kind": "dedupe_on_change", "pattern": r"^A:(\d+)", "key_group": 1, "scope_id": "s"},
            {"id": "b", "kind": "dedupe_on_change", "pattern": r"^B:(\d+)", "key_group": 1, "scope_id": "s"},
        ]
        out, _ = run(rules, "A:1\nB:1\nB:2")
        self.assertEqual(out, ["A:1", "B:2"])

    def test_trailing_blanks_are_ignored_in_key(self):
        rule = {"id": "p", "kind": "dedupe_on_change", "pattern": r"^Pv:"}
        out, _ = run([rule], "Pv:1\nPv:1   \nPv:1\t")
        self.assertEqual(out, ["Pv:1"])

    def test_state_starts_empty_for_every_input(self):
        rule = {"id": "p", "kind": "dedupe_on_change", "pattern": r"^Pv:"}
        c = make_colorizer([rule], CLIENTS)
        self.assertEqual(c.preprocess_text("Pv:1\nPv:1"), "Pv:1")
        self.assertEqual(c.preprocess_text("Pv:1\nPv:1"), "Pv:1")


class RewriteTest(unittest.TestCase):
    def test_rewrite_with_groups(self):
        rule = {"id": "r", "kind": "rewrite", "pattern": r"^(\w+)=(\w+)$", "replace": "$2 <- $1"}
        out, _ = run([rule], "a=b\nunchanged")
        self.assertEqual(out, ["b <- a", "unchanged"])

    def test_missing_group_expands_to_empty(self):
        rule = {"id": "r", "kind": "rewrite", "pattern": r"^(x)(y)?$", "replace": "[$1|$2|$3]"}
        out, _ = run([rule], "x")
        self.assertEqual(out, ["[x||]"])

    def test_later_rules_see_the_rewritten_line(self):
        rules = [
            {"id": "r", "kind": "rewrite", "pattern": r"^old$", "replace": "new"},
            {"id": "d", "kind": "drop", "pattern": r"^new$"},
        ]
        out, _ = run(rules, "old\nkeep")
        self.assertEqual(out, ["keep"])


class DropCloserTest(unittest.TestCase):
    RULES = [
        {"id": "pv", "kind": "dedupe_on_change", "group": "g", "pattern": r"^Pv:"},
        {"id": "sl", "kind": "drop", "group": "g", "pattern": r"^SL:"},
        {"id": "closer", "kind": "drop_closer", "group": "g", "pattern": r"^[>\]][ \t]*$"},
    ]

    def test_closer_dropped_when_block_kept_nothing(self):
        out, _ = run(self.RULES, "Pv:1\nSL:a\n> \nfoo\nPv:1\nSL:b\n> \nbar")
        self.assertEqual(out, ["Pv:1", "> ", "foo", "bar"])

    def test_closer_kept_when_block_kept_a_line(self):
        out, _ = run(self.RULES, "Pv:1\nSL:a\n] \nfoo")
        self.assertEqual(out, ["Pv:1", "] ", "foo"])

    def test_lone_prompt_outside_a_block_is_kept(self):
        out, _ = run(self.RULES, "foo\n> \nbar")
        self.assertEqual(out, ["foo", "> ", "bar"])

    def test_prompt_after_unrelated_line_is_kept(self):
        out, _ = run(self.RULES, "Pv:1\nSL:a\n> \nfoo\n> ")
        self.assertEqual(out, ["Pv:1", "> ", "foo", "> "])

    def test_fragment_starting_mid_block(self):
        out, _ = run(self.RULES, "SL:a\n> \nfoo")
        self.assertEqual(out, ["foo"])


class BlankLineTest(unittest.TestCase):
    def test_stacked_blank_lines_left_by_drops_are_collapsed(self):
        rules = [{"id": "d", "kind": "drop", "pattern": r"^X"}]
        out, _ = run(rules, "\n\na\n\nX\n\nb\n")
        self.assertEqual(out, ["a", "", "b", ""])

    def test_input_without_any_change_is_untouched(self):
        rules = [{"id": "d", "kind": "drop", "pattern": r"^X"}]
        out, _ = run(rules, "\n\na\n\n\nb")
        self.assertEqual(out, ["", "", "a", "", "", "b"])


class SqueezeBlankTest(unittest.TestCase):
    RULES = [{"id": "sq", "kind": "squeeze_blank", "keep_before": r"^(?:[>\]]|Pv:\d|.*[ \t]\[[a-z,]+\][ \t]*$)"}]

    def test_blank_lines_between_messages_are_dropped(self):
        out, _ = run(self.RULES, "a\n\nb\n\n\nc")
        self.assertEqual(out, ["a", "b", "c"])

    def test_one_blank_kept_before_prompt_status_and_exits_lines(self):
        text = "a\n\n> go\nb\n\nPv:1\\2 Pe:1\\2\nc\n\n\nPlaza [n,s] \nd"
        out, _ = run(self.RULES, text)
        self.assertEqual(out, ["a", "", "> go", "b", "", "Pv:1\\2 Pe:1\\2", "c", "", "Plaza [n,s] ", "d"])

    def test_no_blank_is_invented(self):
        out, _ = run(self.RULES, "a\n> go")
        self.assertEqual(out, ["a", "> go"])

    def test_leading_and_trailing_blanks_are_dropped(self):
        out, _ = run(self.RULES, "\n\n> a\nb\n\n")
        self.assertEqual(out, ["> a", "b"])

    def test_only_runs_for_its_client(self):
        rules = [dict(self.RULES[0], clients=["alpha"])]
        out, _ = run(rules, "a\n\nb", client="beta")
        self.assertEqual(out, ["a", "", "b"])
        out, _ = run(rules, "a\n\nb", client="alpha")
        self.assertEqual(out, ["a", "b"])

    def test_real_rules_hide_imagenes_zero_and_status_pv(self):
        c = make_colorizer()
        text = "Pv:10\\10 Pe:1\\1 Xp:5\nJgd:\nImágenes:0\nPieles:2\n> \nHola.\nImágenes:3\n> \nAdios."
        out = c.preprocess_text(text, "vipmud").split("\n")
        self.assertNotIn("Imágenes:0", out)
        self.assertIn("Imágenes:3", out)
        self.assertFalse([l for l in out if l.startswith("Pv:")])

    def test_real_rules_status_counters_only_when_nonzero_and_changed(self):
        c = make_colorizer()
        block = "Jgd:\nPieles:{p}\nAstucia:{a}\nInercia:{i}\n> \nHola."
        text = "\n".join(block.format(p=p, a=a, i=i) for p, a, i in ((0, 3, 0), (0, 3, 2), (4, 0, 2)))
        out = c.preprocess_text(text, "vipmud").split("\n")
        for zero in ("Pieles:0", "Astucia:0", "Inercia:0"):
            self.assertNotIn(zero, out)
        self.assertEqual([l for l in out if l.startswith("Astucia:")], ["Astucia:3"])
        self.assertEqual([l for l in out if l.startswith("Inercia:")], ["Inercia:2"])
        self.assertEqual([l for l in out if l.startswith("Pieles:")], ["Pieles:4"])

    def test_real_rules_squeeze_vipmud_but_mudlet_keeps_blanks(self):
        c = make_colorizer()
        text = "Pv:10\\10 Pe:1\\1 Xp:5\nSL: [n]\nPL:\nJgd:\nImágenes:0\nPieles:0\n> \nHola.\n\nAdios.\n\n> x"
        # Every blank line goes, and the block kept nothing, so its "> " closer goes too.
        self.assertEqual(c.preprocess_text(text, "vipmud").split("\n"), ["Hola.", "Adios.", "> x"])
        self.assertIn("", c.preprocess_text("Hola.\n\nAdios.", "mudlet").split("\n"))


class ClientScopingTest(unittest.TestCase):
    RULES = [
        {"id": "agnostic", "kind": "drop", "pattern": r"^AG"},
        {"id": "only_alpha", "kind": "drop", "pattern": r"^AL ", "clients": ["alpha"]},
    ]

    def test_client_specific_rule_runs_only_for_its_client(self):
        out, c = run(self.RULES, "ALPHA: hi\nAL x\nAG y\nz")
        self.assertEqual(c.detected_client, "alpha")
        self.assertEqual(out, ["ALPHA: hi", "z"])

    def test_without_detected_client_only_agnostic_rules_apply(self):
        out, c = run(self.RULES, "AL x\nAG y\nz")
        self.assertIsNone(c.detected_client)
        self.assertEqual(out, ["AL x", "z"])

    def test_forced_client_overrides_detection(self):
        out, c = run(self.RULES, "AL x\nz", client="alpha")
        self.assertEqual(c.detected_client, "alpha")
        self.assertEqual(out, ["z"])


class ClientDetectionTest(unittest.TestCase):
    def test_most_matching_lines_wins(self):
        c = make_colorizer([], CLIENTS)
        self.assertEqual(c.detect_client("ALPHA: 1\nBETA: 1\nBETA2: 2\nx"), "beta")

    def test_tie_goes_to_first_declared_client(self):
        c = make_colorizer([], CLIENTS)
        self.assertEqual(c.detect_client("ALPHA: 1\nBETA: 1"), "alpha")

    def test_no_signature_means_none(self):
        c = make_colorizer([], CLIENTS)
        self.assertIsNone(c.detect_client("nothing special\nhere"))

    def test_real_rules_detect_vipmud_signatures(self):
        c = make_colorizer()
        for sample in (
            "Pv:2611\\2611 Pe:625\\688 Xp:1231367",
            "Jgd:Koch (Org)",
            "LPmud version: fluffos 063a160d RLII.",
        ):
            self.assertEqual(c.detect_client(sample), "vipmud", sample)

    def test_shared_prompt_lines_alone_do_not_select_vipmud(self):
        # "SL:", "Pieles:" and "Imágenes:" also appear in Mudlet logs with custom prompts
        c = make_colorizer()
        block = "SL: [so,e]" + chr(10) + "PL:" + chr(10) + "Imágenes:0" + chr(10) + "Pieles:0" + chr(10) + "> "
        self.assertIsNone(c.detect_client(block))
        self.assertEqual(c.preprocess_text(block), block)

    def test_real_rules_detect_mudlet_prompt(self):
        c = make_colorizer()
        self.assertEqual(c.detect_client("Pvs: 3200 Pe: 450\nfoo"), "mudlet")
        self.assertEqual(c.detect_client("Pvs: 2611/2611 (-120) Pe: 600/688 (0)"), None)


if __name__ == "__main__":
    unittest.main()
