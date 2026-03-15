#!/usr/bin/env python3
"""Build self-contained HTML page for HK stock data (new object-format input)."""
import json, re, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'hk_stocks_data_new.json'), encoding='utf-8') as f:
    raw = json.load(f)

# ---- 易变市场字段 key（iwencai 原始 key，在此集中定义）----
# 日期后缀字段（总市值、PE、PB、总股本）每次重抓后日期会变，用 _autodetect_key 自动匹配，
# 无需每次手动更新硬编码日期。
def _autodetect_key(rows, prefix, fallback):
    """扫描第一行数据，找到以 prefix 开头的 key；找不到则返回 fallback。"""
    if rows:
        for k in rows[0].keys():
            if k.startswith(prefix):
                return k
    return fallback

_rows0 = raw.get('rows', [])
MKT_KEY_PRICE  = '港股@最新价'
MKT_KEY_CHG    = '港股@最新涨跌幅'
MKT_KEY_MKTCAP = _autodetect_key(_rows0, '港股@总市值[',         '港股@总市值[20260309]')
MKT_KEY_PE     = _autodetect_key(_rows0, '港股@市盈率(pe,ttm)[', '港股@市盈率(pe,ttm)[20260306]')
MKT_KEY_PB     = _autodetect_key(_rows0, '港股@市净率(pb)[',     '港股@市净率(pb)[20260309]')
MKT_KEY_SHARES = _autodetect_key(_rows0, '港股@总股本[',          '港股@总股本[20260309]')
print(f"📊 MKT keys: MKTCAP={MKT_KEY_MKTCAP!r}  SHARES={MKT_KEY_SHARES!r}")

# ---- 净资产字段候选（按优先级，iwencai 重抓后自动匹配，无需手动确认）----
# PE/PB 动态计算时，净资产从此列表中自动探测实际存在的字段名
_NET_ASSETS_CANDIDATES = [
    '归属于母公司股东的权益合计',
    '归属于母公司所有者权益合计',
    '所有者权益合计',
    '权益合计',
    '净资产',
]

# ---- 加载 AKShare 市场数据（若存在则覆盖易变字段，否则使用 iwencai 原始数据）----
_market_data = {}
_market_updated_at = None
_FINANCIAL_JSON_PATH = os.path.join(BASE_DIR, 'hk_stocks_data_new.json')
_MARKET_JSON_PATH    = os.path.join(BASE_DIR, 'hk_stocks_market.json')
if os.path.exists(_MARKET_JSON_PATH):
    try:
        with open(_MARKET_JSON_PATH, encoding='utf-8') as _f:
            _md = json.load(_f)
        _market_data = _md.get('data', {})
        _market_updated_at = _md.get('updated_at', '?')
        print(f"市场数据已加载: {len(_market_data)} 只, 更新于 {_market_updated_at}")
    except Exception as _e:
        print(f"警告: 市场数据加载失败 ({_e}), 使用 iwencai 原始数据")

# ---- 数据优先级：比较两个 JSON 的修改时间 ----
# 规则：
#   iwencai JSON（hk_stocks_data_new.json）更新时 → iwencai 为准（跳过 AKShare 注入）
#   AKShare JSON（hk_stocks_market.json）更新时   → 注入易变字段（价格/市值）
# 这样每次完整重抓 iwencai 后，PE/PB/市值等均以 iwencai 最新值为基础计算；
# 日常 daily_update.sh 小更新时，再用 AKShare 刷新价格和市值。
_financial_mtime = os.path.getmtime(_FINANCIAL_JSON_PATH)
_market_mtime    = os.path.getmtime(_MARKET_JSON_PATH) if os.path.exists(_MARKET_JSON_PATH) else 0.0
_use_market_injection = bool(_market_data) and (_market_mtime > _financial_mtime)

# ---- Column schema ----
# Fixed columns (order matters; idx 0 = 序号 computed)
FIXED_COLS = [
    # (display_name, raw_key_or_None)
    # 易变字段使用 MKT_KEY_* 常量，方便统一维护
    ('序号',           None),
    ('股票代码',        '股票代码'),
    ('股票简称',        '股票简称'),
    ('最新价(港元)',    MKT_KEY_PRICE),
    ('最新涨跌幅(%)',   MKT_KEY_CHG),
    ('总市值(港元)',    MKT_KEY_MKTCAP),
    ('市盈率(pe,ttm)', MKT_KEY_PE),
    ('市净率(pb)',      MKT_KEY_PB),
    ('总股本(股)',      MKT_KEY_SHARES),
    ('所属恒生行业',    '港股@所属恒生行业(二级)'),
]

