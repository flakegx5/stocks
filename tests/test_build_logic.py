import unittest

from stocks_build.metrics import compute_phase1
from stocks_build.ranking import compute_rankings


MARKET_KEYS = {
    "price": "港股@最新价",
    "chg": "港股@最新涨跌幅",
    "mktcap": "港股@总市值[20260309]",
    "pe": "港股@市盈率(pe,ttm)[20260306]",
    "pb": "港股@市净率(pb)[20260309]",
    "shares": "港股@总股本[20260309]",
}


class BuildLogicTests(unittest.TestCase):
    def test_non_financial_with_missing_quality_inputs_stays_unranked(self):
        row = {
            "股票代码": "9999.HK",
            "股票简称": "测试公司",
            "港股@所属恒生行业(二级)": "原材料",
            "港股@总市值[20260309]": 1000000000,
            "港股@归属于母公司所有者的净利润[20251231]": 100000000,
            "港股@归属于母公司所有者的净利润[20241231]": 50000000,
            "港股@经营活动产生的现金流量净额[20251231]": 200000000,
            "港股@投资活动产生的现金流量净额[20251231]": -50000000,
            "港股@资本性支出[20251231]": -30000000,
            "港股@权益合计[20251231]": 600000000,
            "港股@年度分红总额[20251231]": 10000000,
        }
        phase1 = compute_phase1(row, MARKET_KEYS)
        rankings = compute_rankings([phase1])[0]
        self.assertEqual(phase1["vals"][10], "--")
        self.assertEqual(rankings[2], "--")
        self.assertEqual(rankings[5], "--")

    def test_non_financial_with_complete_fields_gets_ranked(self):
        base = {
            "港股@所属恒生行业(二级)": "工业工程",
            "港股@经营活动产生的现金流量净额[20251231]": 300000000,
            "港股@投资活动产生的现金流量净额[20251231]": -50000000,
            "港股@资本性支出[20251231]": -100000000,
            "港股@权益合计[20251231]": 1000000000,
            "港股@年度分红总额[20251231]": 30000000,
            "港股@投入资本回报率[20251231]": 15,
        }
        row_a = {
            **base,
            "股票代码": "1001.HK",
            "股票简称": "甲",
            "港股@总市值[20260309]": 1000000000,
            "港股@归属于母公司所有者的净利润[20251231]": 100000000,
            "港股@归属母公司股东的净利润(同比增长率)[20251231]": 25,
        }
        row_b = {
            **base,
            "股票代码": "1002.HK",
            "股票简称": "乙",
            "港股@总市值[20260309]": 1500000000,
            "港股@归属于母公司所有者的净利润[20251231]": 90000000,
            "港股@归属母公司股东的净利润(同比增长率)[20251231]": 10,
        }
        phase1_list = [compute_phase1(row_a, MARKET_KEYS), compute_phase1(row_b, MARKET_KEYS)]
        rankings = compute_rankings(phase1_list)
        self.assertEqual(rankings[0][5], "1")
        self.assertEqual(rankings[1][5], "2")

    def test_projected_dividend_below_zero_is_clamped_to_zero(self):
        row = {
            "股票代码": "1888.HK",
            "股票简称": "分红测试",
            "港股@所属恒生行业(二级)": "工业工程",
            "港股@总市值[20260309]": 1000000000,
            "港股@归属于母公司所有者的净利润[20250930]": 10000000,
            "港股@归属于母公司所有者的净利润[20241231]": 100000000,
            "港股@归属于母公司所有者的净利润[20240930]": 120000000,
            "港股@归属于母公司所有者的净利润[20231231]": 90000000,
            "港股@归属于母公司所有者的净利润[20230930]": 10000000,
            "港股@年度分红总额[20241231]": 50000000,
            "港股@投入资本回报率[20250930]": 10,
        }
        phase1 = compute_phase1(row, MARKET_KEYS)
        self.assertEqual(phase1["vals"][17], "0")
        self.assertEqual(phase1["vals"][18], "0")

    def test_financial_ranking_uses_raw_iwencai_pe(self):
        row_a = {
            "股票代码": "0001.HK",
            "股票简称": "金融甲",
            "港股@所属恒生行业(二级)": "银行",
            "港股@总市值[20260309]": 1000000000,
            "港股@市盈率(pe,ttm)[20260306]": 8,
            "港股@归属于母公司所有者的净利润[20251231]": 100000000,
            "港股@净资产收益率roe[20251231]": 10,
            "港股@年度分红总额[20251231]": 10000000,
        }
        row_b = {
            "股票代码": "0002.HK",
            "股票简称": "金融乙",
            "港股@所属恒生行业(二级)": "银行",
            "港股@总市值[20260309]": 200000000,
            "港股@市盈率(pe,ttm)[20260306]": 12,
            "港股@归属于母公司所有者的净利润[20251231]": 100000000,
            "港股@净资产收益率roe[20251231]": 8,
            "港股@年度分红总额[20251231]": 10000000,
        }
        phase1_list = [compute_phase1(row_a, MARKET_KEYS), compute_phase1(row_b, MARKET_KEYS)]
        rankings = compute_rankings(phase1_list)
        self.assertEqual(phase1_list[0]["pe_ttm"], 8)
        self.assertEqual(phase1_list[1]["pe_ttm"], 12)
        self.assertEqual(rankings[0][0], "1")
        self.assertEqual(rankings[1][0], "2")


if __name__ == "__main__":
    unittest.main()
