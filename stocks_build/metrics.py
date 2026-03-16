"""Metric computation for the HK stocks dashboard."""

from .config import JINRONG_SET, NET_ASSETS_CANDIDATES, PERIOD_DATES

PERIOD_CODE = {label: code for code, label in PERIOD_DATES}


def get_float(obj, raw_metric, period_label):
    date_code = PERIOD_CODE.get(period_label)
    if not date_code:
        return None
    val = obj.get(f"港股@{raw_metric}[{date_code}]")
    if val is None or val == "":
        return None
    try:
        fval = float(val)
    except Exception:
        return None
    return None if fval != fval else fval


def is_jinrong(obj):
    ind = str(obj.get("港股@所属恒生行业(二级)", "") or "")
    name = str(obj.get("股票简称", "") or "")
    if ind == "综合企业" and "中信股份" in name:
        obj["港股@所属恒生行业(二级)"] = "其他金融"
        return True
    return ind in JINRONG_SET


def format_value(value):
    if value is None:
        return "--"
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e13:
            return str(int(value))
        return str(round(value, 4))
    return str(value)


def build_market_keys(rows):
    def autodetect_key(prefix, fallback):
        if rows:
            for key in rows[0].keys():
                if key.startswith(prefix):
                    return key
        return fallback

    return {
        "price": "港股@最新价",
        "chg": "港股@最新涨跌幅",
        "mktcap": autodetect_key("港股@总市值[", "港股@总市值[20260309]"),
        "pe": autodetect_key("港股@市盈率(pe,ttm)[", "港股@市盈率(pe,ttm)[20260306]"),
        "pb": autodetect_key("港股@市净率(pb)[", "港股@市净率(pb)[20260309]"),
        "shares": autodetect_key("港股@总股本[", "港股@总股本[20260309]"),
    }


def clean_code(raw_code):
    code = str(raw_code).replace(".HK", "").replace("HK", "").strip()
    return code.zfill(5) if code.isdigit() else code


def filter_source_rows(rows):
    rows = [
        row
        for row in rows
        if not (row.get("股票简称", "").endswith("R") and "-" in row.get("股票简称", ""))
    ]
    names = {row.get("股票简称", "") for row in rows}
    return [
        row
        for row in rows
        if not (
            row.get("股票简称", "").endswith("-B")
            and row.get("股票简称", "")[:-2] in names
        )
    ]


def inject_market(obj, market_data, market_keys):
    code = clean_code(obj.get("股票代码", ""))
    snapshot = market_data.get(code)
    if not snapshot:
        return
    if snapshot.get("price") is not None:
        obj[market_keys["price"]] = snapshot["price"]
    if snapshot.get("change_pct") is not None:
        obj[market_keys["chg"]] = snapshot["change_pct"]
    if snapshot.get("mkt_cap") is not None:
        obj[market_keys["mktcap"]] = snapshot["mkt_cap"]