# Periods: most recent first
PERIOD_DATES = [
    ('20251231', '2025年报'),
    ('20250930', '2025三季报'),
    ('20250630', '2025中报'),
    ('20250331', '2025一季报'),
    ('20241231', '2024年报'),
    ('20240930', '2024三季报'),
    ('20240630', '2024中报'),
    ('20240331', '2024一季报'),
    ('20231231', '2023年报'),
    ('20230930', '2023三季报'),
    ('20230630', '2023中报'),
    ('20230331', '2023一季报'),
]

# Metrics per period (raw_name → display_name)
PERIOD_METRICS = [
    ('归属于母公司所有者的净利润',       '归母净利润'),
    ('归属母公司股东的净利润(同比增长率)', '净利润同比'),
    ('总现金',                           '总现金'),
    ('流动资产合计',                     '流动资产'),
    ('负债合计',                         '总负债'),
    ('短期借款',                         '短期借款'),
    ('长期借款',                         '长期借款'),
    ('权益合计',                         '权益合计'),
    ('净资产收益率roe',                   'ROE'),
    ('投入资本回报率',                    'ROIC'),
    ('经营活动产生的现金流量净额',        '经营现金流'),
    ('投资活动产生的现金流量净额',        '投资现金流'),
    ('资本性支出',                        '资本支出'),
    ('融资活动产生的现金流量净额',        '融资现金流'),
    ('股份回购',                          '股份回购'),
    ('支付股息',                          '支付股息'),
    ('年度分红总额',                      '年度分红'),
]

# Computed columns inserted after fixed cols (idx 10-37, total 28 cols)
COMPUTED_COL_DEFS = [
    '最新财报季',     # idx 10: text
    'TTM归母净利润',  # idx 11: 亿
    'TTM净利同比',    # idx 12: %
    '最新总现金',     # idx 13: 亿
    '最新流动资产',   # idx 14: 亿
    '最新总负债',     # idx 15: 亿
    '最新短期借款',   # idx 16: 亿
    '最新长期借款',   # idx 17: 亿
    '最新权益合计',   # idx 18: 亿
    'TTMROE',         # idx 19: %
    'TTMROIC',        # idx 20: %
    'TTM经营现金流',  # idx 21: 亿
    'TTM投资现金流',  # idx 22: 亿
    'TTM资本支出',    # idx 23: 亿
    'TTM融资现金流',  # idx 24: 亿
    'TTM股份回购',    # idx 25: 亿
    'TTM支付股息',    # idx 26: 亿
    '预期25年度分红', # idx 27: 亿
    '预期25股东回报', # idx 28: 亿
    '净现金',         # idx 29: 亿（金融股为空）
    '有息负债',       # idx 30: 亿（金融股为空）
    'TTMFCF',         # idx 31: 亿（金融股为空）
    '股东收益率',     # idx 32: %（金融股为空）
    '股东回报分配率', # idx 33: %
    '低估排名',       # idx 34: 整数排名（越小越好）
    '成长排名',       # idx 35: 整数排名（越小越好）
    '质量排名',       # idx 36: 整数排名（越小越好）
    '股东回报排名',   # idx 37: 整数排名（越小越好）
    '综合分数',       # idx 38: 加权综合（越小越好）
    '综合排名',       # idx 39: 综合分数排名（越小越好，金融/非金融分队列）
]

# Period metrics hidden by default (replaced by computed "最新" cols)
METRICS_HIDE_DEFAULT = {
    '归母净利润', '净利润同比', '总现金', '流动资产', '总负债', '短期借款', '长期借款', '权益合计',
    'ROE', 'ROIC',
    '经营现金流', '投资现金流', '资本支出', '融资现金流', '股份回购', '支付股息',
    '年度分红',
}

# Fixed columns hidden by default (non-locked 基本信息 columns)
FIXED_HIDE_DEFAULT = {'总股本(股)'}

# Computed columns hidden by default
COMPUTED_HIDE_DEFAULT = {
    'TTM股份回购', 'TTM支付股息', '预期25年度分红',
    '最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款', '最新权益合计',
    '综合分数',
    'TTM经营现金流', 'TTM投资现金流', 'TTM资本支出', 'TTM融资现金流', '预期25股东回报', '有息负债',
}

# Build full column list
all_cols = []
for i, (display, raw_key) in enumerate(FIXED_COLS):
    locked = i < 3
    all_cols.append({
        'header': display,
        'raw_key': raw_key,
        'group': '基本信息',
        'locked': locked,
        'defaultVisible': display not in FIXED_HIDE_DEFAULT,
    })

for name in COMPUTED_COL_DEFS:
    all_cols.append({
        'header': name,
        'raw_key': None,
        'group': '计算指标',
        'locked': False,
        'defaultVisible': True,
    })

