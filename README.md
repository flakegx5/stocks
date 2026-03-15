# HK Stocks Dashboard

港股数据看板 —— 市值 ≥50 亿港元的港股，展示财务数据、TTM 指标、排名评分等。

**在线访问**：https://flakegx5.github.io/stocks/

本地使用：直接双击 `index.html` 用浏览器打开（与 `data.js` 放在同一目录即可）。

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `build_html.py` | 核心构建脚本，读取 JSON 数据，生成 `index.html` + `data.js` |
| `scrape_iwencai_xhr.py` | 数据抓取脚本（问财网，Playwright 无头浏览器） |
| `hk_stocks_data_new.json` | 原始数据（iwencai 抓取结果，~760 只股票） |
| `index.html` | 静态模板（~29KB，CSS + JS 逻辑） |
| `data.js` | 构建产出数据（~1.6MB，表格数据 + 计算常量） |

## 快速开始

### 环境要求

```bash
pip3 install playwright
python3 -m playwright install chromium
python3 -m pip install --user pypdf requests
```

### 抓取数据并更新

```bash
# 首次登录（需可视化浏览器，只做一次）
python3 scrape_iwencai_xhr.py --login

# 日常更新（抓取 + 构建 + 推送）
python3 scrape_iwencai_xhr.py --build --push
```

### 仅重建 HTML（不重新抓取）

```bash
python3 build_html.py
```

### 二次补抓（HKEXnews）

当前二次补抓逻辑只生成候选补充数据与统计结果，不直接回写 `hk_stocks_data_new.json`。

```bash
# 先生成缺口审计与二次补抓队列
python3 scripts/audit_missing_financials.py \
  --write-json debug_responses/missing_financial_audit.json

# 再跑 HKEXnews 二次补抓，输出候选补充结果
python3 scripts/hkex_second_pass.py \
  --docs-per-stock 1 \
  --queue-types only_cash only_long_debt only_short_and_long_debt only_capex \
  --out debug_responses/hkex_second_pass/final_candidates_main_gaps.json
```

输出说明：

- `debug_responses/missing_financial_audit.json`：缺口审计结果与二次补抓队列
- `debug_responses/hkex_second_pass/*.json`：HKEXnews 二次补抓候选结果
- 二次补抓结果目前只单独存储，不与主抓取数据自动合并

---

## 计算指标说明

| 指标 | 说明 |
|------|------|
| TTM归母净利润 | 最近四个季度净利润之和 |
| TTM净利同比 | 与去年同期 TTM 净利的增长率 |
| TTMROE / TTMROIC | TTM 股东权益回报率 / 投入资本回报率 |
| TTM经营/投资/融资现金流 | 最近四季度各类现金流 |
| 净现金 | 总现金 - 短期借款 - 长期借款（金融股为空） |
| TTMFCF | max(OCF+资本支出, OCF+投资现金流) |
| 股东收益率 | TTMFCF ÷ (总市值 + 净现金) × 100% |
| 股东回报分配率 | 预期25股东回报 ÷ TTM归母净利润 × 100% |
| 低估排序分 | 金融股按PE升序，非金融股按股东收益率降序 |
| 成长排序分 | 按TTM净利同比降序（金融/非金融各自排名） |
| 质量排序分 | 金融股按TTMROE，非金融股按TTMROIC降序 |
| 综合分数 | 低估×0.4 + 成长×0.2 + 质量×0.2 + 回报×0.2 |

补充说明：非金融股按统一规则计算排名；若缺少对应计算所需字段，则该维度排名或综合排名显示为空。

## 架构

```
scrape_iwencai_xhr.py   →   hk_stocks_data_new.json   →   build_html.py
      (Playwright)              (原始数据 ~7MB)            ↓            ↓
                                                       index.html   data.js
                                                       (~29KB)     (~1.6MB)
```

- `index.html` 通过 `<script src="data.js">` 加载数据，同时支持本地 `file://` 和 GitHub Pages
- MKT 日期后缀字段（总市值、PE、PB、总股本）由 `build_html.py` 自动探测，重新抓取后无需手动修改
