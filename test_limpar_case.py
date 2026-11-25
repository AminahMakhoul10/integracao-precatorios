import unittest
from datetime import date
from decimal import Decimal
from limpar_case import parse_money, parse_date, process_key

class CleaningRulesTest(unittest.TestCase):
    def test_brazilian_money(self):
        self.assertEqual(parse_money("2.500,50"), Decimal("2500.50"))

    def test_iso_and_timestamp_dates(self):
        self.assertEqual(parse_date("2025-04-02"), date(2025, 4, 2))
        self.assertEqual(parse_date("2025-04-03T01:00:00Z"), date(2025, 4, 3))

    def test_process_key_joins_masked_and_unmasked(self):
        self.assertEqual(process_key("0023456-21.2020.8.26.0053"), "00234562120208260053")
        self.assertEqual(process_key("00234562120208260053"), "00234562120208260053")
        self.assertIsNone(process_key(""))

    def test_bad_money_is_not_guessed(self):
        with self.assertRaises(ValueError):
            parse_money("2,500.50")

if __name__ == "__main__":
    unittest.main()
