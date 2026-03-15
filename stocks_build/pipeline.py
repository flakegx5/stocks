"""End-to-end build pipeline for the HK stocks dashboard."""

import json
import os
import re
from datetime import datetime

from .config import (
    COMPUTED_COL_DEFS,
    COMPUTED_HIDE_DEFAULT,
    COMPUTED_YI_NAMES,
    FILTER_SPECS,
    FIXED_COLS,
    FIXED_HIDE_DEFAULT,
    METRICS_HIDE_DEFAULT,
    PERIOD_DATES,
    PERIOD_METRICS,
)
from .metrics import build_market_keys, clean_code, compute_phase1, filter_source_rows, inject_market
from .ranking import compute_rankings


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def get_val(obj, raw_key):
    if raw_key is None:
        return 0
    val = obj.get(raw_key, None)
    if val is None or val == "" or val != val:
        return "--"
    if isinstance(val, float):
        if val == int(val) and abs(val) < 1e13:
            return str(int(val))
        return str(round(val, 4))
    return str(val)


def build_all_columns(market_keys):
    all_cols = []
    for index, (display, raw_key) in enumerate(FIXED_COLS):
        actual_raw_key = raw_key
        if display == "最新价(港元)":
            actual_raw_key = market_keys["price"]
        elif display == "最新涨跌幅(%)":
            actual_raw_key = market_keys["chg"]
        elif display == "总市值(港元)":
            actual_raw_key = market_keys["mktcap"]
        elif display == "市盈率(pe,ttm)":
            actual_raw_key = market_keys["pe"]
        elif display == "市净率(pb)":
            actual_raw_key = market_keys["pb"]
        elif display == "总股本(股)":
            actual_raw_key = market_keys["shares"]
        all_cols.append(
            {
                "header": display,
                "raw_key": actual_raw_key,
                "group": "基本信息",
                "locked": index < 3,
                "defaultVisible": display not in FIXED_HIDE_DEFAULT,
            }
        )
    for name in COMPUTED_COL_DEFS:
        all_cols.append(
            {
                "header": name,
                "raw_key": None,
                "group": "计算指标",
                "locked": False,
                "defaultVisible": True,
            }
        )
    for raw_metric, display_metric in PERIOD_METRICS:
        default_visible = display_metric not in METRICS_HIDE_DEFAULT
        for date_code, date_label in PERIOD_DATES:
            all_cols.append(
                {
                    "header": f"{display_metric}|{date_label}",
                    "raw_key": f"港股@{raw_metric}[{date_code}]",
                    "group": display_metric,
                    "locked": False,
                    "defaultVisible": default_visible,
                }
            )
    return all_cols


def build_rows(source_rows, all_cols, market_keys):
    phase1_list = [compute_phase1(obj, market_keys) for obj in source_rows]
    ranking_list = compute_rankings(phase1_list)
    rows = []
    for row_index, obj in enumerate(source_rows):
        code = clean_code(obj.get("股票代码", obj.get("code", "")))
        derived = phase1_list[row_index]["vals"] + ranking_list[row_index]
        derived_map = dict(zip(COMPUTED_COL_DEFS, derived))
        row = []
        for col_index, col in enumerate(all_cols):
            if col_index == 0:
                row.append(0)
            elif col["header"] == "股票代码":
                row.append(code)
            elif col["group"] == "计算指标":
                row.append(derived_map.get(col["header"], "--"))
            else:
                row.append(get_val(obj, col["raw_key"]))
        rows.append(row)
    return rows


