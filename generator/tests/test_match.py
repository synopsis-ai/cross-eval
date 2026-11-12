import unittest

from cross_eval.match import match

MONEY = {"type": "money", "value": 1234567.0, "tolerance": 0.01, "min_sig_figs": 2}


class MatchTest(unittest.TestCase):
    def test_money_rounded_to_reply_precision(self):
        self.assertTrue(match(MONEY, {"values": [1_200_000], "sig_figs": 2})["correct"])
        self.assertTrue(match(MONEY, {"values": [1_234_000], "sig_figs": 4})["correct"])
        self.assertFalse(match({**MONEY, "value": 1_450_000.0}, {"values": [1_000_000], "sig_figs": 1})["correct"])

    def test_money_within_tolerance(self):
        self.assertTrue(match(MONEY, {"values": [1_240_000.0], "sig_figs": 6})["correct"])
        self.assertFalse(match(MONEY, {"values": [1_300_000.0], "sig_figs": 6})["correct"])

    def test_counts_are_exact(self):
        a = {"type": "count", "value": 41}
        self.assertTrue(match(a, {"values": [41]})["correct"])
        self.assertFalse(match(a, {"values": [40]})["correct"])

    def test_entity_aliases_and_suffixes(self):
        a = {"type": "entity", "value": "Northbeam Analytics", "aliases": ["NORTHBEAM ANALYTICS INC"]}
        self.assertTrue(match(a, {"values": ["Northbeam Analytics, Inc."]})["correct"])
        self.assertTrue(match(a, {"values": ["northbeam analytics llc"]})["correct"])
        self.assertFalse(match(a, {"values": ["Northgate Analytics"]})["correct"])

    def test_accepted_reading(self):
        a = {**MONEY, "accepted": [{"value": 1_500_000.0, "reading": "includes cancelled shows"}]}
        res = match(a, {"values": [1_500_000.0], "sig_figs": 7})
        self.assertTrue(res["correct"])
        self.assertEqual(res["reading"], "includes cancelled shows")

    def test_conflicting_values_are_wrong(self):
        self.assertFalse(match(MONEY, {"values": [1_234_567.0, 1_400_000.0], "sig_figs": 7})["correct"])

    def test_clarifying_question(self):
        res = match(MONEY, {"values": [], "clarifying": True})
        self.assertFalse(res["correct"])
        self.assertTrue(res["clarifying"])

    def test_ranked_list_order(self):
        a = {"type": "ranked_list", "value": ["A Co", "B Co"], "aliases": {}}
        self.assertTrue(match(a, {"values": ["A Co", "B Co"]})["correct"])
        self.assertFalse(match(a, {"values": ["B Co", "A Co"]})["correct"])


if __name__ == "__main__":
    unittest.main()
