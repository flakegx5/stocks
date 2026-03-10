# 项目说明 - HK Stocks Dashboard

## 首次进入项目必做

```bash
git pull   # 先同步最新代码，再开始工作
```

## 完成工作后必做

```bash
git add -A
git commit -m "简要描述本次改动"
git push
```

---

## 项目路径

本项目位于 `/Users/flakeliu/claude/stocks/`（本地），或其他设备 clone 后的根目录。

## 核心文件

### 数据源（两层架构）
- **`hk_stocks_data_new.json`** — 稳定财务数据（iwencai 抓取，每季度更新），不要手动修改
- **`hk_stocks_market.json`** — 易变市场数据（AKShare 每日更新），由 `update_market.py` 生成

### 脚本
- **`build_html.py`** — 唯一需要编辑的核心文件（约1300行）。加载两个 JSON，注入市场数据，计算所有派生列，输出 `index.html` + `data.js`
- **`scrape_iwencai_xhr.py`** — 自动抓取 iwencai 港股数据（Playwright），支持 `--login/--debug/--build`
- **`update_market.py`** — 每日行情更新脚本。从 AKShare 获取最新价/涨跌幅，计算总市值，保存至 `hk_stocks_market.json`
- **`daily_update.sh`** — 每日自动化脚本：依次运行 `update_market.py` → `build_html.py`，可选 `--push` 自动提交

### 输出（前后端分离架构）
- **`index.html`** — 静态模板（~29KB，CSS + JS 逻辑），在 git 中
- **`data.js`** — 构建时数据（~1.6MB，所有表格数据+计算常量），在 git 中
- `index.html` 通过 `<script src="data.js">` 加载数据，本地双击可直接打开

生成命令：`python3 build_html.py`
输出：`index.html`（~29KB）+ `data.js`（~1.6MB）
在线访问：https://flakegx5.github.io/stocks/

---

## 每日行情更新（AKShare）

### 快速运行

```bash
cd /Users/flakeliu/claude/stocks
python3 update_market.py          # 更新行情数据 JSON
python3 build_html.py             # 重建 HTML
# 或一键执行：
./daily_update.sh --push          # 更新 + 重建 + git push
```

### 建议 crontab（港股收盘后 16:30 HKT）

```
30 16 * * 1-5  /Users/flakeliu/claude/stocks/daily_update.sh --push >> /tmp/hk_stocks_daily.log 2>&1
```

### 数据来源与局限性

| 字段 | 来源 | 更新频率 |
|------|------|---------|
| 最新价、涨跌幅 | AKShare `stock_hk_spot_em` | 每日 |
| 总市值 | 最新价 × 总股本（总股本来自 iwencai） | 每日（AKShare 注入后） |
| **PE(TTM)** | **动态计算 = 总市值 ÷ TTM归母净利润** | **每日（随市值自动更新）** |
| **PB** | **动态计算 = 总市值 ÷ 净资产（最新财报期）** | **每日（iwencai 重抓后包含净资产时）** |
| 净资产（PB分母） | iwencai 财务数据 | 每季度 |
| 其他财务数据（净利润、ROE 等） | iwencai 原始数据 | 每季度 |

> **PE/PB 动态计算说明**：
> - PE(TTM) = 总市值 ÷ TTM归母净利润（利润 > 0 时有效；亏损股 fallback 到 iwencai 静态值）
> - PB = 总市值 ÷ 净资产（取最近有数据的财报期，fallback 到 iwencai 静态值）
> - 净资产字段由 `_NET_ASSETS_CANDIDATES` 列表自动探测，iwencai 重抓后无需手动配置

### 市场数据注入（级联更新）

`build_html.py` 在运行时自动加载 `hk_stocks_market.json`，用最新数据覆盖 iwencai 原始值，
然后从头重新计算所有派生列。因此更新行情后，以下链式计算自动刷新：

```
mkt_cap（最新价×总股本）
  → 股东收益率 = TTMFCF / (mkt_cap + 净现金)
    → 低估排名（非金融股）
      → 综合排名

PE(TTM)
  → 低估排名（金融股）
    → 综合排名
```

---

## 数据更新流程（抓取新财务数据）

### 问财查询 URL（直接在浏览器打开）

```
https://www.iwencai.com/unifiedwap/result?w=港股范围内，市值大于50亿港元，列出最新pe、pb、总股本、所属行业，列出2023年一季报和2025年年报的分别以下数字，包括：归母净利润、总现金、流动资产、总负债、短期借款、长期借款、ROE、ROIC、经营活动现金流净额、投资活动现金流净额、资本性支出、融资活动现金流量净额、年度分红、现金流量表中的股份回购、现金流量表中的支付股息，归母净利润同比增速。&querytype=hkstock
```

> **注意**：iwencai 会返回请求区间内所有报期的数据。起始报期固定为"2023年一季报"（保证有足够历史数据做 TTM）；**结束报期随最新数据更新**，当前为"2025年年报"，下次有新季报时改为"2025年一季报"等。

### 操作步骤

