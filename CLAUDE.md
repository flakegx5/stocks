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

- **`build_html.py`** — 唯一需要编辑的核心文件（约1200行）
- **`hk_stocks_data_new.json`** — 原始数据源，不要手动修改（由抓取流程更新）
- **`hk_stocks.html`** — 由 `build_html.py` 生成，不在 git 中
- **`scraper_browser.js`** — 浏览器控制台抓取脚本（每次抓取粘贴到 DevTools）
- **`run_server.sh`** — 启动数据接收服务器的脚本
- **`recv_server.py`** — 数据接收服务器（监听 9876 端口，保存 JSON）

生成命令：`python3 build_html.py`
输出：`hk_stocks.html`（约1.5MB，自包含，直接浏览器打开）

---

## 数据更新流程（抓取新数据）

### 问财查询 URL（直接在浏览器打开）

```
https://www.iwencai.com/unifiedwap/result?w=港股范围内，市值大于50亿港元，列出最新pe、pb、总股本、所属行业，列出2025年年报和2025年三季报的分别以下数字，包括：归母净利润、总现金、流动资产、总负债、短期借款、长期借款、ROE、ROIC、经营活动现金流净额、投资活动现金流净额、资本性支出、融资活动现金流量净额、年度分红、现金流量表中的股份回购、现金流量表中的支付股息，归母净利润同比增速。&querytype=hkstock
```

> **注意**：每次新年报/季报出来后，把 URL 里的报期（如"2025年三季报"→"2025年报"）对应更新。

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

### 索引常量（自动计算，勿手动修改）
```python
PERIOD_START    = 10 + len(COMPUTED_COL_DEFS)   # 当前 = 38
TTMROE_IDX_PY   = 10 + COMPUTED_COL_DEFS.index('TTMROE')    # = 18
TTMROIC_IDX_PY  = 10 + COMPUTED_COL_DEFS.index('TTMROIC')   # = 19
```

### 空值处理规则
- **净现金**：总现金/短期借款/长期借款全部为空 → None；否则 None 视为 0
- **有息负债**：短期借款/长期借款全部为空 → None；否则 None 视为 0
- **预期25年度分红**：计算结果为负 → None

### 排名规则（标准竞争排名，1224式）
- 低估：金融股按 PE 升序（PE≤0不参与），非金融股按股东收益率降序（≤0不参与）
- 成长：金融/非金融各自按 TTM净利同比 降序（None视为0参与）
- 质量：金融股按 TTMROE 降序，非金融股按 TTMROIC 降序（None不参与）
- 股东回报：按股东回报分配率降序，正值参与正常排名；None/负值 → 末位（=队列总人数）
- 综合：低估×0.4 + 成长×0.2 + 质量×0.2 + 回报×0.2（任一子项为空则综合为空）

---

## 默认隐藏列（COMPUTED_HIDE_DEFAULT）
```python
{'TTM股份回购', 'TTM支付股息', '预期25年度分红',
 '最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款'}
```

## JS 亿单位列（COMPUTED_YI_COLS）
索引：11, 13, 14, 15, 16, 17, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30