for raw_metric, display_metric in PERIOD_METRICS:
    default_vis = display_metric not in METRICS_HIDE_DEFAULT
    for date_code, date_label in PERIOD_DATES:
        raw_key = f'港股@{raw_metric}[{date_code}]'
        all_cols.append({
            'header': f'{display_metric}|{date_label}',
            'raw_key': raw_key,
            'group': display_metric,
            'locked': False,
            'defaultVisible': default_vis,
        })

headers = [c['header'] for c in all_cols]

# ---- Filter rows ----
def clean_code(raw_code):
    """Convert '2617.HK' → '02617'"""
    code = str(raw_code).replace('.HK', '').replace('HK', '').strip()
    if code.isdigit():
        return code.zfill(5)
    return code


def _inject_market(obj):
    """用 AKShare 最新行情覆盖 obj 中的价格/市值易变字段（各项有值才覆盖）。
    覆盖同一 key，下游 FIXED_COLS / compute_phase1 无需改动。
    受影响的计算链：mkt_cap → PE/PB 动态值 → 股东收益率 → 低估排名 → 综合排名。
    注：PE/PB 由 compute_phase1 根据最新 mkt_cap 动态计算，此处不再注入 PE/PB 静态值。
    """
    code = clean_code(obj.get('股票代码', ''))
    m = _market_data.get(code)
    if not m:
        return
    if m.get('price') is not None:
        obj[MKT_KEY_PRICE] = m['price']
    if m.get('change_pct') is not None:
        obj[MKT_KEY_CHG] = m['change_pct']
    if m.get('mkt_cap') is not None:
        obj[MKT_KEY_MKTCAP] = m['mkt_cap']
    # PE/PB 不从 AKShare 注入：由 compute_phase1 根据 mkt_cap + 财务数据动态计算
    # 总股本（MKT_KEY_SHARES）不从 AKShare 更新：变动极少，iwencai 数据已足够


obj_rows = raw['rows']

# Remove RMB counter stocks: 股票简称 ends with R after hyphen
obj_rows = [r for r in obj_rows
            if not (r.get('股票简称', '').endswith('R') and '-' in r.get('股票简称', ''))]

# Remove B-share duplicates: if both "X" and "X-B" exist, remove "X-B"
names = {r.get('股票简称', '') for r in obj_rows}
obj_rows = [r for r in obj_rows
            if not (r.get('股票简称', '').endswith('-B')
                    and r.get('股票简称', '')[:-2] in names)]

# ---- 注入 AKShare 市场数据（在过滤之后、计算之前）----
# _use_market_injection = True  → AKShare 更新较新，注入最新价格/市值
# _use_market_injection = False → iwencai 重抓较新，以 iwencai 为准（包含最新 PE/PB/市值）
if _use_market_injection:
    injected = sum(1 for obj in obj_rows if _market_data.get(clean_code(obj.get('股票代码', ''))))
    for obj in obj_rows:
        _inject_market(obj)
    print(f"AKShare 注入: {injected}/{len(obj_rows)} 只股票已更新价格/市值（市场数据: {_market_updated_at}）")
elif _market_data:
    print(f"iwencai 数据更新（mtime 较新），跳过 AKShare 注入，以 iwencai 原始值为准")
else:
    print("市场数据未加载，使用 iwencai 原始数据（运行 update_market.py 可获取最新行情）")

# ---- Computed column helpers ----
PERIOD_CODE = {label: code for code, label in PERIOD_DATES}
JINRONG_SET = {'保险', '其他金融', '银行'}

def _get_float(obj, raw_metric, period_label):
    date_code = PERIOD_CODE.get(period_label)
    if not date_code:
        return None
    val = obj.get(f'港股@{raw_metric}[{date_code}]')
    if val is None or val == '':
        return None
    try:
        f = float(val)
        return None if f != f else f  # NaN guard
    except:
        return None

def _is_jinrong(obj):
    ind  = str(obj.get('港股@所属恒生行业(二级)', '') or '')
    name = str(obj.get('股票简称', '') or '')
    if ind == '综合企业' and '中信股份' in name:
        obj['港股@所属恒生行业(二级)'] = '其他金融'
        return True
    return ind in JINRONG_SET

def _has_any_roic(obj):
    for _, label in PERIOD_DATES:
        if _get_float(obj, '投入资本回报率', label) is not None:
            return True
    return False

def _fmt(v):
    """Format a numeric value for storage: None→'--', int-like→str(int), else round to 4dp."""
    if v is None: return '--'
    if isinstance(v, float):
        return str(int(v)) if (v == int(v) and abs(v) < 1e13) else str(round(v, 4))
    return str(v)

