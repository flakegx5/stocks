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

### 数据源
- **`hk_stocks_data_new.json`** — 所有数据（iwencai 抓取，含最新价/市值/PE/PB 及历史财务），不要手动修改

### 脚本
- **`build_html.py`** — 数据处理核心（约800行）。读取 JSON，计算所有派生列，**只输出 `data.js`**（不再生成 index.html）
- **`scrape_iwencai_xhr.py`** — 自动抓取 iwencai 港股数据（Playwright 无头浏览器），支持 `--login/--debug/--build/--push`
- **`update_market.py`** — 旧版 AKShare 行情更新脚本，已不再使用（保留备用）

### 前后端分离架构
- **`index.html`** — **静态前端源文件**（HTML + CSS + JS 逻辑），改 UI 时直接编辑此文件，在 git 中
- **`data.js`** — 构建输出（所有表格数据 + 全部配置常量），由 `build_html.py` 生成，在 git 中
- `index.html` 通过 `<script src="data.js">` 加载 `window.STOCK_DATA`，本地双击可直接打开

生成命令：`python3 build_html.py`
输出：`data.js`（~1.6MB，不再生成 index.html）
在线访问：https://flakegx5.github.io/stocks/

---

## 每日行情更新（iwencai 直接抓取）

### 快速运行（手动触发）

```bash
cd /Users/flakeliu/claude/stocks
python3 scrape_iwencai_xhr.py --build --push   # 抓取 + 重建 + git push
```

### 设置 crontab 自动运行（港股收盘后 17:00）

```bash
crontab -e   # 打开 crontab 编辑器，添加以下一行：
```

```
0 17 * * 1-5  cd /Users/flakeliu/claude/stocks && python3 scrape_iwencai_xhr.py --build --push >> /tmp/hk_stocks_daily.log 2>&1
```

> 注意：iwencai session（`iwencai_session.json`）过期后需手动重新登录：
> `python3 scrape_iwencai_xhr.py --login`

### 数据来源（单一来源，无 AKShare 依赖）

| 字段 | 来源 | 更新频率 |
|------|------|---------|
| 最新价、涨跌幅、总市值、PE、PB、总股本 | iwencai 每日抓取 | 每日（crontab） |
| **PE(TTM)** | **动态计算 = 总市值 ÷ TTM归母净利润** | **每日（随市值自动更新）** |
| **PB** | **动态计算 = 总市值 ÷ 净资产** | **每日** |
| 净资产（PB分母）、净利润、ROE 等财务数据 | iwencai | 每次抓取 |

> **MKT_KEY 自动探测**：`build_html.py` 会自动从数据中找到带日期后缀的字段名（如 `港股@总市值[20260309]`），
> 重新抓取后日期变化无需手动更新任何常量。

### 级联计算

```
mkt_cap（最新价×总股本，来自iwencai）
  → 股东收益率 = TTMFCF / (mkt_cap + 净现金)
    → 低估排名（非金融股）→ 综合排名

PE(TTM)（动态计算）
  → 低估排名（金融股）→ 综合排名
```

---

## 数据更新流程（抓取新财务数据）

### 问财查询 URL（直接在浏览器打开）

```
https://www.iwencai.com/unifiedwap/result?w=港股范围内，市值大于50亿港元，列出最新pe、pb、总股本、所属行业，列出2023年一季报和2025年年报的分别以下数字，包括：归母净利润、总现金、流动资产、总负债、短期借款、长期借款、ROE、ROIC、经营活动现金流净额、投资活动现金流净额、资本性支出、融资活动现金流量净额、年度分红、现金流量表中的股份回购、现金流量表中的支付股息，归母净利润同比增速。&querytype=hkstock
```

> **注意**：iwencai 会返回请求区间内所有报期的数据。起始报期固定为"2023年一季报"（保证有足够历史数据做 TTM）；**结束报期随最新数据更新**，当前为"2025年年报"，下次有新季报时改为"2025年一季报"等。

### 操作步骤

```bash
cd /Users/flakeliu/claude/stocks

# 首次登录（只做一次，需要可视化浏览器窗口）
python3 scrape_iwencai_xhr.py --login

# 日常抓取 + 构建 + 推送
python3 scrape_iwencai_xhr.py --build --push
```

### 说明

- 使用 **Playwright 无头浏览器**自动完成登录态注入、翻页、XHR 拦截，无需手动操作
- session 保存在 `iwencai_session.json`（已加入 .gitignore），过期后重新 `--login`
- 约 16 页 × 50 行 = 760 行原始数据，构建后去重人民币柜台约 736 行

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

`build_html.py` 顶部定义所有易变字段的 key。**日期后缀字段由 `_autodetect_key()` 自动探测**，每次重新抓取后日期变化无需手动修改任何常量：

```python
MKT_KEY_PRICE  = '港股@最新价'          # 无日期后缀，固定
MKT_KEY_CHG    = '港股@最新涨跌幅'      # 无日期后缀，固定
MKT_KEY_MKTCAP = _autodetect_key(...)   # 自动找 '港股@总市值[YYYYMMDD]'
MKT_KEY_PE     = _autodetect_key(...)   # 自动找 '港股@市盈率(pe,ttm)[YYYYMMDD]'
MKT_KEY_PB     = _autodetect_key(...)   # 自动找 '港股@市净率(pb)[YYYYMMDD]'
MKT_KEY_SHARES = _autodetect_key(...)   # 自动找 '港股@总股本[YYYYMMDD]'
```

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
