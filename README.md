# HK Stocks Dashboard

港股数据看板 —— 自动生成自包含 HTML 文件，内嵌 JSON 数据与全部 JS/CSS，无需服务器即可直接在浏览器中打开。

## 文件说明

| 文件 | 说明 |
|------|------|
| `build_html.py` | 核心脚本，读取 JSON 数据，生成 `hk_stocks.html` |
| `hk_stocks_data_new.json` | 港股原始数据源（757 只股票） |
| `scrape_iwencai.py` | 数据抓取脚本（问财网） |
| `recv_server.py` | 本地接收服务器，用于接收浏览器端传来的分块数据 |
| `assemble_data.py` | 将分块数据拼装成完整 JSON |

## 快速开始

### 环境要求

- Python 3.8+（仅使用标准库，无需额外安装依赖）

### 生成看板

```bash
python3 build_html.py
```

生成 `hk_stocks.html`（约 1.5MB），直接用浏览器打开即可。

## 计算指标说明

`build_html.py` 通过 `COMPUTED_COL_DEFS` 驱动所有计算列（当前共 28 列，索引 10–37）：

| 指标 | 说明 |
|------|------|
| TTM归母净利润 | 最近四个季度净利润之和 |
| TTM净利同比 | 与去年同期 TTM 净利的增长率 |
| TTMROE / TTMROIC | TTM 股东权益回报率 / 投入资本回报率 |
| TTM经营/投资/融资现金流 | 最近四季度各类现金流 |
| 净现金 | 总现金 - 短期借款 - 长期借款（金融股为空，缺失字段视为 0） |
| 有息负债 | 短期借款 + 长期借款（金融股为空，缺失字段视为 0） |
| TTMFCF | max(OCF+资本支出, OCF+投资现金流) |
| 股东收益率 | TTMFCF ÷ (总市值 + 净现金) × 100% |
| 股东回报分配率 | 预期25股东回报 ÷ TTM归母净利润 × 100% |
| 低估排序分 | 金融股按PE升序，非金融股按股东收益率降序（标准竞争排名） |
| 成长排序分 | 按TTM净利同比降序（金融/非金融各自排名） |
| 质量排序分 | 金融股按TTMROE，非金融股按TTMROIC降序 |
| 股东回报排序分 | 按股东回报分配率降序，负值/空值排末位 |
| 综合分数 | 低估×0.4 + 成长×0.2 + 质量×0.2 + 回报×0.2 |

## 核心架构

```
COMPUTED_COL_DEFS (28 列)
    ↓
compute_phase1(obj)        # 逐行计算，idx 10–32
    ↓
compute_rankings(list)     # 跨行排名，idx 33–37
    ↓
hk_stocks.html             # 自包含 HTML 输出
```

- `PERIOD_START = 10 + len(COMPUTED_COL_DEFS)`（自动计算，当前=38）
- 金融股：`JINRONG_SET = {'保险', '其他金融', '银行'}` + 综合企业中的中信股份
- 排名算法：标准竞争排名（1224 式，并列同分，后续跳位）