**第一步：启动接收服务器**（新终端窗口，保持运行）
```bash
cd /Users/flakeliu/claude/stocks
./run_server.sh
```

**第二步：在 Chrome 打开上面的问财 URL，等数据表格加载完毕**

**第三步：打开 DevTools (F12) → Console，粘贴 `scraper_browser.js` 全文并回车**

脚本会提示：`请手动点击"第2页"按钮` → 点击一次翻页，脚本自动捕获 API 后飞速拉取所有页。

**第四步：看到 `✅ DONE` 后，终端会显示 `Saved XXX rows`**

**第五步：重新生成 HTML 并提交**
```bash
python3 build_html.py
git add hk_stocks_data_new.json build_html.py
git commit -m "数据更新: YYYY-MM-DD"
git push
```

### 说明

- 脚本通过**拦截浏览器自身的 fetch/XHR 请求**获取 API endpoint 和鉴权参数（cookie、comp_id 等），无需手动配置任何 token
- 直接调用内部 API，每页约 0.2 秒，15页全部完成约 3-5 秒，数据精准无截断
- 每次会话的 `comp_id` 和 session token 会变，因此脚本需要每次重新捕获（不能写死）
- `run_server.sh` 确保服务器从项目目录启动，数据保存到正确位置

---

## 架构要点

### 计算列（COMPUTED_COL_DEFS，当前28列，idx 10–37）
新增/删除计算列时只需修改此列表，`PERIOD_START` 会自动重算。

### 两阶段计算流水线
```
compute_phase1(obj)       → 逐行计算，idx 10–32（含净现金、FCF、股东收益率等）
compute_rankings(list)    → 跨行排名，idx 33–37（低估/成长/质量/股东回报/综合）
```

### 金融股判断
```python
JINRONG_SET = {'保险', '其他金融', '银行'}
# + 综合企业中含"中信股份"的股票
```

### MKT_KEY_* 易变字段常量

`build_html.py` 顶部定义所有易变字段的 key，避免散落在代码各处。若 iwencai 抓取的字段名包含日期变了，只需改这里：

```python
MKT_KEY_PRICE  = '港股@最新价'
MKT_KEY_CHG    = '港股@最新涨跌幅'
MKT_KEY_MKTCAP = '港股@总市值[20260309]'     # 含日期，需随抓取日期更新
MKT_KEY_PE     = '港股@市盈率(pe,ttm)[20260306]'
MKT_KEY_PB     = '港股@市净率(pb)[20260309]'
MKT_KEY_SHARES = '港股@总股本[20260309]'      # update_market.py 同步引用此 key
```

> **重要**：`update_market.py` 中的 `SHARES_KEY` 必须与 `build_html.py` 的 `MKT_KEY_SHARES` 保持一致。

### 索引常量（自动计算，勿手动修改）
```python
PERIOD_START    = 10 + len(COMPUTED_COL_DEFS)   # 当前 = 38
N_PERIODS       = len(PERIOD_DATES)              # 当前 = 12（最新为 2025年报）
TTMROE_IDX_PY   = 10 + COMPUTED_COL_DEFS.index('TTMROE')    # = 18
TTMROIC_IDX_PY  = 10 + COMPUTED_COL_DEFS.index('TTMROIC')   # = 19
# 各报期的年报位置通过 _PLABELS.index('2024年报') 动态查找，勿硬编码
```

### 空值处理规则
- **净现金**：总现金/短期借款/长期借款各项为空均视为 0（金融股→空）
- **有息负债**：短期借款/长期借款各项为空均视为 0（金融股→空）
- **流动资产/总负债**：为空则保持空，不参与任何衍生计算
- **预期25年度分红**：
  - 有25年报财务数据（归母净利润存在）→ 直接等于25年报年度分红（无分红则为空）
  - 无25年报财务数据 → 按旧方法估算：2024年度分红 × (1 + TTM净利同比/100)，结果为负则为空
- **TTM股份回购/TTM支付股息/预期25年度分红**：参与计算时 None 视为 0，避免一项缺失导致整体为空
- **预期25股东回报**：= 预期25年度分红（None→0）+ |TTM股份回购|（None→0）/2，结果可为 0

### 排名规则（标准竞争排名，1224式）
- 低估：金融股按 PE 升序（PE≤0不参与，None不参与）；非金融股按股东收益率降序（≤0不参与，None不参与）
- 成长：金融/非金融各自按 TTM净利同比 降序（None视为0参与，全员有排名）
- 质量：金融股按 TTMROE 降序，非金融股按 TTMROIC 降序（None不参与，排名为空）
- 股东回报：按股东回报分配率降序，>0 正常排名；≤0 或 None → 末位（=队列总人数）
- 综合：低估×0.4 + 成长×0.2 + 质量×0.2 + 回报×0.2（任一子项为空则综合为空）

---

## 默认隐藏列（COMPUTED_HIDE_DEFAULT）
```python
{'TTM股份回购', 'TTM支付股息', '预期25年度分红',
 '最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款'}
```

## JS 亿单位列（COMPUTED_YI_COLS）
索引：11, 13, 14, 15, 16, 17, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30
