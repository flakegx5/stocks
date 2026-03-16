#!/usr/bin/env python3
"""Prototype HKEXnews second-pass fetcher for missing financial data."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from pypdf import PdfReader
from requests import RequestException

BASE_DIR = Path(__file__).resolve().parents[1]
QUEUE_PATH = BASE_DIR / "debug_responses" / "missing_financial_audit.json"
OUTPUT_DIR = BASE_DIR / "debug_responses" / "hkex_second_pass"

HKEX_BASE = "https://www.hkexnews.hk"
HKEX_PREFIX_URL = "https://www1.hkexnews.hk/search/prefix.do"
HKEX_PARTIAL_URL = "https://www1.hkexnews.hk/search/partial.do"
HKEX_TITLE_URL = "https://www.hkexnews.hk/search/titleSearchServlet.do"
ECB_FX_URL = "https://data-api.ecb.europa.eu/service/data/EXR"

REPORT_KEYWORDS = {
    "年报": ["annual results", "final results", "annual report"],
    "中报": ["interim results", "interim report", "interim results announcement"],
    "三季报": ["quarterly results", "third quarterly results", "third quarter results"],
}

NOISE_KEYWORDS = [
    "monthly return",
    "reply form",
    "notification letter",
    "letter to",
    "date of board meeting",
    "notice of publication",
    "list of members of the board",
]

METRIC_ALIASES = {
    "总现金": [
        "总现金",
        "现金",
        "货币资金",
        "现金及现金等价物",
        "现金及银行结余",
        "银行结余及现金",
        "银行存款及现金",
        "现金及银行存款",
        "cash and cash equivalents",
        "bank balances and cash",
        "cash and bank balances",
        "cash, bank balances and deposits",
        "bank balances, deposits and cash",
        "cash and bank deposits",
        "bank deposits",
    ],
    "现金及现金等价物": [
        "现金及现金等价物",
        "现金",
        "货币资金",
        "cash and cash equivalents",
        "cash",
        "cash balances",
        "bank balances and cash",
        "cash and bank balances",
        "cash at bank and on hand",
        "bank balances, deposits and cash",
    ],
    "受限制货币资金": [
        "受限制货币资金",
        "受限制银行存款",
        "已抵押银行存款",
        "质押银行存款",
        "pledged bank deposits",
        "restricted bank deposits",
        "restricted cash",
    ],
    "定期存款": [
        "定期存款",
        "银行定期存款",
        "time deposits",
        "fixed deposits",
        "bank deposits",
    ],
    "短期投资": [
        "短期投资",
        "短期理财",
        "短期金融资产",
        "short-term investments",
        "current financial assets",
        "financial assets at fair value through profit or loss",
        "financial assets at amortised cost",
    ],
    "短期借款": [
        "短期借款",
        "一年内到期的借款",
        "一年内到期的银行借款",
        "short-term borrowings",
        "bank borrowings – amount due within one year",
        "bank borrowings - amount due within one year",
        "amount due within one year",
        "repayable within one year",
        "bank borrowings - current",
        "current borrowings",
        "current portion of borrowings",
        "current portion of bank borrowings",
    ],
    "长期借款": [
        "长期借款",
        "长期银行借款",
        "非流动借款",
        "long-term borrowings",
        "bank borrowings – amount due after one year",
        "bank borrowings - amount due after one year",
        "amount due after one year",
        "repayable after one year",
        "bank borrowings - non-current",
        "non-current borrowings",
        "bank loans and other interest-bearing borrowings",
        "bank loans and other borrowings",
        "bank and other borrowings",
        "bank and other loans",
        "interest-bearing bank and other borrowings",
    ],
    "资本性支出": [
        "资本性支出",
        "资本开支",
        "购建固定资产",
        "capital expenditure",
        "capital commitments",
        "capital expenditure contracted for",
        "capital commitments contracted for",
        "purchase of property, plant and equipment",
        "additions to property, plant and equipment",
    ],
    "经营活动产生的现金流量净额": [
        "经营活动产生的现金流量净额",
        "net cash generated from operating activities",
        "net cash from operating activities",
    ],
    "投资活动产生的现金流量净额": [
        "投资活动产生的现金流量净额",
        "net cash used in investing activities",
        "net cash from investing activities",
    ],
    "融资活动产生的现金流量净额": [
        "融资活动产生的现金流量净额",
        "net cash from financing activities",
        "net cash used in financing activities",
    ],
    "年度分红总额": [
        "年度分红",
        "final dividend",
        "interim dividend",
        "special dividend",
    ],
    "支付股息": [
        "支付股息",
        "dividend paid",
        "dividends paid",
    ],
    "股份回购": [
        "股份回购",
        "share repurchase",
        "share buy-back",
        "buy-back",
    ],
}

BORROWING_NEGATION_PATTERNS = [
    re.compile(r"\bdid not have(?: any)?\b.{0,80}\bborrowings?\b", re.IGNORECASE),
    re.compile(r"\bno outstanding\b.{0,80}\bborrowings?\b", re.IGNORECASE),
    re.compile(r"\bno\b.{0,40}\bborrowings?\b", re.IGNORECASE),
    re.compile(r"\bborrowings?\b.{0,20}\b(?:was|were|is|are)\s+nil\b", re.IGNORECASE),
    re.compile(r"\bgearing ratio\b.{0,40}\b(?:was|were|is|are)\s+nil\b", re.IGNORECASE),
]

NON_BORROWING_CURRENT_LIABILITY_TERMS = [
    "trade payable",
    "trade payables",
    "other payable",
    "other payables",
    "amounts due to",
    "due to the immediate holding company",
    "due to an intermediate holding company",
    "related parties",
    "contract liabilities",
    "lease liabilities",
]

BORROWING_CONTEXT_TERMS = [
    "borrowings",
    "bank borrowings",
    "bank loans",
    "loans",
    "interest-bearing",
]

ZERO_BORROWING_RULES = [
    {
        "metrics": ("短期借款", "长期借款"),
        "alias": "no short-term or long-term bank borrowings",
        "pattern": re.compile(
            r"\bdid not have any short-term or long-term bank borrowings\b",
            re.IGNORECASE,
        ),
    },
    {
        "metrics": ("短期借款", "长期借款"),
        "alias": "no borrowings",
        "pattern": re.compile(
            r"\b(?:did not have any|has no|have no|had no|no outstanding)\b.{0,60}\bborrowings?\b",
            re.IGNORECASE,
        ),
    },
    {
        "metrics": ("短期借款", "长期借款"),
        "alias": "no interest-bearing bank and other borrowings",
        "pattern": re.compile(
            r"\bdid not have any interest-bearing bank and other borrowings\b",
            re.IGNORECASE,
        ),
    },
    {
        "metrics": ("短期借款", "长期借款"),
        "alias": "no bank and other borrowings",
        "pattern": re.compile(
            r"\bno outstanding bank and other borrowings\b",
            re.IGNORECASE,
        ),
    },
    {
        "metrics": ("长期借款",),
        "alias": "no long-term borrowings",
        "pattern": re.compile(
            r"\b(?:does not have any|did not have any|has no|have no)\b.{0,20}\blong-term borrowings\b",
            re.IGNORECASE,
        ),
    },
    {
        "metrics": ("短期借款",),
        "alias": "no short-term borrowings",
        "pattern": re.compile(
            r"\b(?:does not have any|did not have any|has no|have no)\b.{0,20}\bshort-term borrowings\b",
            re.IGNORECASE,
        ),
    },
]

CASH_COMPONENTS = [
    "现金及现金等价物",
    "受限制货币资金",
    "定期存款",
    "短期投资",
]

DEFAULT_QUEUE_TYPES = [
    "only_cash",
    "only_long_debt",
    "only_short_and_long_debt",
    "only_capex",
]

CURRENCY_PATTERNS = {
    "HKD": [r"\bHKD\b", r"\bHK\$", r"港元"],
    "CNY": [r"\bRMB\b", r"\bCNY\b", r"人民币", r"¥"],
    "USD": [r"\bUSD\b", r"\bUS\$", r"美元"],
    "CAD": [r"\bCAD\b", r"\bC\$", r"加元"],
    "EUR": [r"\bEUR\b", r"欧元", r"€"],
}

UNIT_PATTERNS = [
    (re.compile(r"\b(?:HK\$|RMB|USD|US\$|CAD|C\$|EUR)\s*['’]000\b", re.IGNORECASE), 1_000),
    (re.compile(r"\b(?:HK\$|RMB|USD|US\$|CAD|C\$|EUR)\s*million\b", re.IGNORECASE), 1_000_000),
    (re.compile(r"\b(?:HK\$|RMB|USD|US\$|CAD|C\$|EUR)\s*billion\b", re.IGNORECASE), 1_000_000_000),
    (re.compile(r"人民币[千仟]元"), 1_000),
    (re.compile(r"人民币万元"), 10_000),
    (re.compile(r"人民币百万元"), 1_000_000),
    (re.compile(r"人民币亿元"), 100_000_000),
    (re.compile(r"港元[千仟]元"), 1_000),
    (re.compile(r"港元万元"), 10_000),
    (re.compile(r"港元百万元"), 1_000_000),
    (re.compile(r"港元亿元"), 100_000_000),
]


@dataclass
class SearchResult:
    stock_code: str
    stock_name: str
    title: str
    short_text: str
    file_type: str
    file_link: str
    file_info: str
    date_time: datetime
    news_id: str


class HkexNewsClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def resolve_stock_id(self, code_or_name: str) -> tuple[str, str, int]:
        code = clean_code(code_or_name)
        params = {
            "lang": "EN",
            "type": "A",
            "name": code,
            "market": "SEHK",
            "callback": "callback",
        }
        response = self.session.get(HKEX_PREFIX_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = parse_jsonp(response.text)
        stock_info = payload.get("stockInfo", [])
        for item in stock_info:
            if clean_code(item.get("code", "")) == code:
                return item["code"], item["name"], int(item["stockId"])
        raise RuntimeError(f"unable to resolve stock id for {code_or_name}")

    def search_documents(self, stock_id: int, start: date, end: date) -> list[SearchResult]:
        params = {
            "sortDir": "0",
            "sortByOptions": "DateTime",
            "category": "0",
            "market": "SEHK",
            "stockId": str(stock_id),
            "documentType": "",
            "fromDate": start.strftime("%Y-%m-%d"),
            "toDate": end.strftime("%Y-%m-%d"),
            "title": "",
            "searchType": "1",
            "t1code": "",
            "t2Gcode": "",
            "t2code": "",
            "rowRange": "100",
            "lang": "EN",
        }
        response = self.session.get(HKEX_TITLE_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        items = json.loads(payload.get("result") or "[]")
        results = []
        for item in items:
            results.append(
                SearchResult(
                    stock_code=item["STOCK_CODE"],
                    stock_name=item["STOCK_NAME"],
                    title=item["TITLE"],
                    short_text=item["SHORT_TEXT"],
                    file_type=item["FILE_TYPE"],
                    file_link=urljoin(HKEX_BASE, item["FILE_LINK"]),
                    file_info=item["FILE_INFO"],
                    date_time=datetime.strptime(item["DATE_TIME"], "%d/%m/%Y %H:%M"),
                    news_id=item["NEWS_ID"],
                )
            )
        return results

    def download(self, url: str) -> bytes:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.content


class EcbFxClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "stocks-hkex-second-pass/1.0"})
        self.cache: dict[tuple[str, date], float] = {}

    def rate_to_hkd(self, currency: str, on_date: date) -> float | None:
        currency = currency.upper()
        if currency == "HKD":
            return 1.0
        src = self._eur_to(currency, on_date)
        hkd = self._eur_to("HKD", on_date)
        if src is None or hkd is None:
            return None
        return hkd / src

    def _eur_to(self, currency: str, on_date: date) -> float | None:
        for offset in range(0, 7):
            actual_date = on_date - timedelta(days=offset)
            cache_key = (currency, actual_date)
            if cache_key in self.cache:
                return self.cache[cache_key]
            value = self._fetch_daily_rate(currency, actual_date)
            if value is not None:
                self.cache[cache_key] = value
                return value
        return None

    def _fetch_daily_rate(self, currency: str, on_date: date) -> float | None:
        # Example series: D.USD.EUR.SP00.A
        url = f"{ECB_FX_URL}/D.{currency}.EUR.SP00.A"
        params = {
            "startPeriod": on_date.isoformat(),
            "endPeriod": on_date.isoformat(),
            "format": "jsondata",
        }
        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except RequestException:
            return None
        series = payload.get("dataSets", [{}])[0].get("series", {})
        for entry in series.values():
            observations = entry.get("observations", {})
            if observations:
                first = next(iter(observations.values()))
                return float(first[0])
        return None


def clean_code(raw: str) -> str:
    value = str(raw).replace(".HK", "").replace("HK", "").strip()
    return value.zfill(5) if value.isdigit() else value


def parse_jsonp(text: str) -> dict:
    start = text.find("(")
    end = text.rfind(")")
    if start == -1 or end == -1:
        raise RuntimeError("unexpected JSONP payload")
    return json.loads(text[start + 1 : end])


def load_queue(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["second_pass_queue"]


def period_search_window(period_label: str) -> tuple[date, date]:
    if period_label.endswith("年报"):
        year = int(period_label[:4]) + 1
        return date(year - 1, 4, 1), date(year, 6, 30)
    if period_label.endswith("中报"):
        year = int(period_label[:4])
        return date(year, 7, 1), date(year, 10, 31)
    if period_label.endswith("三季报"):
        year = int(period_label[:4])
        return date(year, 10, 1), date(year, 12, 31)
    if period_label.endswith("一季报"):
        year = int(period_label[:4])
        return date(year, 4, 1), date(year, 6, 30)
    raise ValueError(f"unknown period {period_label}")


def score_result(result: SearchResult, period_label: str) -> int:
    lower_title = result.title.lower()
    score = 0
    if "clarification announcement" in lower_title:
        score -= 20
    for marker in REPORT_KEYWORDS.get(period_label[4:], []):
        if marker in lower_title:
            score += 10
    target_year = int(period_label[:4])
    if str(target_year) in lower_title:
        score += 3
    if period_label.endswith("年报") and any(
        token in lower_title for token in [f"{target_year-1}/{target_year}", f"{target_year-1}-{target_year}"]
    ):
        score += 5
    if "results" in lower_title:
        score += 2
    if result.file_type == "PDF":
        score += 1
    return score


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 20) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages[:max_pages]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def extract_pdf_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def detect_currency(text: str) -> str | None:
    sample = text[:15000]
    for code, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, sample, flags=re.IGNORECASE):
                return code
    return None


def detect_unit_multiplier(text: str) -> int:
    sample = text[:20000]
    for pattern, multiplier in UNIT_PATTERNS:
        if pattern.search(sample):
            return multiplier
    return 1


def parse_numeric_token(token: str) -> float | None:
    token = token.strip()
    if not token or token in {"-", "--", "—"}:
        return None
    negative = False
    if token.startswith("(") and token.endswith(")"):
        negative = True
        token = token[1:-1]
    token = token.replace(",", "").replace(" ", "")
    if token.startswith("-"):
        negative = True
        token = token[1:]
    try:
        value = float(token)
    except ValueError:
        return None
    return -value if negative else value


def numbers_from_text(text: str) -> list[float]:
    values = []
    for token in re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", text):
        parsed = parse_numeric_token(token)
        if parsed is not None:
            values.append(parsed)
    return values


def choose_line_numeric_values(line: str) -> list[float]:
    values = numbers_from_text(line)
    if len(values) >= 3 and abs(values[0]) <= 100 and float(values[0]).is_integer():
        return values[1:]
    return values


def has_placeholder_before_value(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("-") or stripped.startswith("–") or stripped.startswith("—")


def tail_after_alias(text: str, alias: str) -> str:
    match = re.search(re.escape(alias), text, flags=re.IGNORECASE)
    if not match:
        return text
    return text[match.end() :]


def has_negated_borrowings_context(text: str) -> bool:
    normalized = normalize_ws(text).lower()
    return any(pattern.search(normalized) for pattern in BORROWING_NEGATION_PATTERNS)


def is_false_positive_current_liability_hit(metric: str, alias: str, text: str) -> bool:
    if metric != "短期借款":
        return False
    if alias.lower() not in {"amount due within one year", "repayable within one year"}:
        return False
    normalized = normalize_ws(text).lower()
    has_non_borrowing_term = any(term in normalized for term in NON_BORROWING_CURRENT_LIABILITY_TERMS)
    has_borrowing_term = any(term in normalized for term in BORROWING_CONTEXT_TERMS)
    return has_non_borrowing_term and not has_borrowing_term


def should_skip_metric_hit(metric: str, alias: str, text: str) -> bool:
    if metric in {"短期借款", "长期借款"} and has_negated_borrowings_context(text):
        return True
    return is_false_positive_current_liability_hit(metric, alias, text)


def record_line_hit(
    hits: list[dict],
    alias: str,
    line: str,
    raw_value: float,
    multiplier: int,
    fx_to_hkd: float | None,
) -> None:
    normalized = raw_value * multiplier
    hits.append(
        {
            "alias": alias,
            "snippet": normalize_ws(line),
            "raw_value": raw_value,
            "normalized_value": normalized,
            "value_hkd": normalized * fx_to_hkd if fx_to_hkd is not None else None,
        }
    )


def metric_context_aliases(metric: str) -> tuple[list[str], list[str]]:
    if metric == "长期借款":
        return (
            [
                "amount due after one year",
                "repayable after one year",
                "non-current liabilities",
                "non-current borrowings",
            ],
            [
                "borrowings",
                "bank loans and other borrowings",
                "bank and other borrowings",
                "bank and other loans",
                "interest-bearing bank and other borrowings",
            ],
        )
    if metric == "短期借款":
        return (
            [
                "amount due within one year",
                "repayable within one year",
                "current liabilities",
                "current borrowings",
            ],
            [
                "borrowings",
                "bank borrowings",
                "bank and other borrowings",
                "bank and other loans",
            ],
        )
    if metric == "资本性支出":
        return (
            [
                "capital expenditure contracted for",
                "capital commitments",
                "capital expenditure",
                "purchase of property, plant and equipment",
                "additions to property, plant and equipment",
            ],
            [],
        )
    return ([], [])


def metric_text_aliases(metric: str) -> list[str]:
    aliases = list(METRIC_ALIASES.get(metric, [metric]))
    if metric == "长期借款":
        banned = {
            "bank loans and other borrowings",
            "bank and other borrowings",
            "bank and other loans",
            "interest-bearing bank and other borrowings",
        }
        return [alias for alias in aliases if alias not in banned]
    if metric == "短期借款":
        banned = {
            "bank borrowings",
            "bank and other borrowings",
            "bank and other loans",
        }
        return [alias for alias in aliases if alias not in banned]
    return aliases


def find_metric_amounts_by_lines(
    lines: list[str],
    metrics: Iterable[str],
    multiplier: int,
    fx_to_hkd: float | None,
) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {metric: [] for metric in metrics}
    lower_lines = [line.lower() for line in lines]

    for metric in metrics:
        direct_aliases = METRIC_ALIASES.get(metric, [metric])
        primary_aliases, contextual_aliases = metric_context_aliases(metric)
        hits: list[dict] = []

        for index, line in enumerate(lines):
            lower = lower_lines[index]
            matched_alias = next((alias for alias in direct_aliases if alias.lower() in lower), None)
            if matched_alias is None:
                continue
            if should_skip_metric_hit(metric, matched_alias, line):
                continue
            tail = tail_after_alias(line, matched_alias)
            if has_placeholder_before_value(tail):
                continue
            values = choose_line_numeric_values(line)
            if values:
                record_line_hit(hits, matched_alias, line, values[0], multiplier, fx_to_hkd)
                if len(hits) >= 5:
                    break
                continue

            window = " ".join(lines[index : index + 3])
            if should_skip_metric_hit(metric, matched_alias, window):
                continue
            values = choose_line_numeric_values(window)
            if values:
                record_line_hit(hits, matched_alias, window, values[0], multiplier, fx_to_hkd)
                if len(hits) >= 5:
                    break

        if hits:
            results[metric] = hits
            continue

        if not primary_aliases:
            continue

        for index, line in enumerate(lines):
            lower = lower_lines[index]
            matched_primary = next((alias for alias in primary_aliases if alias.lower() in lower), None)
            if matched_primary is None:
                continue

            window_lines = lines[index : index + 4]
            window_lower = " ".join(item.lower() for item in window_lines)
            matched_context = next(
                (alias for alias in contextual_aliases if alias.lower() in window_lower),
                None,
            )
            if matched_context is None and contextual_aliases:
                continue

            candidate_line = None
            for probe in window_lines:
                if matched_context and matched_context.lower() in probe.lower():
                    candidate_line = probe
                    break
            if candidate_line is None:
                candidate_line = " ".join(window_lines)
            if should_skip_metric_hit(metric, matched_context or matched_primary, candidate_line):
                continue
            if matched_context:
                tail = tail_after_alias(candidate_line, matched_context)
                if has_placeholder_before_value(tail):
                    continue
            values = choose_line_numeric_values(candidate_line)
            if not values:
                continue
            alias = f"{matched_primary} + {matched_context}" if matched_context else matched_primary
            record_line_hit(hits, alias, candidate_line, values[0], multiplier, fx_to_hkd)
            if len(hits) >= 5:
                break

        results[metric] = hits

    return results


def find_metric_amounts(text: str, metrics: Iterable[str], multiplier: int, fx_to_hkd: float | None) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {}
    number_pattern = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
    for metric in metrics:
        hits = []
        for alias in metric_text_aliases(metric):
            for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
                tail = text[match.end() : min(len(text), match.end() + 24)]
                if has_placeholder_before_value(tail):
                    continue
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 160)
                snippet = text[start:end]
                if should_skip_metric_hit(metric, alias, snippet):
                    continue
                numeric_tokens = number_pattern.findall(snippet)
                parsed = [parse_numeric_token(token) for token in numeric_tokens]
                parsed = [value for value in parsed if value is not None]
                if not parsed:
                    continue
                raw_value = parsed[0]
                normalized = raw_value * multiplier
                value_hkd = normalized * fx_to_hkd if fx_to_hkd is not None else None
                hits.append(
                    {
                        "alias": alias,
                        "snippet": normalize_ws(snippet),
                        "raw_value": raw_value,
                        "normalized_value": normalized,
                        "value_hkd": value_hkd,
                    }
                )
                if len(hits) >= 3:
                    break
            if hits:
                break
        results[metric] = hits
    return results


def merge_metric_amounts(*sources: dict[str, list[dict]]) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = {}
    seen: dict[str, set[tuple[float, str]]] = {}
    for source in sources:
        for metric, hits in source.items():
            merged.setdefault(metric, [])
            seen.setdefault(metric, set())
            for hit in hits:
                key = (
                    round(hit["normalized_value"], 6),
                    normalize_ws(hit["snippet"])[:160],
                )
                if key in seen[metric]:
                    continue
                seen[metric].add(key)
                merged[metric].append(hit)
    return merged


def aggregate_cash_components(amounts: dict[str, list[dict]]) -> dict:
    components = {}
    found_count = 0
    total_hkd = 0.0
    total_native = 0.0
    has_primary = False
    for name in CASH_COMPONENTS:
        hits = amounts.get(name, [])
        if hits:
            chosen = choose_distinct_amount_hit(hits)
            if chosen is None:
                components[name] = None
                continue
            found_count += 1
            components[name] = chosen
            total_native += chosen["normalized_value"]
            if chosen["value_hkd"] is not None:
                total_hkd += chosen["value_hkd"]
            if name == "现金及现金等价物":
                has_primary = True
        else:
            components[name] = None
    status = "missing"
    if has_primary and found_count >= 2:
        status = "strong"
    elif has_primary:
        status = "base"
    elif found_count > 0:
        status = "weak"
    return {
        "status": status,
        "found_components": found_count,
        "has_primary": has_primary,
        "components": components,
        "total_native": total_native if found_count else None,
        "total_hkd": total_hkd if found_count else None,
    }


def choose_distinct_amount_hit(hits: list[dict]) -> dict | None:
    seen = set()
    for hit in hits:
        key = (
            round(hit["normalized_value"], 6),
            normalize_ws(hit["snippet"])[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        return hit
    return None


def detect_zero_borrowing_candidates(text: str, metrics: Iterable[str]) -> dict[str, dict]:
    normalized = normalize_ws(text)
    lower_metrics = set(metrics)
    candidates: dict[str, dict] = {}
    for rule in ZERO_BORROWING_RULES:
        if not lower_metrics.intersection(rule["metrics"]):
            continue
        match = rule["pattern"].search(normalized)
        if not match:
            continue
        snippet = normalize_ws(normalized[max(0, match.start() - 40) : min(len(normalized), match.end() + 120)])
        for metric in rule["metrics"]:
            if metric not in lower_metrics or metric in candidates:
                continue
            candidates[metric] = {
                "status": "zero_explicit",
                "confidence": "high",
                "value_hkd": 0.0,
                "value_native": 0.0,
                "alias": rule["alias"],
                "snippet": snippet,
            }
    return candidates


def confidence_for_metric_hit(metric: str, hit: dict) -> str:
    score = score_metric_hit(metric, hit)
    if metric in {"长期借款", "短期借款", "资本性支出"}:
        return "high" if score >= 20 else "medium"
    return "high" if score >= 10 else "medium"


def score_metric_hit(metric: str, hit: dict) -> int:
    alias = hit.get("alias", "").lower()
    snippet = hit.get("snippet", "").lower()
    raw_value = abs(hit.get("raw_value") or 0)
    score = 0

    if metric == "长期借款":
        if any(token in alias or token in snippet for token in ["after one year", "non-current liabilities", "non-current borrowings"]):
            score += 30
        if any(token in alias or token in snippet for token in ["bank loans and other", "interest-bearing bank and other"]):
            score += 20
        if "borrowings" in alias:
            score += 8
        if "total assets less current liabilities" in snippet:
            score -= 20
        if any(token in snippet for token in ["interest on", "total borrowings", "external borrowings", "fair value of such borrowings"]):
            score -= 25
        if raw_value and 1900 <= raw_value <= 2100 and any(token in snippet for token in ["june", "december", "2025", "2024", "2026"]):
            score -= 40
        if hit.get("raw_value", 0) < 0:
            score -= 25

    elif metric == "短期借款":
        if any(token in alias or token in snippet for token in ["within one year", "current liabilities", "current borrowings"]):
            score += 30
        if "current portion" in alias or "current portion" in snippet:
            score += 20
        if "borrowings" in alias:
            score += 8
        if any(token in snippet for token in ["interest on", "total borrowings", "external borrowings"]):
            score -= 25
        if raw_value and 1900 <= raw_value <= 2100 and any(token in snippet for token in ["june", "december", "2025", "2024", "2026"]):
            score -= 40
        if hit.get("raw_value", 0) < 0:
            score -= 25

    elif metric == "资本性支出":
        if any(token in snippet for token in ["contracted for", "amounted to", "capital commitments"]):
            score += 30
        if "purchase of property, plant and equipment" in alias or "additions to property, plant and equipment" in alias:
            score += 20
        if "capital expenditure" in alias:
            score += 10
        if "% of sales" in snippet:
            score -= 40
        if "funded from cash on hand" in snippet:
            score -= 25
        if raw_value and 1900 <= raw_value <= 2100 and "2025" in snippet:
            score -= 40

    else:
        if raw_value and 1900 <= raw_value <= 2100 and any(token in snippet for token in ["2025", "2024", "2026"]):
            score -= 25

    if raw_value >= 1_000:
        score += 5
    if raw_value >= 1_000_000:
        score += 5
    return score


def choose_metric_candidate(metric: str, amounts: dict[str, list[dict]]) -> dict | None:
    hits = amounts.get(metric, [])
    if not hits:
        return None
    ranked = sorted(
        hits,
        key=lambda hit: (score_metric_hit(metric, hit), abs(hit.get("normalized_value", 0))),
        reverse=True,
    )
    min_score = 1 if metric in {"长期借款", "短期借款", "资本性支出"} else -10
    for hit in ranked:
        if score_metric_hit(metric, hit) >= min_score:
            return hit
    return None


def build_supplement_candidates(target: dict, doc: dict) -> dict:
    candidates = {}
    for metric in target["core_missing"]:
        if metric == "总现金":
            cash = doc.get("cash_rebuild")
            if cash and cash["status"] in {"strong", "base"}:
                candidates[metric] = {
                    "status": cash["status"],
                    "confidence": "high" if cash["status"] == "strong" else "medium",
                    "value_hkd": cash["total_hkd"],
                    "value_native": cash["total_native"],
                    "components": cash["components"],
                }
            continue
        chosen = choose_metric_candidate(metric, doc["metric_amounts"])
        if chosen is not None:
            candidates[metric] = {
                "status": "direct",
                "confidence": confidence_for_metric_hit(metric, chosen),
                "value_hkd": chosen["value_hkd"],
                "value_native": chosen["normalized_value"],
                "alias": chosen["alias"],
                "snippet": chosen["snippet"],
            }
            continue
        zero_candidate = doc.get("zero_borrowing_candidates", {}).get(metric)
        if zero_candidate is not None:
            candidates[metric] = zero_candidate
    return candidates


def find_metric_snippets(text: str, metrics: Iterable[str], radius: int = 80) -> dict[str, list[str]]:
    snippets: dict[str, list[str]] = {}
    for metric in metrics:
        found = []
        for alias in METRIC_ALIASES.get(metric, [metric]):
            for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
                start = max(0, match.start() - radius)
                end = min(len(text), match.end() + radius)
                found.append(normalize_ws(text[start:end]))
                if len(found) >= 3:
                    break
            if found:
                break
        snippets[metric] = found
    return snippets


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def broad_search_window(period_label: str) -> tuple[date, date]:
    year = int(period_label[:4])
    return date(year, 1, 1), date(year + 1, 12, 31)


def choose_best_documents(
    results: list[SearchResult],
    period_label: str,
    target_start: date,
    target_end: date,
    limit: int,
) -> list[SearchResult]:
    period_key = period_label[4:]
    target_year = int(period_label[:4])
    windowed = [
        item
        for item in results
        if target_start <= item.date_time.date() <= target_end
    ]
    filtered = [
        item
        for item in windowed
        if not any(noise in item.title.lower() for noise in NOISE_KEYWORDS)
    ]
    keyword_hits = [
        item
        for item in filtered
        if any(keyword in item.title.lower() for keyword in REPORT_KEYWORDS.get(period_key, []))
        and (
            str(target_year) in item.title
            or (
                period_label.endswith("年报")
                and (
                    f"{target_year-1}/{target_year}" in item.title
                    or f"{target_year-1}-{target_year}" in item.title
                )
            )
        )
    ]
    pool = keyword_hits
    ranked = sorted(pool, key=lambda item: (score_result(item, period_label), item.date_time), reverse=True)
    return ranked[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-json", default=str(QUEUE_PATH))
    parser.add_argument("--limit", type=int, default=0, help="How many queue items to probe; 0 means no limit")
    parser.add_argument("--docs-per-stock", type=int, default=2)
    parser.add_argument("--queue-types", nargs="*", default=DEFAULT_QUEUE_TYPES)
    parser.add_argument("--out", default=str(OUTPUT_DIR / "sample_probe.json"))
    args = parser.parse_args()

    queue = load_queue(Path(args.queue_json))
    filtered_targets = [item for item in queue if item["queue_type"] in set(args.queue_types)]
    targets = filtered_targets[: args.limit] if args.limit else filtered_targets

    hkex = HkexNewsClient()
    fx = EcbFxClient()
    out_dir = Path(args.out).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    report = []
    summary = {
        "targets": len(targets),
        "doc_hit": 0,
        "candidate_hit": 0,
        "by_type": {},
    }
    for target in targets:
        canonical_code, resolved_name, stock_id = hkex.resolve_stock_id(target["code"])
        start, end = period_search_window(target["period"])
        broad_start, broad_end = broad_search_window(target["period"])
        results = hkex.search_documents(stock_id, broad_start, broad_end)
        docs = choose_best_documents(results, target["period"], start, end, args.docs_per_stock)

        doc_reports = []
        for index, doc in enumerate(docs, start=1):
            binary = hkex.download(doc.file_link)
            file_path = out_dir / f"{clean_code(target['code'])}_{target['period']}_{index}.pdf"
            file_path.write_bytes(binary)
            text = extract_pdf_text(binary)
            lines = extract_pdf_lines(text)
            currency = detect_currency(text)
            fx_rate = fx.rate_to_hkd(currency, doc.date_time.date()) if currency else None
            unit_multiplier = detect_unit_multiplier(text)
            snippets = find_metric_snippets(text, target["core_missing"] + target["optional_missing"])
            metrics_for_amounts = list(dict.fromkeys(target["core_missing"] + target["optional_missing"] + CASH_COMPONENTS))
            amounts = merge_metric_amounts(
                find_metric_amounts_by_lines(lines, metrics_for_amounts, unit_multiplier, fx_rate),
                find_metric_amounts(text, metrics_for_amounts, unit_multiplier, fx_rate),
            )
            cash_rebuild = aggregate_cash_components(amounts) if "总现金" in target["core_missing"] else None
            zero_borrowing_candidates = detect_zero_borrowing_candidates(text, target["core_missing"])
            doc_reports.append(
                {
                    "title": doc.title,
                    "date_time": doc.date_time.isoformat(),
                    "file_type": doc.file_type,
                    "file_info": doc.file_info,
                    "file_link": doc.file_link,
                    "local_path": str(file_path),
                    "detected_currency": currency,
                    "unit_multiplier": unit_multiplier,
                    "fx_to_hkd": fx_rate,
                    "metric_snippets": snippets,
                    "metric_amounts": amounts,
                    "cash_rebuild": cash_rebuild,
                    "zero_borrowing_candidates": zero_borrowing_candidates,
                }
            )

        supplement_candidates = build_supplement_candidates(target, doc_reports[0]) if doc_reports else {}
        queue_type = target["queue_type"]
        summary["by_type"].setdefault(queue_type, {"targets": 0, "doc_hit": 0, "candidate_hit": 0})
        summary["by_type"][queue_type]["targets"] += 1
        if doc_reports:
            summary["doc_hit"] += 1
            summary["by_type"][queue_type]["doc_hit"] += 1
        if supplement_candidates:
            summary["candidate_hit"] += 1
            summary["by_type"][queue_type]["candidate_hit"] += 1

        report.append(
            {
                "target": target,
                "resolved_code": canonical_code,
                "resolved_name": resolved_name,
                "stock_id": stock_id,
                "search_window": {"start": start.isoformat(), "end": end.isoformat()},
                "broad_search_window": {"start": broad_start.isoformat(), "end": broad_end.isoformat()},
                "candidate_count": len(results),
                "documents": doc_reports,
                "supplement_candidates": supplement_candidates,
            }
        )

    payload = {"summary": summary, "records": report}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"probe written: {args.out}")
    print(f"targets: {len(report)}")
    print(f"doc_hit: {summary['doc_hit']}")
    print(f"candidate_hit: {summary['candidate_hit']}")
    for item in report:
        print(
            f"{item['target']['code']} {item['target']['name']} [{item['target']['period']}] "
            f"candidates={item['candidate_count']} docs={len(item['documents'])} "
            f"supplement={len(item['supplement_candidates'])}"
        )
        for doc in item["documents"]:
            hits = sum(1 for snippets in doc["metric_snippets"].values() if snippets)
            amount_hits = sum(1 for amounts in doc["metric_amounts"].values() if amounts)
            cash_status = doc["cash_rebuild"]["status"] if doc.get("cash_rebuild") else "-"
            print(
                f"  - {doc['date_time']} {doc['title'][:70]} "
                f"| currency={doc['detected_currency']} unit={doc['unit_multiplier']} "
                f"fx={doc['fx_to_hkd']} metric_hits={hits} amount_hits={amount_hits} cash={cash_status}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
