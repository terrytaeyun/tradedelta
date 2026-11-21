import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tradedelta import ROOT, compare, load_csv, render_html


class ContributionTests(unittest.TestCase):
    def test_demo_reconciles_to_published_totals(self):
        report = compare(load_csv(ROOT / "examples" / "korea_cosmetics.csv"), "2024", "2025")
        self.assertEqual((report.base_usd, report.target_usd), (10_177_312_000, 11_417_570_000))
        self.assertEqual(sum(row.change_usd for row in report.rows), 1_240_258_000)
        self.assertEqual(report.rows[-1].group, ("China",))
        self.assertEqual(report.rows[-1].change_usd, -473_762_000)
        self.assertAlmostEqual(sum(row.contribution_pp for row in report.rows), report.growth_pct)

    def test_every_grouping_reconciles_with_zero_net_change(self):
        values = {
            ("2024-10", "US", "090121"): 100,
            ("2024-10", "JP", "020200"): 100,
            ("2025-10", "US", "090121"): 150,
            ("2025-10", "JP", "020200"): 50,
        }
        for grouping in ("partner", "product", "pair"):
            with self.subTest(grouping=grouping):
                report = compare(values, "2024-10", "2025-10", grouping)
                self.assertEqual([row.contribution_pp for row in report.rows], [25, -25])
                self.assertEqual(report.growth_pct, 0)

    def test_missing_pair_requires_explicit_choice(self):
        values = {("2024", "US", "090121"): 100, ("2025", "JP", "090121"): 120}
        with self.assertRaisesRegex(ValueError, "2 partner/product pairs"):
            compare(values, "2024", "2025")
        report = compare(values, "2024", "2025", missing_as_zero=True)
        self.assertEqual(report.assumed_zero_pairs, 2)
        self.assertEqual(sum(row.change_usd for row in report.rows), 20)

    def test_zero_base_preserves_dollar_change_and_escapes_labels(self):
        values = {("2024", "<example>", "090121"): 0, ("2025", "<example>", "090121"): 120}
        report = compare(values, "2024", "2025")
        self.assertEqual(report.change_usd, 120)
        self.assertIsNone(report.growth_pct)
        self.assertIsNone(report.rows[0].contribution_pp)
        html = render_html(report, False)
        self.assertIn("&lt;example&gt;", html)
        self.assertNotIn("<example>", html)

    def test_csv_checks_duplicate_and_aggregate_keys(self):
        cases = [
            ("2024,US,090121,100\n2024,US,090121,100", "duplicate record"),
            ("2024,World,090121,100", "remove aggregate"),
            ("2024-13,US,090121,100", "period must be"),
            ("2024,US,090121,\n", "nonnegative whole USD"),
            ("2024,US,090121,100\n2025-02,US,090121,200", "one frequency"),
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            for body, message in cases:
                with self.subTest(message=message):
                    path.write_text("period,partner,product,value_usd\n" + body + "\n", encoding="utf-8-sig")
                    with self.assertRaisesRegex(ValueError, message):
                        load_csv(path)
            path.write_text("period,partner,product,value_usd\n2024,US,090121,100\n", encoding="utf-8-sig")
            self.assertEqual(load_csv(path), {("2024", "US", "090121"): 100})


if __name__ == "__main__":
    unittest.main()
