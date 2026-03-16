import unittest
import sys
import types
from datetime import datetime

sys.modules.setdefault("requests", types.SimpleNamespace(RequestException=Exception))
sys.modules.setdefault("pypdf", types.SimpleNamespace(PdfReader=object))

from scripts.hkex_second_pass import (
    SearchResult,
    build_supplement_candidates,
    build_supplement_candidates_for_docs,
    choose_line_numeric_values,
    find_metric_amounts_by_lines,
    find_metric_amounts,
    detect_zero_borrowing_candidates,
    score_result,
    snippet_multiplier,
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

    def test_build_supplement_candidates_for_docs_uses_later_doc_hit(self):
        target = {"core_missing": ["长期借款"]}
        docs = [
            {
                "metric_amounts": {"长期借款": []},
                "zero_borrowing_candidates": {},
            },
            {
                "metric_amounts": {
                    "长期借款": [
                        {
                            "alias": "long-term borrowings",
                            "snippet": "Long-term borrowings 640,000",
                            "raw_value": 640000.0,
                            "normalized_value": 640000.0,
                            "value_hkd": 640000.0,
                        }
                    ]
                },
                "zero_borrowing_candidates": {},
            },
        ]
        candidates = build_supplement_candidates_for_docs(target, docs)
        self.assertEqual(candidates["长期借款"]["status"], "direct")
        self.assertEqual(candidates["长期借款"]["value_native"], 640000.0)

    def test_build_supplement_candidates_for_docs_prefers_direct_over_zero(self):
        target = {"core_missing": ["长期借款"]}
        docs = [
            {
                "metric_amounts": {"长期借款": []},
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
            },
            {
                "metric_amounts": {
                    "长期借款": [
                        {
                            "alias": "long-term borrowings",
                            "snippet": "Long-term borrowings 128,000",
                            "raw_value": 128000.0,
                            "normalized_value": 128000.0,
                            "value_hkd": 128000.0,
                        }
                    ]
                },
                "zero_borrowing_candidates": {},
            },
        ]
        candidates = build_supplement_candidates_for_docs(target, docs)
        self.assertEqual(candidates["长期借款"]["status"], "direct")
        self.assertEqual(candidates["长期借款"]["value_native"], 128000.0)

    def test_choose_line_numeric_values_skips_note_reference_column(self):
        self.assertEqual(choose_line_numeric_values("Borrowings 13 205,082"), [205082.0])

    def test_choose_line_numeric_values_ignores_note_reference_with_placeholders(self):
        self.assertEqual(choose_line_numeric_values("Borrowings 13 - -"), [])

    def test_choose_line_numeric_values_ignores_comparative_amount_after_placeholder(self):
        self.assertEqual(choose_line_numeric_values("Borrowings 13 - 205,082"), [])

    def test_find_metric_amounts_by_lines_aggregates_capex_components_after_heading(self):
        lines = [
            "30 June 31 December",
            "2025 2024",
            "RMB'000 RMB'000",
            "Capital expenditure contracted for but not provided in",
            "the consolidated financial statements",
            "- acquisition of property, plant and equipment 5,237 17,058",
            "- construction of property, plant and equipment 375,783 438,150",
            "381,020 455,208",
        ]
        amounts = find_metric_amounts_by_lines(lines, ["资本性支出"], 1, 1.0)
        self.assertEqual(amounts["资本性支出"][0]["raw_value"], 381020.0)

    def test_find_metric_amounts_by_lines_extracts_property_development_commitment(self):
        lines = [
            "At the end of the reporting period, the Group had commitments in relation to expenditure on properties",
            "under development of HK$2,531,687,000 (31st December, 2024: HK$2,123,477,000), which were contracted",
            "but not provided for.",
        ]
        amounts = find_metric_amounts_by_lines(lines, ["资本性支出"], 1, 1.0)
        self.assertEqual(amounts["资本性支出"][0]["raw_value"], 2531687000.0)

    def test_snippet_multiplier_ignores_document_unit_when_snippet_has_explicit_currency_amount(self):
        self.assertEqual(snippet_multiplier("HK$2,531,687,000", 1000), 1)

    def test_find_metric_amounts_respects_explicit_currency_amount_over_doc_unit(self):
        text = "The Group had commitments in relation to expenditure on properties under development of HK$2,531,687,000."
        amounts = find_metric_amounts(text, ["资本性支出"], 1000, 1.0)
        self.assertEqual(amounts["资本性支出"][0]["normalized_value"], 2531687000.0)

    def test_find_metric_amounts_prefers_numbers_after_alias(self):
        text = (
            "89,615 90,000 Non-current liabilities "
            "Bank loans and other interest-bearing borrowings 15 - (2,505) "
            "Derivative financial instruments"
        )
        amounts = find_metric_amounts(text, ["长期借款"], 1, 1.0)
        self.assertEqual(amounts["长期借款"], [])

    def test_find_metric_amounts_by_lines_ignores_note_and_date_columns_before_alias_value(self):
        lines = [
            "15. Bank loans and other interest-bearing borrowings",
            "30 June 31 December 2025 2024 $ million $ million",
            "Bank loan and others 3,768 2,505",
            "Current portion (3,768) -",
            "Non-current portion - 2,505",
        ]
        amounts = find_metric_amounts_by_lines(lines, ["长期借款"], 1, 1.0)
        self.assertEqual(amounts["长期借款"], [])

    def test_find_metric_amounts_ignores_date_header_after_borrowings_alias(self):
        text = (
            "15. Bank loans and other interest-bearing borrowings "
            "30 June 31 December 2025 2024 $ million $ million "
            "Bank loan and others 3,768 2,505 Current portion (3,768) - "
            "Non-current portion - 2,505"
        )
        amounts = find_metric_amounts(text, ["长期借款"], 1, 1.0)
        self.assertEqual(amounts["长期借款"], [])


if __name__ == "__main__":
    unittest.main()