def build_data_bundle(all_cols, rows):
    headers = [col["header"] for col in all_cols]
    cols_meta = [
        {
            "idx": idx,
            "name": col["header"].split("|")[0],
            "fullName": col["header"],
            "group": col["group"],
            "locked": col["locked"],
            "defaultVisible": col["defaultVisible"],
        }
        for idx, col in enumerate(all_cols)
    ]
    period_start = 10 + len(COMPUTED_COL_DEFS)
    periods_count = len(PERIOD_DATES)
    metric_labels = [display for _, display in PERIOD_METRICS]
    roic_start = period_start + metric_labels.index("ROIC") * periods_count
    roic_end = roic_start + periods_count - 1
    ttmroe_idx = 10 + COMPUTED_COL_DEFS.index("TTMROE")
    ttmroic_idx = 10 + COMPUTED_COL_DEFS.index("TTMROIC")
    return {
        "headers": headers,
        "rows": rows,
        "cols": cols_meta,
        "periods": [label for _, label in PERIOD_DATES],
        "metrics": metric_labels,
        "roic_start": roic_start,
        "roic_end": roic_end,
        "ttmroe_idx": ttmroe_idx,
        "ttmroic_idx": ttmroic_idx,
        "metrics_hidden": sorted(METRICS_HIDE_DEFAULT),
        "computed_hidden": sorted(COMPUTED_HIDE_DEFAULT),
        "fixed_hidden": sorted(FIXED_HIDE_DEFAULT),
        "row_count": len(rows),
        "computed_col_names": list(COMPUTED_COL_DEFS),
        "computed_yi_cols": [10 + index for index, name in enumerate(COMPUTED_COL_DEFS) if name in COMPUTED_YI_NAMES],
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filter_cols": [
            {"idx": 10 + COMPUTED_COL_DEFS.index(name), "name": name, "unit": unit, "isYi": name in COMPUTED_YI_NAMES}
            for name, unit in FILTER_SPECS
        ],
    }


def write_outputs(base_dir, bundle):
    with open(os.path.join(base_dir, "data.js"), "w", encoding="utf-8") as handle:
        handle.write("window.STOCK_DATA=" + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + ";")
    index_path = os.path.join(base_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as handle:
            html = handle.read()
        timestamp = int(datetime.now().timestamp())
        html = re.sub(r'<script src="data\.js(?:\?t=\d+)?"></script>', f'<script src="data.js?t={timestamp}"></script>', html)
        with open(index_path, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(f"✅ index.html updated with cache-busting timestamp: ?t={timestamp}")


def run_build(base_dir):
    financial_json_path = os.path.join(base_dir, "hk_stocks_data_new.json")
    market_json_path = os.path.join(base_dir, "hk_stocks_market.json")
    raw = load_json(financial_json_path)
    source_rows = filter_source_rows(raw.get("rows", []))
    market_keys = build_market_keys(raw.get("rows", []))
    print(f"📊 MKT keys: MKTCAP={market_keys['mktcap']!r}  SHARES={market_keys['shares']!r}")

    market_data = {}
    market_updated_at = None
    if os.path.exists(market_json_path):
        try:
            market_payload = load_json(market_json_path)
            market_data = market_payload.get("data", {})
            market_updated_at = market_payload.get("updated_at", "?")
            print(f"市场数据已加载: {len(market_data)} 只, 更新于 {market_updated_at}")
        except Exception as exc:
            print(f"警告: 市场数据加载失败 ({exc}), 使用 iwencai 原始数据")

    financial_mtime = os.path.getmtime(financial_json_path)
    market_mtime = os.path.getmtime(market_json_path) if os.path.exists(market_json_path) else 0.0
    use_market_injection = bool(market_data) and (market_mtime > financial_mtime)
    if use_market_injection:
        injected = sum(1 for obj in source_rows if market_data.get(clean_code(obj.get("股票代码", ""))))
        for obj in source_rows:
            inject_market(obj, market_data, market_keys)
        print(f"AKShare 注入: {injected}/{len(source_rows)} 只股票已更新价格/市值（市场数据: {market_updated_at}）")
    elif market_data:
        print("iwencai 数据更新（mtime 较新），跳过 AKShare 注入，以 iwencai 原始值为准")
    else:
        print("市场数据未加载，使用 iwencai 原始数据（运行 update_market.py 可获取最新行情）")

    all_cols = build_all_columns(market_keys)
    rows = build_rows(source_rows, all_cols, market_keys)
    bundle = build_data_bundle(all_cols, rows)
    write_outputs(base_dir, bundle)
    print(f"Columns: {len(bundle['headers'])}, Rows: {len(rows)}")
    print(f"N_PERIODS={len(PERIOD_DATES)}, PERIOD_START={10 + len(COMPUTED_COL_DEFS)}")
    print(f"ROIC_START_IDX={bundle['roic_start']}, ROIC_END_IDX={bundle['roic_end']}")


def main():
    run_build(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

