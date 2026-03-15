#!/usr/bin/env python3
"""Audit missing non-financial metrics in the HK stocks dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from stocks_build.metrics import filter_source_rows, get_float, is_jinrong  # noqa: E402

CORE_METRICS = [
    "归属于母公司所有者的净利润",
    "归属母公司股东的净利润(同比增长率)",
    "总现金",
    "流动资产合计",
    "负债合计",
    "短期借款",
    "长期借款",
    "权益合计",
    "净资产收益率roe",
    "投入资本回报率",
    "经营活动产生的现金流量净额",
    "投资活动产生的现金流量净额",
    "资本性支出",
    "融资活动产生的现金流量净额",
]

OPTIONAL_METRICS = [
    "股份回购",
    "支付股息",
    "年度分红总额",
]

PERIOD_CODE = {
    "2025年报": "20251231",
    "2025三季报": "20250930",
    "2025中报": "20250630",
    "2025一季报": "20250331",
    "2024年报": "20241231",
    "2024三季报": "20240930",
    "2024中报": "20240630",
    "2024一季报": "20240331",
    "2023年报": "20231231",
    "2023三季报": "20230930",
    "2023中报": "20230630",
    "2023一季报": "20230331",
}

LATEST_PRIORITY = ("2025年报", "2025三季报", "2025中报")
FOCUS_PERIODS = ("2025年报", "2025中报", "2024年报", "2024中报", "2023年报", "2023中报")

SECOND_PASS_PRIORITY = [
    {"name": "only_long_debt", "metrics": {"长期借款"}},
    {"name": "only_short_and_long_debt", "metrics": {"短期借款", "长期借款"}},
    {"name": "only_capex", "metrics": {"资本性支出"}},
    {"name": "only_cash", "metrics": {"总现金"}},
    {
        "name": "cashflow_cluster_only",
        "metrics": {
            "经营活动产生的现金流量净额",
            "投资活动产生的现金流量净额",
            "资本性支出",
            "融资活动产生的现金流量净额",
        },
    },
]


def load_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = filter_source_rows(payload.get("rows", []))
    return [row for row in rows if not is_jinrong(dict(row))]


def pick_latest_period(row: dict) -> str:
    for label in LATEST_PRIORITY:
        if get_float(row, "归属于母公司所有者的净利润", label) is not None:
            return label
    return "2025中报"


def missing_metrics(row: dict, period_label: str, metrics: list[str]) -> list[str]:
    code = PERIOD_CODE[period_label]
    return [metric for metric in metrics if row.get(f"港股@{metric}[{code}]") in (None, "")]


def build_record(row: dict, period_label: str) -> dict:
    core_missing = missing_metrics(row, period_label, CORE_METRICS)
    optional_missing = missing_metrics(row, period_label, OPTIONAL_METRICS)
    return {
        "code": str(row.get("股票代码", "")),
        "name": str(row.get("股票简称", "")),
        "industry": str(row.get("港股@所属恒生行业(二级)", "")),
        "period": period_label,
        "core_missing_count": len(core_missing),
        "optional_missing_count": len(optional_missing),
        "core_missing": core_missing,
        "optional_missing": optional_missing,
    }


def summarize(records: list[dict], title: str) -> None:
    print(f"\n== {title} ==")
    print(f"records: {len(records)}")
    if not records:
        return

    metric_counter = Counter()
    pattern_counter = Counter()
    for record in records:
        metric_counter.update(record["core_missing"])
        pattern_counter[tuple(record["core_missing"])] += 1

    print("top missing core metrics:")
    for metric, count in metric_counter.most_common(10):
        print(f"  {metric}: {count}")

    print("top missing patterns:")
    for pattern, count in pattern_counter.most_common(10):
        rendered = "、".join(pattern) if pattern else "(none)"
        print(f"  {rendered}: {count}")

    print("examples:")
    for record in sorted(records, key=lambda item: (-item["core_missing_count"], item["code"]))[:12]:
        missing = "、".join(record["core_missing"])
        print(f"  {record['code']} {record['name']} [{record['period']}] -> {missing}")


def classify_second_pass(record: dict) -> str:
    missing = set(record["core_missing"])
    if not record["core_missing"] and record["optional_missing"]:
        return "optional_only"
    for item in SECOND_PASS_PRIORITY:
        if missing == item["metrics"]:
            return item["name"]
    if missing.issubset(SECOND_PASS_PRIORITY[-1]["metrics"]):
        return SECOND_PASS_PRIORITY[-1]["name"]
    return "complex_gap"


def build_second_pass_queue(rows: list[dict]) -> list[dict]:
    queue = []
    for row in rows:
        latest_period = pick_latest_period(row)
        record = build_record(row, latest_period)
        if not record["core_missing"] and not record["optional_missing"]:
            continue
        record["queue_type"] = classify_second_pass(record)
        record["latest_effective_period"] = latest_period
        queue.append(record)
    queue.sort(
        key=lambda item: (
            item["queue_type"] == "complex_gap",
            item["queue_type"] == "optional_only",
            item["core_missing_count"],
            item["code"],
        )
    )
    return queue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(BASE_DIR / "hk_stocks_data_new.json"),
        help="Path to hk_stocks_data_new.json",
    )
    parser.add_argument(
        "--write-json",
        default="",
        help="Optional output path for machine-readable audit JSON",
    )
    args = parser.parse_args()

    rows = load_rows(Path(args.input))

    latest_records = []
    for row in rows:
        latest_period = pick_latest_period(row)
        record = build_record(row, latest_period)
        if record["core_missing"]:
            latest_records.append(record)

    focus_records = []
    for row in rows:
        for period_label in FOCUS_PERIODS:
            record = build_record(row, period_label)
            if record["core_missing_count"] and record["core_missing_count"] < len(CORE_METRICS):
                focus_records.append(record)

    summarize(latest_records, "Latest Effective Period Core Gaps")
    summarize(focus_records, "Annual/Interim Partial Core Gaps")

    second_pass_queue = build_second_pass_queue(rows)
    queue_counter = Counter(record["queue_type"] for record in second_pass_queue)
    print("\n== Second-Pass Queue ==")
    print(f"records: {len(second_pass_queue)}")
    for queue_type, count in queue_counter.most_common():
        print(f"  {queue_type}: {count}")
    print("examples:")
    for record in second_pass_queue[:15]:
        core_missing = "、".join(record["core_missing"]) or "(none)"
        optional_missing = "、".join(record["optional_missing"]) or "(none)"
        print(
            f"  {record['code']} {record['name']} [{record['period']}] "
            f"{record['queue_type']} | core={core_missing} | optional={optional_missing}"
        )

    if args.write_json:
        output = {
            "non_financial_total": len(rows),
            "latest_effective_period_gaps": latest_records,
            "annual_interim_partial_gaps": focus_records,
            "second_pass_queue": second_pass_queue,
            "core_metrics": CORE_METRICS,
            "optional_metrics": OPTIONAL_METRICS,
        }
        Path(args.write_json).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\njson written: {args.write_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
