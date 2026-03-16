import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from scripts import audit_missing_financials
from scripts.audit_missing_financials import build_gap_strategy, build_record, build_second_pass_queue


class AuditMissingFinancialsTests(unittest.TestCase):
    def make_base_row(self, code: str, name: str) -> dict:
        return {
            "股票代码": code,
            "股票简称": name,
            "港股@所属恒生行业(二级)": "工业工程",
            "港股@归属于母公司所有者的净利润[20250630]": 100.0,
            "港股@归属母公司股东的净利润(同比增长率)[20250630]": 10.0,
            "港股@总现金[20250630]": 1000.0,
            "港股@流动资产合计[20250630]": 1200.0,
            "港股@负债合计[20250630]": 500.0,
            "港股@短期借款[20250630]": 100.0,
            "港股@长期借款[20250630]": 200.0,
            "港股@权益合计[20250630]": 700.0,
            "港股@净资产收益率roe[20250630]": 8.0,
            "港股@投入资本回报率[20250630]": 9.0,
            "港股@经营活动产生的现金流量净额[20250630]": 100.0,
            "港股@投资活动产生的现金流量净额[20250630]": -50.0,
            "港股@资本性支出[20250630]": -30.0,
            "港股@融资活动产生的现金流量净额[20250630]": 20.0,
            "港股@股份回购[20250630]": 0.0,
            "港股@支付股息[20250630]": 0.0,
            "港股@年度分红总额[20250630]": 0.0,
        }

    def test_build_record_groups_missing_metrics(self):
        row = self.make_base_row("9999.HK", "测试公司")
        row["港股@总现金[20250630]"] = ""
        row["港股@短期借款[20250630]"] = ""
        row["港股@长期借款[20250630]"] = ""
        row["港股@资本性支出[20250630]"] = ""
        record = build_record(row, "2025中报")
        self.assertEqual(record["missing_metric_groups"]["debt"], ["短期借款", "长期借款"])
        self.assertEqual(record["missing_metric_groups"]["cash"], ["总现金"])
        self.assertEqual(record["missing_metric_groups"]["capex"], ["资本性支出"])

    def test_build_gap_strategy_marks_debt_zero_fill_as_allowed(self):
        record = {
            "queue_type": "only_short_and_long_debt",
            "core_missing": ["短期借款", "长期借款"],
        }
        strategy = build_gap_strategy(record)
        self.assertEqual(strategy["strategy"], "direct_extract_or_zero")
        self.assertEqual(strategy["recoverability"], "medium")
        self.assertEqual(strategy["zero_fill_metrics"], ["短期借款", "长期借款"])

    def test_build_second_pass_queue_sorts_by_audit_priority(self):
        rows = [
            self.make_base_row("1001.HK", "甲"),
            self.make_base_row("1002.HK", "乙"),
        ]
        rows[0]["港股@总现金[20250630]"] = ""
        rows[1]["港股@短期借款[20250630]"] = ""
        rows[1]["港股@长期借款[20250630]"] = ""
        queue = build_second_pass_queue(rows)
        self.assertEqual(queue[0]["queue_type"], "only_cash")
        self.assertEqual(queue[0]["gap_strategy"]["audit_priority"], 1)
        self.assertEqual(queue[1]["queue_type"], "only_short_and_long_debt")

    def test_main_creates_parent_directory_for_write_json(self):
        row = self.make_base_row("1001.HK", "甲")
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "missing_financial_audit.json"
            with mock.patch.object(audit_missing_financials, "load_rows", return_value=[row]):
                with mock.patch("sys.argv", ["audit_missing_financials.py", "--write-json", str(output_path)]):
                    exit_code = audit_missing_financials.main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