def compute_phase1(obj):
    """
    Compute per-row derived values for idx 10-32 (23 cols).
    Returns dict with 'vals' (list of formatted strings) and raw numerics for ranking.
    """
    P       = '归属于母公司所有者的净利润'
    CH      = '总现金'
    CA      = '流动资产合计'
    LB      = '负债合计'
    SD      = '短期借款'
    LD      = '长期借款'
    ROE     = '净资产收益率roe'
    ROIC    = '投入资本回报率'
    OCF     = '经营活动产生的现金流量净额'
    ICF     = '投资活动产生的现金流量净额'
    CAP     = '资本性支出'
    FCF_CF  = '融资活动产生的现金流量净额'
    BUY     = '股份回购'
    DIV     = '支付股息'
    DIV_ANN = '年度分红总额'

    def gf(metric, period): return _get_float(obj, metric, period)

    has_annual  = gf(P, '2025年报') is not None
    has_q3      = gf(P, '2025三季报') is not None

    # latest_period: 2025年报 > 2025三季报 > 2025中报
    if has_annual:
        lp = '2025年报'
    elif has_q3:
        lp = '2025三季报'
    else:
        lp = '2025中报'

    def ttm(metric, q_latest, annual, q_base):
        r, a, b = gf(metric, q_latest), gf(metric, annual), gf(metric, q_base)
        return None if any(v is None for v in [r, a, b]) else r + (a - b)

    # TTM归母净利润 and YoY
    if has_annual:
        ttm_p    = gf(P, '2025年报')
        ttm_base = gf(P, '2024年报')
        # 优先用年报自带同比字段
        _ann_yoy = gf('归属母公司股东的净利润(同比增长率)', '2025年报')
        if _ann_yoy is not None:
            ttm_yoy = _ann_yoy
        elif ttm_p is not None and ttm_base and ttm_base != 0:
            ttm_yoy = (ttm_p - ttm_base) / abs(ttm_base) * 100
        else:
            ttm_yoy = None
    elif has_q3:
        ttm_p    = ttm(P, '2025三季报', '2024年报', '2024三季报')
        ttm_base = ttm(P, '2024三季报', '2023年报', '2023三季报')
        ttm_yoy  = ((ttm_p - ttm_base) / abs(ttm_base) * 100
                    if ttm_p is not None and ttm_base and ttm_base != 0 else None)
    else:
        ttm_p    = ttm(P, '2025中报', '2024年报', '2024中报')
        ttm_base = ttm(P, '2024中报', '2023年报', '2023中报')
        ttm_yoy  = ((ttm_p - ttm_base) / abs(ttm_base) * 100
                    if ttm_p is not None and ttm_base and ttm_base != 0 else None)

    def ttm_pct(metric):
        """TTM for % metrics (ROE/ROIC): 年报直接用, then Q3, fallback H1."""
        if has_annual:
            ann = gf(metric, '2025年报')
            if ann is not None:
                return ann
        r_q3 = gf(metric, '2025三季报')
        if r_q3 is not None:
            a, b = gf(metric, '2024年报'), gf(metric, '2024三季报')
            return (r_q3 + (a - b)) if a is not None and b is not None else (r_q3 / 3 * 4)
        r_h1 = gf(metric, '2025中报')
        if r_h1 is not None:
            a, b = gf(metric, '2024年报'), gf(metric, '2024中报')
            return (r_h1 + (a - b)) if a is not None and b is not None else (r_h1 * 2)
        return None

    def ttm_yi(raw_metric):
        """TTM for 亿 metrics: 年报直接用, then Q3/H1 TTM calculation."""
        if has_annual:
            ann = gf(raw_metric, '2025年报')
            if ann is not None:
                return ann
        q3 = gf(raw_metric, '2025三季报')
        if q3 is not None:
            return ttm(raw_metric, '2025三季报', '2024年报', '2024三季报')
        h1 = gf(raw_metric, '2025中报')
        if h1 is not None:
            return ttm(raw_metric, '2025中报', '2024年报', '2024中报')
        return None

    def neg_only(v):
        """If value is positive (anomalous), return None; else keep."""
        return None if v is None or v > 0 else v

    def negate_neg_only(v):
        """Negate; if result is positive (anomalous), return None."""
        if v is None: return None
        return None if -v > 0 else -v

    def gv(metric): return gf(metric, lp)

    # ---- Pre-compute intermediates ----
    is_jrong = _is_jinrong(obj)
    is_other = (not is_jrong) and (not _has_any_roic(obj))

    v_ttmroe  = ttm_pct(ROE)
    v_ttmroic = ttm_pct(ROIC)
    v_ocf     = ttm_yi(OCF)
    v_icf     = ttm_yi(ICF)
    v_cap     = negate_neg_only(ttm_yi(CAP))   # stored as negative (outflow) or None

    # 净现金: 总现金 - 短期借款 - 长期借款（各项为空视为0；金融股→空）
    if is_jrong:
        v_net_cash = None
    else:
        _ch, _sd, _ld = gv(CH), gv(SD), gv(LD)
        v_net_cash = (_ch or 0) - (_sd or 0) - (_ld or 0)

    # 有息负债: 短期借款 + 长期借款（各项为空视为0；金融股→空）
    if is_jrong:
        v_interest_debt = None
    else:
        _sd2, _ld2 = gv(SD), gv(LD)
        v_interest_debt = (_sd2 or 0) + (_ld2 or 0)

    # TTMFCF: max(OCF+CapEx, OCF+ICF)
    if is_jrong:
        v_ttmfcf = None
    else:
        fcf1 = (v_ocf + v_cap) if v_ocf is not None and v_cap is not None else None
        fcf2 = (v_ocf + v_icf) if v_ocf is not None and v_icf is not None else None
        if fcf1 is not None and fcf2 is not None:
            v_ttmfcf = max(fcf1, fcf2)
        else:
            v_ttmfcf = fcf1 if fcf1 is not None else fcf2

    # 股东收益率: TTMFCF / (总市值 + 净现金) * 100
    if is_jrong:
        v_shareholder_yield = None
    else:
        try:
            mkt_cap = float(obj.get(MKT_KEY_MKTCAP) or 0) or None
        except:
            mkt_cap = None
        # v_net_cash 对非金融股始终为数值（空项已视为0）
        if v_ttmfcf is not None and mkt_cap is not None:
            denom = mkt_cap + v_net_cash
            v_shareholder_yield = (v_ttmfcf / denom * 100) if denom != 0 else None
        else:
            v_shareholder_yield = None

    # 预期25年度分红:
    # - 有25年报财务数据(has_annual)：直接等同25年报年度分红（无分红数据则为空）
    #   注：25年报分红字段可能因中期分红等原因有数据但财务报表未出，故以财务数据存在与否为准
    # - 无25年报财务数据：按旧方法估算 2024年度分红×(1+TTM净利同比/100)；结果为负→空
    _div_2025_actual = gf(DIV_ANN, '2025年报')
    if has_annual:
        v_exp_div = None if (_div_2025_actual is None or _div_2025_actual < 0) else _div_2025_actual
    else:
        _div_2024    = gf(DIV_ANN, '2024年报')
        _exp_div_raw = (None if _div_2024 is None or ttm_yoy is None
                        else _div_2024 * (1 + ttm_yoy / 100))
        v_exp_div = None if (_exp_div_raw is not None and _exp_div_raw < 0) else _exp_div_raw

    # 预期25股东回报: 预期25年度分红 + |TTM股份回购| / 2
    # 各项为空视为0，避免某一项缺失导致整体为空（如有分红无回购数据，回报仍应有值）
    v_buy_raw = neg_only(ttm_yi(BUY))
    v_buy_abs = (-v_buy_raw) if v_buy_raw is not None else 0
    v_exp_return = (v_exp_div or 0) + (v_buy_abs / 2)

    # 股东回报分配率: 预期25股东回报 / TTM归母净利润 * 100
    v_return_ratio = (None if ttm_p is None or ttm_p == 0
                      else v_exp_return / ttm_p * 100)

    # ---- 获取总市值（PE/PB 动态计算公用，所有股票均需）----
    try:
        _mkt_cap = float(obj.get(MKT_KEY_MKTCAP) or 0) or None
    except:
        _mkt_cap = None

    # ---- PE(TTM) 动态计算 = 总市值 / TTM归母净利润 ----
    # 条件：ttm_p > 0（亏损时 PE 无意义）且 mkt_cap 有值
    # 优先动态值，fallback 到 iwencai 静态值
    if _mkt_cap is not None and ttm_p is not None and ttm_p > 0:
        v_pe_ttm = _mkt_cap / ttm_p
        obj[MKT_KEY_PE] = v_pe_ttm   # 回写，供 FIXED_COLS 列和 JS 显示
    else:
        try:
            v_pe_ttm = float(obj.get(MKT_KEY_PE) or 0) or None
        except:
            v_pe_ttm = None

    # ---- PB 动态计算 = 总市值 / 净资产（取最近有数据的报期）----
    # 净资产字段名由 _NET_ASSETS_CANDIDATES 自动探测（iwencai 重抓后生效）
    # fallback：若净资产数据暂缺，保留 iwencai 静态 PB
    _net_assets = None
    for _, _period_label in PERIOD_DATES:
        for _na_raw in _NET_ASSETS_CANDIDATES:
            _val = _get_float(obj, _na_raw, _period_label)
            if _val is not None:
                _net_assets = _val
                break
        if _net_assets is not None:
            break

    if _mkt_cap is not None and _net_assets is not None and _net_assets > 0:
        obj[MKT_KEY_PB] = _mkt_cap / _net_assets   # 回写，供 FIXED_COLS 列显示

    return {
        'vals': [
            lp,                                   # 10: 最新财报季
            _fmt(ttm_p),                          # 11: TTM归母净利润
            _fmt(ttm_yoy),                        # 12: TTM净利同比
            _fmt(gv(CH)),                         # 13: 最新总现金
            _fmt(gv(CA)),                         # 14: 最新流动资产
            _fmt(gv(LB)),                         # 15: 最新总负债
            _fmt(gv(SD)),                         # 16: 最新短期借款
            _fmt(gv(LD)),                         # 17: 最新长期借款
            _fmt(_net_assets),                    # 18: 最新权益合计
            _fmt(v_ttmroe),                       # 19: TTMROE
            _fmt(v_ttmroic),                      # 20: TTMROIC
            _fmt(v_ocf),                          # 21: TTM经营现金流
            _fmt(v_icf),                          # 22: TTM投资现金流 (可正可负)
            _fmt(v_cap),                          # 23: TTM资本支出 (取反，>0则空)
            _fmt(ttm_yi(FCF_CF)),                 # 24: TTM融资现金流
            _fmt(neg_only(ttm_yi(BUY))),          # 25: TTM股份回购 (>0则空)
            _fmt(neg_only(ttm_yi(DIV))),          # 26: TTM支付股息 (>0则空)
            _fmt(v_exp_div),                      # 27: 预期25年度分红
            _fmt(v_exp_return),                   # 28: 预期25股东回报
            _fmt(v_net_cash),                     # 29: 净现金
            _fmt(v_interest_debt),                # 30: 有息负债
            _fmt(v_ttmfcf),                       # 31: TTMFCF
            _fmt(v_shareholder_yield),            # 32: 股东收益率 (%)
            _fmt(v_return_ratio),                 # 33: 股东回报分配率 (%)
        ],
        'is_jinrong': is_jrong,
        'is_other':   is_other,
        # Raw numerics for cross-row ranking
        'ttm_yoy':          ttm_yoy,
        'ttmroe':           v_ttmroe,
        'ttmroic':          v_ttmroic,
        'pe_ttm':           v_pe_ttm,
        'shareholder_yield': v_shareholder_yield,
        'return_ratio':     v_return_ratio,
    }

