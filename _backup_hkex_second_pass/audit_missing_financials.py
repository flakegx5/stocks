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

ZERO_FILL_ALLOWED_METRICS = {"短期借款", "长期借款"}

QUEUE_STRATEGIES = {
    "only_cash": {
        "audit_priority": 1,
        "recoverability": "high",
        "strategy": "direct_extract",
        "reason": "现金类通常能从业绩公告的资产负债表或流动性段落中直接补出。",
    },
    "only_long_debt": {
        "audit_priority": 1,
        "recoverability": "high",
        "strategy": "direct_extract",
        "reason": "长期借款在报表和附注中相对稳定，适合高置信直接抽值。",
    },
    "only_capex": {
        "audit_priority": 1,
        "recoverability": "high",
        "strategy": "direct_extract",
        "reason": "资本开支常见于现金流量表或资本承诺附注，适合单指标补抓。",
    },
    "only_short_and_long_debt": {
        "audit_priority": 2,
        "recoverability": "medium",
        "strategy": "direct_extract_or_zero",
        "reason": "借款缺口既可能来自明确金额，也可能来自高置信零借款表述，需要双路径处理。",
    },
    "cashflow_cluster_only": {
        "audit_priority": 3,
        "recoverability": "low",
        "strategy": "defer_or_manual",
        "reason": "现金流组缺口往往涉及多字段联动，当前规则化补抓成本较高。",
    },
    "complex_gap": {
        "audit_priority": 4,
        "recoverability": "low",
        "strategy": "manual_review",
        "reason": "复杂缺口不适合当前单文档单轮规则补抓，应先人工分型。",
    },
    "optional_only": {
        "audit_priority": 5,
        "recoverability": "low",
        "strategy": "opportunistic",
        "reason": "仅缺可选字段，对主看板影响较小，可低优先级顺手补。",
    },
}


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
        "missing_metric_groups": {
            "debt": [metric for metric in core_missing if metric in {"短期借款", "长期借款"}],
            "cash": [metric for metric in core_missing if metric == "总现金"],
            "capex": [metric for metric in core_missing if metric == "资本性支出"],
            "cashflow": [
                metric
                for metric in core_missing
                if metric in {"经营活动产生的现金流量净额", "投资活动产生的现金流量净额", "融资活动产生的现金流量净额"}
            ],
            "other": [
                metric
                for metric in core_missing
                if metric
                not in {
                    "短期借款",
                    "长期借款",
                    "总现金",
                    "资本性支出",
                    "经营活动产生的现金流量净额",
                    "投资活动产生的现金流量净额",
                    "融资活动产生的现金流量净额",
                }
            ],
        },
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


def build_gap_strategy(record: dict) -> dict:
    queue_type = record["queue_type"]
    strategy = QUEUE_STRATEGIES.get(
        queue_type,
        {
            "audit_priority": 9,
            "recoverability": "low",
            "strategy": "manual_review",
            "reason": "未命中预设策略，默认进入人工复核。",
        },
    )
    zero_fill_metrics = [
        metric for metric in record["core_missing"] if metric in ZERO_FILL_ALLOWED_METRICS
    ]
    return {
        "audit_priority": strategy["audit_priority"],
        "recoverability": strategy["recoverability"],
        "strategy": strategy["strategy"],
        "reason": strategy["reason"],
        "zero_fill_metrics": zero_fill_metrics,
    }


def build_second_pass_queue(rows: list[dict]) -> list[dict]:
    queue = []
    for row in rows:
        latest_period = pick_latest_period(row)
        record = build_record(row, latest_period)
        if not record["core_missing"] and not record["optional_missing"]:
            continue
        record["queue_type"] = classify_second_pass(record)
        record["latest_effective_period"] = latest_period
        record["gap_strategy"] = build_gap_strategy(record)
        queue.append(record)
    queue.sort(
        key=lambda item: (
            item["gap_strategy"]["audit_priority"],
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
    strategy_counter = Counter(record["gap_strategy"]["strategy"] for record in second_pass_queue)
    print("\n== Second-Pass Queue ==")
    print(f"records: {len(second_pass_queue)}")
    for queue_type, count in queue_counter.most_common():
        print(f"  {queue_type}: {count}")
    print("strategies:")
    for strategy, count in strategy_counter.most_common():
        print(f"  {strategy}: {count}")
    print("examples:")
    for record in second_pass_queue[:15]:
        core_missing = "、".join(record["core_missing"]) or "(none)"
        optional_missing = "、".join(record["optional_missing"]) or "(none)"
        zero_fill = "、".join(record["gap_strategy"]["zero_fill_metrics"]) or "(none)"
        print(
            f"  {record['code']} {record['name']} [{record['period']}] "
            f"{record['queue_type']} | core={core_missing} | optional={optional_missing} "
            f"| strategy={record['gap_strategy']['strategy']} | zero_fill={zero_fill}"
        )

    if args.write_json:
        output_path = Path(args.write_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "non_financial_total": len(rows),
            "latest_effective_period_gaps": latest_records,
            "annual_interim_partial_gaps": focus_records,
            "second_pass_queue": second_pass_queue,
            "core_metrics": CORE_METRICS,
            "optional_metrics": OPTIONAL_METRICS,
            "queue_strategies": QUEUE_STRATEGIES,
            "zero_fill_allowed_metrics": sorted(ZERO_FILL_ALLOWED_METRICS),
        }
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\njson written: {args.write_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
