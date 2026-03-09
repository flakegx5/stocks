#!/usr/bin/env python3
"""
update_market.py — 每日更新港股易变市场数据

数据来源：
  - 最新价、涨跌幅：AKShare / 东方财富 (stock_hk_spot_em / stock_hk_main_board_spot_em)
  - 总市值：最新价 × 总股本（总股本来自 hk_stocks_data_new.json，极少变化）
  - PE(TTM)、PB：暂由 iwencai 原始数据提供（AKShare 当前无批量接口）

输出：hk_stocks_market.json
  {
    "updated_at": "2026-03-09T16:35:00",
    "source": "...",
    "count": 700,
    "data": { "00700": {"price":300.2, "change_pct":1.5, "mkt_cap":2.76e12}, ... }
  }

用法：
    python3 update_market.py              # 仅更新 JSON
    python3 update_market.py --build      # 更新 JSON + 重建 HTML
    python3 update_market.py --build --push  # + git push
"""

import json
import os
import sys
import subprocess
from datetime import datetime

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
FINANCIAL_JSON = os.path.join(BASE_DIR, 'hk_stocks_data_new.json')
MARKET_JSON    = os.path.join(BASE_DIR, 'hk_stocks_market.json')

# 总股本的 iwencai key（与 build_html.py 的 MKT_KEY_SHARES 一致）
SHARES_KEY = '港股@总股本[20260309]'


def safe_float(v):
    """Convert to float; return None for None/NaN/error."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if (f != f) else f  # NaN guard
    except (TypeError, ValueError):
        return None


def load_shares_map():
    """从 iwencai JSON 读取 股票代码→总股本 映射（用于计算总市值）。"""
    try:
        with open(FINANCIAL_JSON, encoding='utf-8') as f:
            raw = json.load(f)
        obj_rows = raw.get('rows', [])
    except Exception as e:
        print(f"警告: 无法读取 {FINANCIAL_JSON}: {e}")
        return {}

    shares_map = {}
    for obj in obj_rows:
        code_raw = str(obj.get('股票代码', '')).strip()
        # 与 clean_code() 保持一致: '3317.HK' → '03317'
        code = code_raw.replace('.HK', '').replace('HK', '').strip()
        if code.isdigit():
            code = code.zfill(5)
        shares = safe_float(obj.get(SHARES_KEY))
        if code and shares:
            shares_map[code] = shares

    print(f"总股本: 读取到 {len(shares_map)} 只股票")
    return shares_map


def fetch_price_data():
    """
    从 AKShare 获取价格和涨跌幅。
    优先用 stock_hk_spot_em（全部港股），失败则回退到 stock_hk_main_board_spot_em（主板）。
    返回 dict: code5 → {'price': float, 'change_pct': float}
    """
    try:
        import akshare as ak
    except ImportError:
        print("错误: 未安装 akshare，请运行: pip3 install akshare")
        return None

    df = None
    for fn_name in ('stock_hk_spot_em', 'stock_hk_main_board_spot_em'):
        try:
            print(f"  尝试 ak.{fn_name}()...")
            df = getattr(ak, fn_name)()
            print(f"  获取到 {len(df)} 条记录，字段: {list(df.columns)}")
            break
        except Exception as e:
            print(f"  {fn_name} 失败: {e}")

    if df is None:
        print("所有接口均失败")
        return None

    # 动态识别列名
    col_code   = next((c for c in df.columns if c in ('代码',)), None)
    col_price  = next((c for c in df.columns if '最新价' in c), None)
    col_chg    = next((c for c in df.columns if '涨跌幅' in c), None)

    if not col_code or not col_price:
        print(f"警告: 无法识别代码列或价格列，已有: {list(df.columns)}")
        return None

    result = {}
    for _, row in df.iterrows():
        code = str(row.get(col_code, '')).strip().zfill(5)
        price = safe_float(row.get(col_price))
        if not code or price is None:
            continue
        result[code] = {
            'price':      price,
            'change_pct': safe_float(row.get(col_chg)) if col_chg else None,
        }

    return result


def main():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] 开始更新港股市场数据...")

    # Step 1: 获取实时价格
    print("\n[1/2] 获取实时价格 (AKShare)...")
    price_data = fetch_price_data()
    if price_data is None:
        print("价格获取失败，中止")
        return False
    print(f"  价格数据: {len(price_data)} 只股票")

    # Step 2: 加载总股本，计算总市值
    print("\n[2/2] 计算总市值 (价格 × 总股本)...")
    shares_map = load_shares_map()

    data = {}
    mkt_computed = 0
    for code, pd_entry in price_data.items():
        price = pd_entry.get('price')
        shares = shares_map.get(code)

        entry = {
            'price':      price,
            'change_pct': pd_entry.get('change_pct'),
            'mkt_cap':    None,
        }
        if price is not None and shares is not None:
            entry['mkt_cap'] = price * shares  # 港元（与 iwencai 原始单位一致）
            mkt_computed += 1

        if any(v is not None for v in entry.values()):
            data[code] = entry

    print(f"  已计算总市值: {mkt_computed} 只（总 {len(data)} 只有行情数据）")

    # 统计覆盖率（与 hk_stocks_data_new.json 的交集）
    def coverage(key):
        return sum(1 for v in data.values() if v.get(key) is not None)
    print(f"\n覆盖率 — 价格:{coverage('price')} 涨跌幅:{coverage('change_pct')} 市值:{coverage('mkt_cap')}")
    print(f"注: PE(TTM)/PB 暂用 iwencai 原始数据（AKShare 无批量接口）")

    # Step 3: 保存
    out = {
        'updated_at': datetime.now().isoformat(),
        'source':     'price/change: akshare; mkt_cap: price×shares(iwencai)',
        'count':      len(data),
        'data':       data,
    }
    with open(MARKET_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f"\n已保存 → {MARKET_JSON}")
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='更新港股易变市场数据')
    parser.add_argument('--build', action='store_true', help='完成后自动重建 hk_stocks.html')
    parser.add_argument('--push',  action='store_true', help='完成后自动 git add/commit/push')
    args = parser.parse_args()

    ok = main()
    if not ok:
        sys.exit(1)

    if args.build:
        print("\n[build] 正在重建 HTML...")
        ret = subprocess.run(
            ['python3', os.path.join(BASE_DIR, 'build_html.py')],
            cwd=BASE_DIR
        )
        if ret.returncode != 0:
            print("[build] 失败，中止")
            sys.exit(1)

    if args.push:
        ts_short = datetime.now().strftime('%Y-%m-%d %H:%M')
        print(f"\n[push] 推送至 GitHub ({ts_short})...")
        subprocess.run(['git', 'add', 'hk_stocks_market.json'], cwd=BASE_DIR)
        ret = subprocess.run(
            ['git', 'commit', '-m', f'市场数据更新: {ts_short}'],
            cwd=BASE_DIR
        )
        if ret.returncode == 0:
            subprocess.run(['git', 'push'], cwd=BASE_DIR)
        else:
            print("[push] 无变更可提交，跳过")