# ---- Cross-row ranking helpers ----
def _competition_rank(sorted_items):
    """
    Standard competition ranking (1224 style) over a pre-sorted list of (idx, value).
    Returns dict: idx → rank (1-based).
    Ties share the same rank; subsequent rank skips by tie count.
    """
    ranks = {}
    for pos0, (idx, val) in enumerate(sorted_items):
        if pos0 == 0:
            ranks[idx] = 1
        elif val == sorted_items[pos0 - 1][1]:
            ranks[idx] = ranks[sorted_items[pos0 - 1][0]]
        else:
            ranks[idx] = pos0 + 1
    return ranks

def compute_rankings(phase1_list):
    """
    Compute ranking columns (idx 33-37) for all rows.
    Returns list of 5-element formatted-string lists (one per row).
    """
    n = len(phase1_list)

    # Classify into 金融 / 非金融 / 其他
    jin = [i for i, d in enumerate(phase1_list) if d['is_jinrong']]
    fei = [i for i, d in enumerate(phase1_list) if not d['is_jinrong'] and not d['is_other']]

    # ── 低估排序分 ──────────────────────────────────────────────────
    undervalue = [None] * n

    # 金融股: ascending PE TTM (lower is better), exclude PE <= 0
    jin_pe = [(i, phase1_list[i]['pe_ttm']) for i in jin
              if phase1_list[i]['pe_ttm'] is not None and phase1_list[i]['pe_ttm'] > 0]
    jin_pe.sort(key=lambda x: x[1])
    rk = _competition_rank(jin_pe)
    for i in jin:
        pe = phase1_list[i]['pe_ttm']
        if pe is not None and pe > 0:
            undervalue[i] = rk.get(i)

    # 非金融股: descending 股东收益率, exclude <= 0
    fei_sy = [(i, phase1_list[i]['shareholder_yield']) for i in fei
              if phase1_list[i]['shareholder_yield'] is not None
              and phase1_list[i]['shareholder_yield'] > 0]
    fei_sy.sort(key=lambda x: x[1], reverse=True)
    rk = _competition_rank(fei_sy)
    for i in fei:
        sy = phase1_list[i]['shareholder_yield']
        if sy is not None and sy > 0:
            undervalue[i] = rk.get(i)

    # ── 成长排序分 ──────────────────────────────────────────────────
    growth = [None] * n

    def _growth_key(d):
        return 0.0 if d['ttm_yoy'] is None else d['ttm_yoy']

    for queue in (jin, fei):
        items = [(i, _growth_key(phase1_list[i])) for i in queue]
        items.sort(key=lambda x: x[1], reverse=True)
        rk = _competition_rank(items)
        for i in queue:
            growth[i] = rk.get(i)

    # ── 质量排序分 ──────────────────────────────────────────────────
    quality = [None] * n

    # 金融股: descending TTMROE, exclude None
    jin_roe = [(i, phase1_list[i]['ttmroe']) for i in jin
               if phase1_list[i]['ttmroe'] is not None]
    jin_roe.sort(key=lambda x: x[1], reverse=True)
    rk = _competition_rank(jin_roe)
    for i in jin:
        if phase1_list[i]['ttmroe'] is not None:
            quality[i] = rk.get(i)

    # 非金融股: descending TTMROIC, exclude None
    fei_roic = [(i, phase1_list[i]['ttmroic']) for i in fei
                if phase1_list[i]['ttmroic'] is not None]
    fei_roic.sort(key=lambda x: x[1], reverse=True)
    rk = _competition_rank(fei_roic)
    for i in fei:
        if phase1_list[i]['ttmroic'] is not None:
            quality[i] = rk.get(i)

    # ── 股东回报排序分 ──────────────────────────────────────────────
    return_dist = [None] * n

    def _calc_return_dist(queue_indices):
        q_size = len(queue_indices)
        positive = [(i, phase1_list[i]['return_ratio']) for i in queue_indices
                    if phase1_list[i]['return_ratio'] is not None
                    and phase1_list[i]['return_ratio'] > 0]
        positive.sort(key=lambda x: x[1], reverse=True)
        rk = _competition_rank(positive)
        result = {}
        for i in queue_indices:
            rr = phase1_list[i]['return_ratio']
            if rr is not None and rr > 0:
                result[i] = rk.get(i, q_size)
            else:
                result[i] = q_size   # None/负 → 末位 = 队列总人数
        return result

    jin_rd = _calc_return_dist(jin)
    fei_rd = _calc_return_dist(fei)
    for i in jin: return_dist[i] = jin_rd.get(i)
    for i in fei: return_dist[i] = fei_rd.get(i)

    # ── 综合分数 ─────────────────────────────────────────────────────
    composite = [None] * n
    for i in range(n):
        u, g, q, r = undervalue[i], growth[i], quality[i], return_dist[i]
        if None not in (u, g, q, r):
            composite[i] = round(u * 0.4 + g * 0.2 + q * 0.2 + r * 0.2, 1)

    # ── 综合排名 ─────────────────────────────────────────────────────
    # 金融/非金融分队列，按综合分数升序排名（越低越好），其他/综合分数为空则不参与
    composite_rank = [None] * n
    for queue in (jin, fei):
        items = [(i, composite[i]) for i in queue if composite[i] is not None]
        items.sort(key=lambda x: x[1])
        rk = _competition_rank(items)
        for i in queue:
            if composite[i] is not None:
                composite_rank[i] = rk.get(i)

    def _fr(v):  return '--' if v is None else str(int(v))
    def _fc(v):  return '--' if v is None else str(v)

    return [
        [_fr(undervalue[i]), _fr(growth[i]), _fr(quality[i]),
         _fr(return_dist[i]), _fc(composite[i]), _fr(composite_rank[i])]
        for i in range(n)
    ]

