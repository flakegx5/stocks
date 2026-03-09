#!/usr/bin/env python3
"""Build self-contained HTML page for HK stock data (new object-format input)."""
import json, re, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'hk_stocks_data_new.json'), encoding='utf-8') as f:
    raw = json.load(f)

# ---- Column schema ----
# Fixed columns (order matters; idx 0 = 序号 computed)
FIXED_COLS = [
    # (display_name, raw_key_or_None)
    ('序号',           None),
    ('股票代码',        '股票代码'),
    ('股票简称',        '股票简称'),
    ('最新价(港元)',    '港股@最新价'),
    ('最新涨跌幅(%)',   '港股@最新涨跌幅'),
    ('总市值(港元)',    '港股@总市值[20260309]'),
    ('市盈率(pe,ttm)', '港股@市盈率(pe,ttm)[20260306]'),
    ('市净率(pb)',      '港股@市净率(pb)[20260309]'),
    ('总股本(股)',      '港股@总股本[20260309]'),
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
    'TTMROE',         # idx 18: %
    'TTMROIC',        # idx 19: %
    'TTM经营现金流',  # idx 20: 亿
    'TTM投资现金流',  # idx 21: 亿
    'TTM资本支出',    # idx 22: 亿
    'TTM融资现金流',  # idx 23: 亿
    'TTM股份回购',    # idx 24: 亿
    'TTM支付股息',    # idx 25: 亿
    '预期25年度分红', # idx 26: 亿
    '预期25股东回报', # idx 27: 亿
    '净现金',         # idx 28: 亿（金融股为空）
    '有息负债',       # idx 29: 亿（金融股为空）
    'TTMFCF',         # idx 30: 亿（金融股为空）
    '股东收益率',     # idx 31: %（金融股为空）
    '股东回报分配率', # idx 32: %
    '低估排序分',     # idx 33: 整数排名（越小越好）
    '成长排序分',     # idx 34: 整数排名（越小越好）
    '质量排序分',     # idx 35: 整数排名（越小越好）
    '股东回报排序分', # idx 36: 整数排名（越小越好）
    '综合分数',       # idx 37: 加权综合（越小越好）
]

# Period metrics hidden by default (replaced by computed "最新" cols)
METRICS_HIDE_DEFAULT = {
    '归母净利润', '净利润同比', '总现金', '流动资产', '总负债', '短期借款', '长期借款',
    'ROE', 'ROIC',
    '经营现金流', '投资现金流', '资本支出', '融资现金流', '股份回购', '支付股息',
    '年度分红',
}

