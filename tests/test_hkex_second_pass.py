import unittest
import sys
import types
from datetime import datetime

sys.modules.setdefault("requests", types.SimpleNamespace(RequestException=Exception))
sys.modules.setdefault("pypdf", types.SimpleNamespace(PdfReader=object))

from scripts.hkex_second_pass import (
    SearchResult,
    build_supplement_candidates,
    detect_zero_borrowing_candidates,
    score_result,
    should_skip_metric_hit,
)


class HkexSecondPassTests(unittest.TestCase):
    def test_skips_trade_payables_for_short_term_borrowings(self):
        snippet = (
            "Trade payable balances are repayable within one year. "
            "The amounts due to the immediate holding company and other related parties are unsecured."
        )
        self.assertTrue(should_skip_metric_hit("短期借款", "repayable within one year", snippet))

    def test_skips_negated_interest_bearing_borrowings(self):
        snippet = (
            "Interest-bearing bank and other borrowings As of June 30, 2025, "
            "the Group did not have any interest-bearing bank and other borrowings "
            "(as of December 31, 2024: Nil)."
        )
        self.assertTrue(should_skip_metric_hit("长期借款", "bank and other borrowings", snippet))

    def test_skips_no_outstanding_borrowings_with_lease_liabilities(self):
        snippet = (
            "The Group did not have any short-term or long-term bank borrowings and had no outstanding "
            "bank and other borrowings and other indebtedness apart from lease liabilities "
            "for the relevant lease terms amounting to approximately RMB15.0 million in aggregate."
        )
        self.assertTrue(should_skip_metric_hit("长期借款", "bank and other borrowings", snippet))

    def test_keeps_real_short_term_borrowings(self):
        snippet = "Bank borrowings repayable within one year amounted to RMB320.0 million."
        self.assertFalse(should_skip_metric_hit("短期借款", "repayable within one year", snippet))

    def test_clarification_announcement_scores_below_results_announcement(self):
        clarification = SearchResult(
            stock_code="00071",
            stock_name="MIRAMAR HOTEL",
            title="CLARIFICATION ANNOUNCEMENT IN RELATION TO 2025 INTERIM RESULTS ANNOUNCEMENT",
            short_text="",
            file_type="PDF",
            file_link="https://example.com/a.pdf",
            file_info="1KB",
            date_time=datetime(2025, 8, 28, 12, 0),
            news_id="1",
        )
        results_announcement = SearchResult(
            stock_code="00071",
            stock_name="MIRAMAR HOTEL",
            title="INTERIM RESULTS ANNOUNCEMENT FOR THE SIX MONTHS ENDED 30 JUNE 2025",
            short_text="",
            file_type="PDF",
            file_link="https://example.com/b.pdf",
            file_info="1KB",
            date_time=datetime(2025, 8, 27, 12, 0),
            news_id="2",
        )
        self.assertLess(score_result(clarification, "2025中报"), score_result(results_announcement, "2025中报"))

    def test_detects_high_confidence_zero_borrowings_for_both_metrics(self):
        text = (
            "As of June 30, 2025, the Group did not have any interest-bearing bank and other borrowings "
            "(as of December 31, 2024: Nil)."
        )
        zero_candidates = detect_zero_borrowing_candidates(text, ["短期借款", "长期借款"])
        self.assertEqual(zero_candidates["短期借款"]["value_native"], 0.0)
        self.assertEqual(zero_candidates["长期借款"]["value_native"], 0.0)
        self.assertEqual(zero_candidates["长期借款"]["status"], "zero_explicit")
        self.assertEqual(zero_candidates["长期借款"]["confidence"], "high")

    def test_build_supplement_candidates_uses_zero_when_no_amount_hit(self):
        target = {"core_missing": ["短期借款", "长期借款"]}
        doc = {
            "metric_amounts": {"短期借款": [], "长期借款": []},
            "zero_borrowing_candidates": {
                "短期借款": {
                    "status": "zero_explicit",
                    "confidence": "high",
                    "value_hkd": 0.0,
                    "value_native": 0.0,
                    "alias": "no borrowings",
                    "snippet": "The Group had no borrowings.",
                },
                "长期借款": {
                    "status": "zero_explicit",
                    "confidence": "high",
                    "value_hkd": 0.0,
                    "value_native": 0.0,
                    "alias": "no borrowings",
                    "snippet": "The Group had no borrowings.",
                },
            },
        }
        candidates = build_supplement_candidates(target, doc)
        self.assertEqual(candidates["短期借款"]["status"], "zero_explicit")
        self.assertEqual(candidates["长期借款"]["value_native"], 0.0)

    def test_build_supplement_candidates_prefers_real_amount_over_zero(self):
        target = {"core_missing": ["长期借款"]}
        doc = {
            "metric_amounts": {
                "长期借款": [
                    {
                        "alias": "long-term borrowings",
                        "snippet": "Long-term borrowings 320,000",
                        "raw_value": 320000.0,
                        "normalized_value": 320000.0,
                        "value_hkd": 320000.0,
                    }
                ]
            },
            "zero_borrowing_candidates": {
                "长期借款": {
                    "status": "zero_explicit",
                    "confidence": "high",
                    "value_hkd": 0.0,
                    "value_native": 0.0,
                    "alias": "no long-term borrowings",
                    "snippet": "no long-term borrowings",
                }
            },
        }
        candidates = build_supplement_candidates(target, doc)
        self.assertEqual(candidates["长期借款"]["status"], "direct")
        self.assertEqual(candidates["长期借款"]["value_native"], 320000.0)


if __name__ == "__main__":
    unittest.main()