# ---- Convert to row arrays ----
def get_val(obj, raw_key):
    if raw_key is None:
        return 0
    val = obj.get(raw_key, None)
    if val is None or val == '' or val != val:
        return '--'
    if isinstance(val, float):
        if val == int(val) and abs(val) < 1e13:
            return str(int(val))
        return str(round(val, 4))
    return str(val)

# Phase 1: per-row derived values (idx 10-32)
phase1_list = [compute_phase1(obj) for obj in obj_rows]
# Phase 2: cross-row ranking values (idx 33-37)
ranking_list = compute_rankings(phase1_list)

rows = []
for idx_row, obj in enumerate(obj_rows):
    code = clean_code(obj.get('股票代码', obj.get('code', '')))
    derived = phase1_list[idx_row]['vals'] + ranking_list[idx_row]
    derived_map = dict(zip(COMPUTED_COL_DEFS, derived))
    row = []
    for i, col in enumerate(all_cols):
        if i == 0:
            row.append(0)
        elif col['header'] == '股票代码':
            row.append(code)
        elif col['group'] == '计算指标':
            row.append(derived_map.get(col['header'], '--'))
        else:
            row.append(get_val(obj, col['raw_key']))
    rows.append(row)

# ---- Industry filter options ----
industries = sorted(set(r[9] for r in rows if r[9] and r[9] != '--'))
industry_opts = ''.join(f'<option value="{i}">{i}</option>' for i in industries)