def compute_phase1(obj, market_keys):
    profit_metric = "归属于母公司所有者的净利润"
    cash_metric = "总现金"
    current_assets_metric = "流动资产合计"
    liability_metric = "负债合计"
    short_debt_metric = "短期借款"
    long_debt_metric = "长期借款"
    roe_metric = "净资产收益率roe"
    roic_metric = "投入资本回报率"
    ocf_metric = "经营活动产生的现金流量净额"
    icf_metric = "投资活动产生的现金流量净额"
    capex_metric = "资本性支出"
    financing_metric = "融资活动产生的现金流量净额"
    buyback_metric = "股份回购"
    dividend_paid_metric = "支付股息"
    annual_dividend_metric = "年度分红总额"

    def gf(metric, period):
        return get_float(obj, metric, period)

    has_annual = gf(profit_metric, "2025年报") is not None
    has_q3 = gf(profit_metric, "2025三季报") is not None
    latest_period = "2025年报" if has_annual else ("2025三季报" if has_q3 else "2025中报")

    def ttm(metric, q_latest, annual, q_base):
        recent, annual_full, base = gf(metric, q_latest), gf(metric, annual), gf(metric, q_base)
        return None if any(v is None for v in [recent, annual_full, base]) else recent + (annual_full - base)

    if has_annual:
        ttm_profit = gf(profit_metric, "2025年报")
        ttm_base = gf(profit_metric, "2024年报")
        annual_yoy = gf("归属母公司股东的净利润(同比增长率)", "2025年报")
        if annual_yoy is not None:
            ttm_yoy = annual_yoy
        elif ttm_profit is not None and ttm_base and ttm_base != 0:
            ttm_yoy = (ttm_profit - ttm_base) / abs(ttm_base) * 100
        else:
            ttm_yoy = None
    elif has_q3:
        ttm_profit = ttm(profit_metric, "2025三季报", "2024年报", "2024三季报")
        ttm_base = ttm(profit_metric, "2024三季报", "2023年报", "2023三季报")
        ttm_yoy = ((ttm_profit - ttm_base) / abs(ttm_base) * 100) if ttm_profit is not None and ttm_base and ttm_base != 0 else None
    else:
        ttm_profit = ttm(profit_metric, "2025中报", "2024年报", "2024中报")
        ttm_base = ttm(profit_metric, "2024中报", "2023年报", "2023中报")
        ttm_yoy = ((ttm_profit - ttm_base) / abs(ttm_base) * 100) if ttm_profit is not None and ttm_base and ttm_base != 0 else None

    def ttm_pct(metric):
        if has_annual:
            annual = gf(metric, "2025年报")
            if annual is not None:
                return annual
        quarter3 = gf(metric, "2025三季报")
        if quarter3 is not None:
            annual, base = gf(metric, "2024年报"), gf(metric, "2024三季报")
            return (quarter3 + (annual - base)) if annual is not None and base is not None else (quarter3 / 3 * 4)
        half_year = gf(metric, "2025中报")
        if half_year is not None:
            annual, base = gf(metric, "2024年报"), gf(metric, "2024中报")
            return (half_year + (annual - base)) if annual is not None and base is not None else (half_year * 2)
        return None

    def ttm_yi(metric):
        if has_annual:
            annual = gf(metric, "2025年报")
            if annual is not None:
                return annual
        quarter3 = gf(metric, "2025三季报")
        if quarter3 is not None:
            return ttm(metric, "2025三季报", "2024年报", "2024三季报")
        half_year = gf(metric, "2025中报")
        if half_year is not None:
            return ttm(metric, "2025中报", "2024年报", "2024中报")
        return None

    def neg_only(value):
        return None if value is None or value > 0 else value

    def negate_neg_only(value):
        if value is None:
            return None
        return None if -value > 0 else -value

    def gv(metric):
        return gf(metric, latest_period)

    financial = is_jinrong(obj)
    ttm_roe = ttm_pct(roe_metric)
    ttm_roic = ttm_pct(roic_metric)
    ttm_ocf = ttm_yi(ocf_metric)
    ttm_icf = ttm_yi(icf_metric)
    ttm_capex = negate_neg_only(ttm_yi(capex_metric))

    if financial:
        net_cash = None
        interest_debt = None
        ttm_fcf = None
        shareholder_yield = None
    else:
        net_cash = (gv(cash_metric) or 0) - (gv(short_debt_metric) or 0) - (gv(long_debt_metric) or 0)
        interest_debt = (gv(short_debt_metric) or 0) + (gv(long_debt_metric) or 0)
        fcf1 = (ttm_ocf + ttm_capex) if ttm_ocf is not None and ttm_capex is not None else None
        fcf2 = (ttm_ocf + ttm_icf) if ttm_ocf is not None and ttm_icf is not None else None
        if fcf1 is not None and fcf2 is not None:
            ttm_fcf = max(fcf1, fcf2)
        else:
            ttm_fcf = fcf1 if fcf1 is not None else fcf2
        try:
            market_cap = float(obj.get(market_keys["mktcap"]) or 0) or None
        except Exception:
            market_cap = None
        if ttm_fcf is not None and market_cap is not None:
            denominator = market_cap + net_cash
            shareholder_yield = (ttm_fcf / denominator * 100) if denominator != 0 else None
        else:
            shareholder_yield = None

    actual_dividend_2025 = gf(annual_dividend_metric, "2025年报")
    if has_annual:
        if actual_dividend_2025 is None:
            expected_dividend = None
        else:
            expected_dividend = max(actual_dividend_2025, 0)
    else:
        dividend_2024 = gf(annual_dividend_metric, "2024年报")
        projected = None if dividend_2024 is None or ttm_yoy is None else dividend_2024 * (1 + ttm_yoy / 100)
        expected_dividend = None if projected is None else max(projected, 0)

    buyback_raw = neg_only(ttm_yi(buyback_metric))
    buyback_abs = (-buyback_raw) if buyback_raw is not None else 0
    expected_return = (expected_dividend or 0) + (buyback_abs / 2)
    return_ratio = None if ttm_profit is None or ttm_profit == 0 else expected_return / ttm_profit * 100

    try:
        market_cap_numeric = float(obj.get(market_keys["mktcap"]) or 0) or None
    except Exception:
        market_cap_numeric = None

    if market_cap_numeric is not None and ttm_profit is not None and ttm_profit > 0:
        pe_ttm = market_cap_numeric / ttm_profit
        obj[market_keys["pe"]] = pe_ttm
    else:
        try:
            pe_ttm = float(obj.get(market_keys["pe"]) or 0) or None
        except Exception:
            pe_ttm = None

    net_assets = None
    for _, period_label in PERIOD_DATES:
        for candidate in NET_ASSETS_CANDIDATES:
            net_assets = get_float(obj, candidate, period_label)
            if net_assets is not None:
                break
        if net_assets is not None:
            break

    if market_cap_numeric is not None and net_assets is not None and net_assets > 0:
        obj[market_keys["pb"]] = market_cap_numeric / net_assets

    return {
        "vals": [
            latest_period,
            format_value(ttm_profit),
            format_value(ttm_yoy),
            format_value(gv(cash_metric)),
            format_value(gv(current_assets_metric)),
            format_value(gv(liability_metric)),
            format_value(gv(short_debt_metric)),
            format_value(gv(long_debt_metric)),
            format_value(net_assets),
            format_value(ttm_roe),
            format_value(ttm_roic),
            format_value(ttm_ocf),
            format_value(ttm_icf),
            format_value(ttm_capex),
            format_value(ttm_yi(financing_metric)),
            format_value(neg_only(ttm_yi(buyback_metric))),
            format_value(neg_only(ttm_yi(dividend_paid_metric))),
            format_value(expected_dividend),
            format_value(expected_return),
            format_value(net_cash),
            format_value(interest_debt),
            format_value(ttm_fcf),
            format_value(shareholder_yield),
            format_value(return_ratio),
        ],
        "is_jinrong": financial,
        "ttm_yoy": ttm_yoy,
        "ttmroe": ttm_roe,
        "ttmroic": ttm_roic,
        "pe_ttm": pe_ttm,
        "shareholder_yield": shareholder_yield,
        "return_ratio": return_ratio,
    }