# Computed columns hidden by default
COMPUTED_HIDE_DEFAULT = {
    'TTM股份回购', 'TTM支付股息', '预期25年度分红',
    '最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款',
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
        'defaultVisible': True,
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

obj_rows = raw['rows']

# Remove RMB counter stocks: 股票简称 ends with R after hyphen
obj_rows = [r for r in obj_rows
            if not (r.get('股票简称', '').endswith('R') and '-' in r.get('股票简称', ''))]

# Remove B-share duplicates: if both "X" and "X-B" exist, remove "X-B"
names = {r.get('股票简称', '') for r in obj_rows}
obj_rows = [r for r in obj_rows
            if not (r.get('股票简称', '').endswith('-B')
                    and r.get('股票简称', '')[:-2] in names)]

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
    return ind in JINRONG_SET or (ind == '综合企业' and '中信股份' in name)

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

    # 净现金: 总现金 - 短期借款 - 长期借款（缺失数据视为0，全部缺失才为空）
    if is_jrong:
        v_net_cash = None
    else:
        _ch, _sd, _ld = gv(CH), gv(SD), gv(LD)
        if _ch is None and _sd is None and _ld is None:
            v_net_cash = None
        else:
            v_net_cash = (_ch or 0) - (_sd or 0) - (_ld or 0)

    # 有息负债: 短期借款 + 长期借款（缺失数据视为0，全部缺失才为空）
    if is_jrong:
        v_interest_debt = None
    else:
        _sd2, _ld2 = gv(SD), gv(LD)
        if _sd2 is None and _ld2 is None:
            v_interest_debt = None
        else:
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
            mkt_cap = float(obj.get('港股@总市值[20260309]') or 0) or None
        except:
            mkt_cap = None
        if v_ttmfcf is not None and mkt_cap is not None and v_net_cash is not None:
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

    # PE TTM (for 低估排序分 金融股)
    try:
        v_pe_ttm = float(obj.get('港股@市盈率(pe,ttm)[20260306]') or 0) or None
    except:
        v_pe_ttm = None

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
            _fmt(v_ttmroe),                       # 18: TTMROE
            _fmt(v_ttmroic),                      # 19: TTMROIC
            _fmt(v_ocf),                          # 20: TTM经营现金流
            _fmt(v_icf),                          # 21: TTM投资现金流 (可正可负)
            _fmt(v_cap),                          # 22: TTM资本支出 (取反，>0则空)
            _fmt(ttm_yi(FCF_CF)),                 # 23: TTM融资现金流
            _fmt(neg_only(ttm_yi(BUY))),          # 24: TTM股份回购 (>0则空)
            _fmt(neg_only(ttm_yi(DIV))),          # 25: TTM支付股息 (>0则空)
            _fmt(v_exp_div),                      # 26: 预期25年度分红
            _fmt(v_exp_return),                   # 27: 预期25股东回报
            _fmt(v_net_cash),                     # 28: 净现金
            _fmt(v_interest_debt),                # 29: 有息负债
            _fmt(v_ttmfcf),                       # 30: TTMFCF
            _fmt(v_shareholder_yield),            # 31: 股东收益率 (%)
            _fmt(v_return_ratio),                 # 32: 股东回报分配率 (%)
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

    def _fr(v):  return '--' if v is None else str(int(v))
    def _fc(v):  return '--' if v is None else str(v)

    return [
        [_fr(undervalue[i]), _fr(growth[i]), _fr(quality[i]),
         _fr(return_dist[i]), _fc(composite[i])]
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

# ---- Serialize ----
data_js = json.dumps({'headers': headers, 'rows': rows}, ensure_ascii=False, separators=(',', ':'))
cols_meta_js = json.dumps(cols_meta, ensure_ascii=False, separators=(',', ':'))
periods_js = json.dumps([label for _, label in PERIOD_DATES], ensure_ascii=False)
metrics_js = json.dumps([disp for _, disp in PERIOD_METRICS], ensure_ascii=False)

# Period cols start after fixed(10) + computed(28) = idx 38
# metric_i * 11 + period_j; 2024年报 = period 3
PERIOD_START = 10 + len(COMPUTED_COL_DEFS)   # = 38 (10 fixed + 28 computed)
ROE_2024_IDX    = PERIOD_START + 7 * 11 + 3  # = 100
PROFIT_2024_IDX = PERIOD_START + 0 * 11 + 3  # = 23
CF_2024_IDX     = PERIOD_START + 9 * 11 + 3  # = 122
ROIC_START_IDX  = PERIOD_START + 8 * 11      # = 108 (first ROIC period col)
ROIC_END_IDX    = ROIC_START_IDX + 10        # = 118 (last ROIC period col, inclusive)
TTMROE_IDX_PY   = 10 + COMPUTED_COL_DEFS.index('TTMROE')   # = 18
TTMROIC_IDX_PY  = 10 + COMPUTED_COL_DEFS.index('TTMROIC')  # = 19

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>港股数据 · 市值50亿+</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px; background: #f5f6f8; color: #1a1a1a; }}

/* Header */
.page-header {{ background: #1a2332; color: #fff; padding: 14px 20px; display: flex;
  align-items: center; gap: 16px; position: sticky; top: 0; z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,.3); }}
.page-header h1 {{ margin: 0; font-size: 17px; font-weight: 600; }}
.page-header .subtitle {{ font-size: 11px; color: #9ab; }}

/* Controls */
.controls {{ background: #fff; border-bottom: 1px solid #e0e3ea; padding: 8px 20px;
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  position: sticky; top: 49px; z-index: 99; }}
.controls input[type=search], .controls select {{
  height: 30px; border: 1px solid #d0d3da; border-radius: 4px; padding: 0 10px;
  font-size: 12px; outline: none; background: #fafbfc; }}
.controls input[type=search] {{ width: 180px; }}
.controls input[type=search]:focus, .controls select:focus {{
  border-color: #4a7fff; box-shadow: 0 0 0 2px rgba(74,127,255,.15); }}
.controls select {{ max-width: 140px; }}
.btn {{ height: 30px; padding: 0 12px; border: 1px solid #d0d3da; border-radius: 4px;
  background: #fff; cursor: pointer; font-size: 12px; color: #444; white-space: nowrap; }}
.btn:hover {{ background: #f0f2f5; }}
.sep {{ color: #ccc; font-size: 18px; line-height: 1; }}

/* Column picker */
.col-picker-wrap {{ position: relative; }}
#colPickerBtn {{ background: #fff; }}
#colPickerBtn.active {{ background: #1a2332; color: #fff; border-color: #1a2332; }}
.col-picker {{
  display: none; position: fixed; top: 0; right: 0; width: 420px; height: 100vh;
  background: #fff; border-left: 1px solid #d0d3da; z-index: 200;
  box-shadow: -4px 0 20px rgba(0,0,0,.15); flex-direction: column;
  overflow: hidden;
}}
.col-picker.open {{ display: flex; }}
.cp-header {{ background: #1a2332; color: #fff; padding: 14px 16px;
  display: flex; justify-content: space-between; align-items: center;
  font-weight: 600; font-size: 14px; flex-shrink: 0; }}
.cp-close {{ background: none; border: none; color: #cde; cursor: pointer;
  font-size: 18px; line-height: 1; padding: 4px; }}
.cp-close:hover {{ color: #fff; }}
.cp-body {{ flex: 1; overflow-y: auto; padding: 8px 0; }}
.cp-group {{ border-bottom: 1px solid #edf0f5; }}
.cp-group-hdr {{ background: #f5f7fa; padding: 8px 16px; display: flex;
  align-items: center; gap: 8px; position: sticky; top: 0; z-index: 1; }}
.cp-group-name {{ font-weight: 600; font-size: 12px; color: #1a2332; flex: 1; }}
.cp-group-btn {{ font-size: 11px; color: #4a7fff; cursor: pointer; border: none;
  background: none; padding: 2px 6px; }}
.cp-group-btn:hover {{ text-decoration: underline; }}
.cp-cols {{ display: flex; flex-wrap: wrap; gap: 2px; padding: 6px 12px 10px; }}
.cp-col {{ display: flex; align-items: center; gap: 5px; cursor: pointer;
  font-size: 12px; color: #333; padding: 3px 6px; border-radius: 3px;
  white-space: nowrap; min-width: 120px; }}
.cp-col:hover {{ background: #f0f4ff; }}
.cp-col input {{ cursor: pointer; margin: 0; flex-shrink: 0; }}
.cp-col.locked {{ color: #aaa; cursor: default; }}
.cp-overlay {{ display: none; position: fixed; inset: 0; z-index: 199; }}
.cp-overlay.open {{ display: block; }}

/* Summary */
.summary-bar {{ background: #eef1f7; border-bottom: 1px solid #d8dbe5;
  padding: 5px 20px; font-size: 12px; color: #555; display: flex; gap: 20px; flex-wrap: wrap; }}
.summary-bar strong {{ color: #1a2332; }}

/* Table wrapper */
.table-wrap {{ overflow: auto; height: calc(100vh - 148px); }}

/* Table */
table {{ border-collapse: separate; border-spacing: 0; width: max-content; min-width: 100%; }}
thead th {{
  position: sticky; top: 0; z-index: 10;
  background: #1e2d42; color: #dde4ef;
  padding: 0 8px; height: 44px; white-space: nowrap;
  font-weight: 500; font-size: 12px; border-right: 1px solid #2a3d58;
  cursor: pointer; user-select: none; vertical-align: middle; text-align: center;
}}
thead th:hover {{ background: #253650; }}
thead th.sort-asc::after {{ content: ' ▲'; color: #6af; font-size: 10px; }}
thead th.sort-desc::after {{ content: ' ▼'; color: #6af; font-size: 10px; }}
thead th .th-metric {{ display: block; font-weight: 600; }}
thead th .th-unit  {{ display: block; font-size: 9px; color: #7bc; margin-top: 1px; font-weight: 400; }}
thead th .th-date  {{ display: block; font-size: 10px; color: #8ab; margin-top: 1px; }}

/* Sticky cols in header */
thead th:nth-child(1) {{ position: sticky; left: 0; z-index: 20; min-width: 48px; max-width: 48px; }}
thead th:nth-child(2) {{ position: sticky; left: 48px; z-index: 20; min-width: 80px; max-width: 80px; }}
thead th:nth-child(3) {{ position: sticky; left: 128px; z-index: 20; min-width: 110px; max-width: 110px; }}

/* Column group colors — by metric type */
th[data-group="基本信息"]   {{ background: #1a3055; }}
th[data-group="归母净利润"] {{ background: #1e3d28; }}
th[data-group="净利润同比"] {{ background: #1a3530; }}
th[data-group="总现金"]     {{ background: #1e2d3a; }}
th[data-group="流动资产"]   {{ background: #2d2035; }}
th[data-group="总负债"]     {{ background: #28203a; }}
th[data-group="短期借款"]   {{ background: #221f3a; }}
th[data-group="长期借款"]   {{ background: #1c2038; }}
th[data-group="ROE"]        {{ background: #2a1e20; }}
th[data-group="ROIC"]       {{ background: #282020; }}
th[data-group="经营现金流"] {{ background: #261e22; }}
th[data-group="投资现金流"] {{ background: #241e24; }}
th[data-group="资本支出"]   {{ background: #1e2438; }}
th[data-group="融资现金流"] {{ background: #22263a; }}
th[data-group="年度分红"]   {{ background: #2a2018; }}
th[data-group="股份回购"]   {{ background: #28221a; }}
th[data-group="支付股息"]   {{ background: #261e1c; }}

/* Body */
tbody tr:nth-child(even) {{ background: #f8f9fb; }}
tbody tr:hover td {{ background: #e8eef8 !important; }}
td {{
  padding: 0 8px; height: 32px; white-space: nowrap;
  border-right: 1px solid #e8eaef; border-bottom: 1px solid #e8eaef;
  text-align: right; vertical-align: middle; font-size: 12px;
}}
td:nth-child(1), td:nth-child(2), td:nth-child(3) {{ text-align: left; }}
td.neg {{ color: #d04020; }}
td.pos {{ color: #206840; }}

/* Sticky body cells */
td:nth-child(1) {{
  position: sticky; left: 0; z-index: 5; background: inherit;
  min-width: 48px; max-width: 48px; text-align: center; color: #888;
  border-right: 2px solid #e0e3ea;
}}
td:nth-child(2) {{
  position: sticky; left: 48px; z-index: 5; background: inherit;
  min-width: 80px; max-width: 80px; font-family: monospace; color: #555;
}}
td:nth-child(3) {{
  position: sticky; left: 128px; z-index: 5; background: inherit;
  min-width: 110px; max-width: 110px; font-weight: 500; color: #1a2332;
  border-right: 2px solid #c0c8d8;
}}
tbody tr:nth-child(even) td:nth-child(1),
tbody tr:nth-child(even) td:nth-child(2),
tbody tr:nth-child(even) td:nth-child(3) {{ background: #f8f9fb; }}
tbody tr:nth-child(odd) td:nth-child(1),
tbody tr:nth-child(odd) td:nth-child(2),
tbody tr:nth-child(odd) td:nth-child(3) {{ background: #fff; }}

/* Export button */
.btn-export {{ background: #1a5c30; color: #fff; border-color: #1a5c30; }}
.btn-export:hover {{ background: #236b3a; }}
/* Filter bar */
.filter-bar {{ background: #eef3ff; border-bottom: 1px solid #c8d4f0;
  padding: 8px 20px; display: none; flex-wrap: wrap; gap: 12px; align-items: center; }}
.filter-bar.open {{ display: flex; }}
.filter-item {{ display: flex; align-items: center; gap: 5px; font-size: 12px; }}
.filter-item label {{ color: #334; white-space: nowrap; font-weight: 500; }}
.filter-item select {{ height: 26px; border: 1px solid #b0c0e0; border-radius: 4px;
  padding: 0 4px; font-size: 12px; background: #fff; }}
.filter-item input[type=number] {{ width: 72px; height: 26px; border: 1px solid #b0c0e0;
  border-radius: 4px; padding: 0 6px; font-size: 12px; }}
.filter-item .unit {{ color: #778; font-size: 11px; }}
.filter-active {{ color: #e05020; font-weight: 600; }}
#clearFiltersBtn {{ color: #e05020; border-color: #e05020; }}
</style>
</head>
<body>

<div class="page-header">
  <h1>港股数据</h1>
  <span class="subtitle">市值≥50亿港元 · 共{len(rows)}只（已去除人民币柜台/B股重复）· 数据来源：问财</span>
</div>

<div class="controls">
  <input type="search" id="searchBox" placeholder="搜索代码/名称…">
  <select id="stockTypeFilter">
    <option value="">所有类型</option>
    <option value="金融股">金融股</option>
    <option value="非金融股">非金融股</option>
    <option value="其他">其他</option>
  </select>
  <select id="industryFilter">
    <option value="">所有行业</option>
    {industry_opts}
  </select>
  <span class="sep">|</span>
  <div class="col-picker-wrap">
    <button class="btn" id="colPickerBtn">列设置 ▼</button>
  </div>
  <span class="sep">|</span>
  <button class="btn" id="clearSort">清除排序</button>
  <button class="btn" id="resetView">重置视图</button>
  <span class="sep">|</span>
  <button class="btn" id="filterToggleBtn">筛选 ▼</button>
  <span class="sep">|</span>
  <button class="btn btn-export" id="exportBtn">导出 Excel</button>
</div>

<div class="filter-bar" id="filterBar"></div>

<div class="summary-bar">
  <span>显示 <strong id="sRowCount">-</strong> 只</span>
  <span>总市值 <strong id="sTotalMkt">-</strong></span>
  <span>平均PE(TTM) <strong id="sAvgPE">-</strong></span>
  <span>平均PB <strong id="sAvgPB">-</strong></span>
  <span>平均ROE(2024年报) <strong id="sAvgROE">-</strong></span>
</div>

<!-- Column picker side panel -->
<div class="cp-overlay" id="cpOverlay"></div>
<div class="col-picker" id="colPicker">
  <div class="cp-header">
    <span>列设置</span>
    <button class="cp-close" id="cpClose">✕</button>
  </div>
  <div class="cp-body" id="cpBody"></div>
</div>

<div class="table-wrap" id="tableWrap">
  <table id="mainTable">
    <thead id="tableHead"></thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<script src="https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js"></script>
<script>
const DATA = {data_js};
const COLS = {cols_meta_js};
const PERIODS = {periods_js};
const METRICS = {metrics_js};
const ROE_IDX = {ROE_2024_IDX};
const PROFIT_IDX = {PROFIT_2024_IDX};
const CF_IDX = {CF_2024_IDX};
const ROIC_START   = {ROIC_START_IDX};   // first ROIC period col
const ROIC_END     = {ROIC_END_IDX};     // last  ROIC period col (inclusive, 11 periods)
const TTMROE_IDX   = {TTMROE_IDX_PY};   // computed TTMROE col
const TTMROIC_IDX  = {TTMROIC_IDX_PY};  // computed TTMROIC col

// Percentage-type metrics — do NOT convert to 亿
const PCT_METRICS = new Set(['净利润同比', 'ROE', 'ROIC']);

// Computed 亿 cols: TTM净利(11), 现金(13-17), 现金流(20-27), 净现金/有息负债/FCF(28-30)
const COMPUTED_YI_COLS = new Set([11,13,14,15,16,17,20,21,22,23,24,25,26,27,28,29,30]);
const COMPUTED_COL_NAMES = [
  '最新财报季','TTM归母净利润','TTM净利同比',
  '最新总现金','最新流动资产','最新总负债','最新短期借款','最新长期借款',
  'TTMROE','TTMROIC',
  'TTM经营现金流','TTM投资现金流','TTM资本支出','TTM融资现金流','TTM股份回购','TTM支付股息',
  '预期25年度分红','预期25股东回报',
  '净现金','有息负债','TTMFCF','股东收益率','股东回报分配率',
  '低估排序分','成长排序分','质量排序分','股东回报排序分','综合分数',
];
const FILTER_COLS = [
  {{idx:11, name:'TTM归母净利润',  unit:'亿', isYi:true}},
  {{idx:12, name:'TTM净利同比',    unit:'%',  isYi:false}},
  {{idx:TTMROE_IDX,  name:'TTMROE',  unit:'%', isYi:false}},
  {{idx:TTMROIC_IDX, name:'TTMROIC', unit:'%', isYi:false}},
  {{idx:20, name:'TTM经营现金流',  unit:'亿', isYi:true}},
  {{idx:21, name:'TTM投资现金流',  unit:'亿', isYi:true}},
  {{idx:22, name:'TTM资本支出',    unit:'亿', isYi:true}},
  {{idx:23, name:'TTM融资现金流',  unit:'亿', isYi:true}},
  {{idx:26, name:'预期25年度分红', unit:'亿', isYi:true}},
  {{idx:27, name:'预期25股东回报', unit:'亿', isYi:true}},
  {{idx:28, name:'净现金',         unit:'亿', isYi:true}},
  {{idx:29, name:'有息负债',       unit:'亿', isYi:true}},
  {{idx:30, name:'TTMFCF',        unit:'亿', isYi:true}},
  {{idx:31, name:'股东收益率',     unit:'%',  isYi:false}},
  {{idx:32, name:'股东回报分配率', unit:'%',  isYi:false}},
  {{idx:33, name:'低估排序分',     unit:'',   isYi:false}},
  {{idx:34, name:'成长排序分',     unit:'',   isYi:false}},
  {{idx:35, name:'质量排序分',     unit:'',   isYi:false}},
  {{idx:36, name:'股东回报排序分', unit:'',   isYi:false}},
  {{idx:37, name:'综合分数',       unit:'',   isYi:false}},
];

// ---- Utility ----
function parseNum(s) {{
  if (s === null || s === undefined || s === '--') return null;
  s = String(s).replace(/,/g, '');
  let m = 1;
  if (s.endsWith('亿')) {{ m = 1e8; s = s.slice(0, -1); }}
  else if (s.endsWith('万')) {{ m = 1e4; s = s.slice(0, -1); }}
  const v = parseFloat(s);
  return isNaN(v) ? null : v * m;
}}

function fmtYi(n) {{
  // Pure number in 亿 units — no unit suffix (unit shown in column header)
  const yi = n / 1e8;
  if (Math.abs(yi) >= 1) return yi.toFixed(1);
  return yi.toFixed(2);
}}

function getColUnit(col) {{
  if (col.idx === 5) return '亿港元';
  if (col.idx === 8) return '亿股';
  if (COMPUTED_YI_COLS.has(col.idx)) return '亿';
  if (col.idx === 12 || col.idx === TTMROE_IDX || col.idx === TTMROIC_IDX
      || col.idx === 31 || col.idx === 32) return '%';
  if (col.group !== '基本信息' && col.group !== '计算指标' && !PCT_METRICS.has(col.group)) return '亿';
  return '';
}}

function fmtCell(val, col) {{
  if (val === '--' || val === null || val === undefined) return '--';
  if (col.idx === 6 || col.idx === 7) {{  // PE / PB
    const n = parseNum(String(val));
    return n === null ? val : n.toFixed(1);
  }}
  if (col.idx === 10) return val;  // 最新财报季: text as-is
  if (col.idx === 12 || col.idx === TTMROE_IDX || col.idx === TTMROIC_IDX
      || col.idx === 31 || col.idx === 32) {{  // % cols: 1 decimal
    const n = parseNum(String(val));
    return n === null ? val : n.toFixed(1);
  }}
  if (!getColUnit(col)) return val;  // ranking/composite: return as-is
  const n = parseNum(String(val));
  if (n === null) return val;
  return fmtYi(n);
}}

function fmtMktCap(v) {{
  if (v === null) return '--';
  return fmtYi(v) + '亿';   // summary bar keeps unit
}}

function fmtNum(v) {{
  if (v === null || v === undefined) return '--';
  return fmtYi(v) + '亿';   // summary bar keeps unit
}}

// ---- Stock type classification ----
// 金融股: 行业 in {{保险,其他金融,银行}} OR (行业==综合企业 AND 名称含中信集团)
// 非金融股: 非金融 AND 至少一期有ROIC数据
// 其他: 其余

function isJinRong(row) {{
  const ind = String(row[9]);
  if (ind === '保险' || ind === '其他金融' || ind === '银行') return true;
  if (ind === '综合企业' && String(row[2]).includes('中信股份')) return true;
  return false;
}}

function hasAnyROIC(row) {{
  for (let i = ROIC_START; i <= ROIC_END; i++) {{
    const v = row[i];
    if (v !== '--' && v !== null && v !== undefined && v !== '') return true;
  }}
  return false;
}}

function getStockType(row) {{
  if (isJinRong(row)) return '金融股';
  if (hasAnyROIC(row)) return '非金融股';
  return '其他';
}}

// ---- State ----
const METRICS_DEFAULT_HIDDEN   = new Set({json.dumps(sorted(METRICS_HIDE_DEFAULT),   ensure_ascii=False)});
const COMPUTED_DEFAULT_HIDDEN  = new Set({json.dumps(sorted(COMPUTED_HIDE_DEFAULT),  ensure_ascii=False)});
let sortCol = -1, sortDir = 'asc';
let visiblePeriods = new Set(PERIODS);
let visibleMetrics = new Set(METRICS.filter(m => !METRICS_DEFAULT_HIDDEN.has(m)));
let visibleComputedCols = new Set(COMPUTED_COL_NAMES.filter(n => !COMPUTED_DEFAULT_HIDDEN.has(n)));
let searchText = '';
let filterIndustry = '';
let filterStockType = '';
let filters = {{}};   // {{colIdx: {{op, val}}}}
let displayIndices = [];

// ---- Column picker (2-D: periods × metrics) ----
function buildColPicker() {{
  const body = document.getElementById('cpBody');

  function makeSection(title, items, activeSet) {{
    const allChk = items.every(v => activeSet.has(v));
    let html = `<div class="cp-group">
      <div class="cp-group-hdr">
        <span class="cp-group-name">${{title}}</span>
        <button class="cp-group-btn" data-sec="${{title}}" data-a="all">全选</button>
        <button class="cp-group-btn" data-sec="${{title}}" data-a="none">全不选</button>
      </div><div class="cp-cols">`;
    items.forEach(item => {{
      const chk = activeSet.has(item) ? 'checked' : '';
      html += `<label class="cp-col"><input type="checkbox" data-sec="${{title}}" data-val="${{item}}" ${{chk}}> ${{item}}</label>`;
    }});
    html += `</div></div>`;
    return html;
  }}

  // Computed cols section (individual checkboxes)
  function makeComputedSection() {{
    let h = `<div class="cp-group"><div class="cp-group-hdr">
      <span class="cp-group-name">计算指标</span>
      <button class="cp-group-btn" data-sec="computed" data-a="all">全选</button>
      <button class="cp-group-btn" data-sec="computed" data-a="none">全不选</button>
      </div><div class="cp-cols">`;
    COMPUTED_COL_NAMES.forEach(n => {{
      h += `<label class="cp-col"><input type="checkbox" data-sec="computed" data-val="${{n}}" ${{visibleComputedCols.has(n)?'checked':''}}> ${{n}}</label>`;
    }});
    return h + `</div></div>`;
  }}

  body.innerHTML =
    makeComputedSection() +
    makeSection('财报周期', PERIODS, visiblePeriods) +
    makeSection('财务指标', METRICS, visibleMetrics);

  body.querySelectorAll('input[data-sec]').forEach(cb => {{
    cb.addEventListener('change', e => {{
      const sec = e.target.dataset.sec;
      const set = sec === 'computed' ? visibleComputedCols
                : sec === '财报周期' ? visiblePeriods : visibleMetrics;
      if (e.target.checked) set.add(e.target.dataset.val);
      else set.delete(e.target.dataset.val);
      buildHeader(); buildBody();
    }});
  }});

  body.querySelectorAll('.cp-group-btn').forEach(btn => {{
    btn.addEventListener('click', e => {{
      const sec = e.target.dataset.sec;
      const set  = sec === 'computed' ? visibleComputedCols
                 : sec === '财报周期' ? visiblePeriods : visibleMetrics;
      const items = sec === 'computed' ? COMPUTED_COL_NAMES
                  : sec === '财报周期' ? PERIODS : METRICS;
      if (e.target.dataset.a === 'all') items.forEach(v => set.add(v));
      else set.clear();
      buildColPicker(); buildHeader(); buildBody();
    }});
  }});
}}

function openColPicker() {{
  document.getElementById('colPicker').classList.add('open');
  document.getElementById('cpOverlay').classList.add('open');
  document.getElementById('colPickerBtn').classList.add('active');
  buildColPicker();
}}

function closeColPicker() {{
  document.getElementById('colPicker').classList.remove('open');
  document.getElementById('cpOverlay').classList.remove('open');
  document.getElementById('colPickerBtn').classList.remove('active');
}}

document.getElementById('colPickerBtn').addEventListener('click', () => {{
  if (document.getElementById('colPicker').classList.contains('open')) closeColPicker();
  else openColPicker();
}});
document.getElementById('cpClose').addEventListener('click', closeColPicker);
document.getElementById('cpOverlay').addEventListener('click', closeColPicker);

// ---- Visible col defs ----
function getVisibleColDefs() {{
  return COLS.filter(col => {{
    if (col.locked || col.group === '基本信息') return true;
    if (col.group === '计算指标') return visibleComputedCols.has(col.name);
    const pipe = col.fullName.indexOf('|');
    const period = col.fullName.slice(pipe + 1);
    return visibleMetrics.has(col.group) && visiblePeriods.has(period);
  }});
}}

// ---- Build header ----
function buildHeader() {{
  const thead = document.getElementById('tableHead');
  const tr = document.createElement('tr');
  getVisibleColDefs().forEach(col => {{
    const th = document.createElement('th');
    const pipe = col.fullName.indexOf('|');
    let metric, date;
    if (pipe >= 0) {{
      metric = col.fullName.slice(0, pipe);
      date = col.fullName.slice(pipe + 1);
    }} else {{
      metric = col.name; date = '';
    }}
    const unit = getColUnit(col);
    const unitHtml = unit ? `<span class="th-unit">${{unit}}</span>` : '';
    th.innerHTML = `<span class="th-metric">${{metric}}</span>${{unitHtml}}${{date ? `<span class="th-date">${{date}}</span>` : ''}}`;
    th.dataset.colidx = col.idx;
    th.dataset.group = col.group;
    if (String(sortCol) === String(col.idx)) {{
      th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
    }}
    th.addEventListener('click', () => onSortClick(col.idx));
    tr.appendChild(th);
  }});
  thead.innerHTML = '';
  thead.appendChild(tr);
}}

// ---- Build body ----
function buildBody() {{
  const colDefs = getVisibleColDefs();
  let html = '';
  displayIndices.forEach((ri, rowPos) => {{
    const row = DATA.rows[ri];
    html += `<tr>`;
    colDefs.forEach((col, pos) => {{
      const rawVal = col.idx === 0 ? (rowPos + 1) : (row[col.idx] ?? '--');
      let cls = '';
      if (pos >= 3) {{
        const n = parseNum(String(rawVal));
        if (n !== null && n < 0) cls = ' class="neg"';
        else if (n !== null && n > 0 && col.idx >= 4) cls = ' class="pos"';
      }}
      const displayVal = col.idx === 0 ? rawVal : fmtCell(rawVal, col);
      html += `<td${{cls}}>${{displayVal}}</td>`;
    }});
    html += '</tr>';
  }});
  document.getElementById('tableBody').innerHTML = html;
}}

// ---- Filter & Sort ----
function applyFilters() {{
  let indices = DATA.rows.map((_, i) => i);
  if (filterStockType) indices = indices.filter(i => getStockType(DATA.rows[i]) === filterStockType);
  if (filterIndustry) indices = indices.filter(i => DATA.rows[i][9] === filterIndustry);
  if (searchText) {{
    const t = searchText.toLowerCase();
    indices = indices.filter(i =>
      String(DATA.rows[i][1]).toLowerCase().includes(t) ||
      String(DATA.rows[i][2]).toLowerCase().includes(t)
    );
  }}
  // Computed column filters
  Object.entries(filters).forEach(([idx, f]) => {{
    const ci = parseInt(idx);
    const fc = FILTER_COLS.find(c => c.idx === ci);
    const threshold = fc?.isYi ? f.val * 1e8 : f.val;
    indices = indices.filter(i => {{
      const v = parseNum(String(DATA.rows[i][ci]));
      if (v === null) return false;
      if (f.op === '>')  return v > threshold;
      if (f.op === '>=') return v >= threshold;
      if (f.op === '<')  return v < threshold;
      if (f.op === '<=') return v <= threshold;
      return true;
    }});
  }});
  if (sortCol !== -1) {{
    indices.sort((a, b) => {{
      const ci = parseInt(sortCol);
      const va = parseNum(String(DATA.rows[a][ci]));
      const vb = parseNum(String(DATA.rows[b][ci]));
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return sortDir === 'asc' ? va - vb : vb - va;
    }});
  }} else {{
    // Default: sort by stock code ascending
    indices.sort((a, b) => String(DATA.rows[a][1]).localeCompare(String(DATA.rows[b][1])));
  }}
  displayIndices = indices;
}}

function onSortClick(colidx) {{
  const ci = String(colidx);
  if (String(sortCol) === ci) {{
    sortDir = sortDir === 'asc' ? 'desc' : 'asc';
  }} else {{
    sortCol = colidx;
    sortDir = 'desc';
  }}
  applyFilters();
  buildHeader();
  buildBody();
  updateSummary();
}}

// ---- Summary ----
function updateSummary() {{
  document.getElementById('sRowCount').textContent = displayIndices.length;
  let totalMkt = 0, totalPE = 0, cPE = 0, totalPB = 0, cPB = 0, totalROE = 0, cROE = 0;
  displayIndices.forEach(i => {{
    const r = DATA.rows[i];
    const mkt = parseNum(r[5]); if (mkt && mkt > 0) totalMkt += mkt;
    const pe = parseNum(r[6]);  if (pe && pe > 0 && pe < 1000) {{ totalPE += pe; cPE++; }}
    const pb = parseNum(r[7]);  if (pb && pb > 0 && pb < 100)  {{ totalPB += pb; cPB++; }}
    const roe = parseNum(r[ROE_IDX]); if (roe !== null) {{ totalROE += roe; cROE++; }}
  }});
  document.getElementById('sTotalMkt').textContent = fmtMktCap(totalMkt || null);
  document.getElementById('sAvgPE').textContent = cPE ? (totalPE/cPE).toFixed(1)+'x' : '--';
  document.getElementById('sAvgPB').textContent = cPB ? (totalPB/cPB).toFixed(2)+'x' : '--';
  document.getElementById('sAvgROE').textContent = cROE ? (totalROE/cROE).toFixed(1)+'%' : '--';
}}

// ---- Export Excel ----
function exportExcel() {{
  const colDefs = getVisibleColDefs();

  // Header row: "指标 (单位) [周期]"
  const headerRow = colDefs.map(col => {{
    const pipe = col.fullName.indexOf('|');
    const name = pipe >= 0 ? col.fullName.slice(0, pipe) : col.name;
    const date = pipe >= 0 ? col.fullName.slice(pipe + 1) : '';
    const unit = getColUnit(col);
    return name + (unit ? ` (${{unit}})` : '') + (date ? ` [${{date}}]` : '');
  }});

  // Data rows: numbers as numeric, text as string
  const dataRows = displayIndices.map((ri, rowPos) => {{
    const row = DATA.rows[ri];
    return colDefs.map((col, pos) => {{
      if (col.idx === 0) return rowPos + 1;
      const rawVal = row[col.idx] ?? '--';
      const display = fmtCell(rawVal, col);
      if (display === '--' || display === '') return '';
      const n = parseFloat(display);
      return isNaN(n) ? display : n;
    }});
  }});

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet([headerRow, ...dataRows]);
  XLSX.utils.book_append_sheet(wb, ws, '港股数据');
  XLSX.writeFile(wb, '港股数据.xlsx');
}}

// ---- Filter bar ----
function buildFilterBar() {{
  const bar = document.getElementById('filterBar');
  let html = '';
  FILTER_COLS.forEach(fc => {{
    const f = filters[fc.idx] || {{}};
    html += `<div class="filter-item">
      <label>${{fc.name}}</label>
      <select data-fidx="${{fc.idx}}" class="f-op">
        <option value="" ${{!f.op ? 'selected' : ''}}>—</option>
        <option value=">"  ${{f.op === '>'  ? 'selected' : ''}}>&gt;</option>
        <option value=">=" ${{f.op === '>=' ? 'selected' : ''}}>≥</option>
        <option value="<"  ${{f.op === '<'  ? 'selected' : ''}}>&lt;</option>
        <option value="<=" ${{f.op === '<=' ? 'selected' : ''}}>≤</option>
      </select>
      <input type="number" data-fidx="${{fc.idx}}" class="f-val"
             value="${{f.val !== undefined ? f.val : ''}}" placeholder="0" step="any">
      <span class="unit">${{fc.unit}}</span>
    </div>`;
  }});
  html += `<button class="btn" id="clearFiltersBtn">清除筛选</button>`;
  bar.innerHTML = html;

  bar.querySelectorAll('.f-op').forEach(sel => {{
    sel.addEventListener('change', () => updateFilter(parseInt(sel.dataset.fidx)));
  }});
  bar.querySelectorAll('.f-val').forEach(inp => {{
    inp.addEventListener('input', () => updateFilter(parseInt(inp.dataset.fidx)));
  }});
  bar.querySelector('#clearFiltersBtn').addEventListener('click', clearFilters);
}}

function updateFilter(idx) {{
  const bar = document.getElementById('filterBar');
  const opSel = bar.querySelector(`.f-op[data-fidx="${{idx}}"]`);
  const valInp = bar.querySelector(`.f-val[data-fidx="${{idx}}"]`);
  const op = opSel.value;
  const val = parseFloat(valInp.value);
  if (op && !isNaN(val)) {{
    filters[idx] = {{op, val}};
  }} else {{
    delete filters[idx];
  }}
  updateFilterToggleStyle();
  render();
}}

function clearFilters() {{
  filters = {{}};
  updateFilterToggleStyle();
  buildFilterBar();
  render();
}}

function updateFilterToggleStyle() {{
  const btn = document.getElementById('filterToggleBtn');
  const hasActive = Object.keys(filters).length > 0;
  btn.classList.toggle('filter-active', hasActive);
  btn.textContent = hasActive ? '筛选 ●' : '筛选 ▼';
}}

function render() {{
  applyFilters();
  buildHeader();
  buildBody();
  updateSummary();
}}

// ---- Events ----
document.getElementById('searchBox').addEventListener('input', e => {{
  searchText = e.target.value.trim();
  render();
}});

document.getElementById('stockTypeFilter').addEventListener('change', e => {{
  filterStockType = e.target.value;
  render();
}});

document.getElementById('industryFilter').addEventListener('change', e => {{
  filterIndustry = e.target.value;
  render();
}});

document.getElementById('clearSort').addEventListener('click', () => {{
  sortCol = -1; sortDir = 'asc';
  render();
}});

document.getElementById('filterToggleBtn').addEventListener('click', () => {{
  const bar = document.getElementById('filterBar');
  const isOpen = bar.classList.toggle('open');
  if (isOpen) buildFilterBar();
}});

document.getElementById('resetView').addEventListener('click', () => {{
  sortCol = -1; sortDir = 'asc';
  searchText = ''; filterIndustry = ''; filterStockType = '';
  filters = {{}};
  document.getElementById('searchBox').value = '';
  document.getElementById('stockTypeFilter').value = '';
  document.getElementById('industryFilter').value = '';
  visiblePeriods = new Set(PERIODS);
  visibleMetrics = new Set(METRICS.filter(m => !METRICS_DEFAULT_HIDDEN.has(m)));
  visibleComputedCols = new Set(COMPUTED_COL_NAMES.filter(n => !COMPUTED_DEFAULT_HIDDEN.has(n)));
  document.getElementById('filterBar').classList.remove('open');
  updateFilterToggleStyle();
  closeColPicker();
  render();
}});

document.getElementById('exportBtn').addEventListener('click', exportExcel);

// ---- Init ----
render();
</script>
</body>
</html>'''

with open(os.path.join(BASE_DIR, 'hk_stocks.html'), 'w', encoding='utf-8') as f:
    f.write(html)

print(f"HTML generated: {len(html):,} chars")
print(f"Columns: {len(headers)}, Rows: {len(rows)}")
print(f"ROE_2024_IDX={ROE_2024_IDX}, PROFIT_2024_IDX={PROFIT_2024_IDX}, CF_2024_IDX={CF_2024_IDX}")