# ---- Build COLS metadata for JS ----
cols_meta = []
for i, col in enumerate(all_cols):
    cols_meta.append({
        'idx': i,
        'name': col['header'].split('|')[0],
        'fullName': col['header'],
        'group': col['group'],
        'locked': col['locked'],
        'defaultVisible': col['defaultVisible'],
    })


# Period cols start after fixed(10) + computed cols
# metric_i * N_PERIODS + period_j; N_PERIODS = len(PERIOD_DATES)
PERIOD_START  = 10 + len(COMPUTED_COL_DEFS)
N_PERIODS     = len(PERIOD_DATES)
_PMETRICS     = [disp for _, disp in PERIOD_METRICS]
_PLABELS      = [label for _, label in PERIOD_DATES]   # most-recent-first
ROIC_START_IDX  = PERIOD_START + _PMETRICS.index('ROIC') * N_PERIODS
ROIC_END_IDX    = ROIC_START_IDX + N_PERIODS - 1
TTMROE_IDX_PY   = 10 + COMPUTED_COL_DEFS.index('TTMROE')
TTMROIC_IDX_PY  = 10 + COMPUTED_COL_DEFS.index('TTMROIC')

# ---- Write data.js (all build-time data + constants, loaded by index.html) ----

# 亿单位计算列名集合（用于生成 computed_yi_cols 索引列表）
COMPUTED_YI_NAMES = {
    'TTM归母净利润', '最新总现金', '最新流动资产', '最新总负债',
    '最新短期借款', '最新长期借款', '最新权益合计',
    'TTM经营现金流', 'TTM投资现金流', 'TTM资本支出', 'TTM融资现金流',
    'TTM股份回购', 'TTM支付股息', '预期25年度分红', '预期25股东回报',
    '净现金', '有息负债', 'TTMFCF',
}

# 筛选栏列规格（名称、单位）；isYi 由 COMPUTED_YI_NAMES 自动推算
_FILTER_SPECS = [
    ('TTM归母净利润',  '亿'),
    ('TTM净利同比',    '%'),
    ('TTMROE',         '%'),
    ('TTMROIC',        '%'),
    ('最新权益合计',   '亿'),
    ('TTM经营现金流',  '亿'),
    ('TTM投资现金流',  '亿'),
    ('TTM资本支出',    '亿'),
    ('TTM融资现金流',  '亿'),
    ('预期25年度分红', '亿'),
    ('预期25股东回报', '亿'),
    ('净现金',         '亿'),
    ('有息负债',       '亿'),
    ('TTMFCF',         '亿'),
    ('股东收益率',     '%'),
    ('股东回报分配率', '%'),
]

_data_bundle = {
    'headers': headers,
    'rows': rows,
    'cols': cols_meta,
    'periods': [label for _, label in PERIOD_DATES],
    'metrics': [disp for _, disp in PERIOD_METRICS],
    'roic_start': ROIC_START_IDX,
    'roic_end': ROIC_END_IDX,
    'ttmroe_idx': TTMROE_IDX_PY,
    'ttmroic_idx': TTMROIC_IDX_PY,
    'metrics_hidden': sorted(METRICS_HIDE_DEFAULT),
    'computed_hidden': sorted(COMPUTED_HIDE_DEFAULT),
    'fixed_hidden': sorted(FIXED_HIDE_DEFAULT),
    'industry_html': industry_opts,
    'row_count': len(rows),
    'computed_col_names': list(COMPUTED_COL_DEFS),
    'computed_yi_cols': [10 + i for i, n in enumerate(COMPUTED_COL_DEFS) if n in COMPUTED_YI_NAMES],
    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
    'filter_cols': [
        {'idx': 10 + COMPUTED_COL_DEFS.index(name), 'name': name, 'unit': unit, 'isYi': name in COMPUTED_YI_NAMES}
        for name, unit in _FILTER_SPECS
    ],
}
with open(os.path.join(BASE_DIR, 'data.js'), 'w', encoding='utf-8') as f:
    f.write('window.STOCK_DATA=' + json.dumps(_data_bundle, ensure_ascii=False, separators=(',', ':')) + ';')

# Update index.html to cache-bust data.js
index_path = os.path.join(BASE_DIR, 'index.html')
if os.path.exists(index_path):
    with open(index_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    timestamp = int(datetime.now().timestamp())
    new_html_content = re.sub(
        r'<script src="data\.js(?:\?t=\d+)?"></script>',
        f'<script src="data.js?t={timestamp}"></script>',
        html_content
    )
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(new_html_content)
    print(f"✅ index.html updated with cache-busting timestamp: ?t={timestamp}")

print(f"Columns: {len(headers)}, Rows: {len(rows)}")
print(f"N_PERIODS={N_PERIODS}, PERIOD_START={PERIOD_START}")
print(f"ROIC_START_IDX={ROIC_START_IDX}, ROIC_END_IDX={ROIC_END_IDX}")
