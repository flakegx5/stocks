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

> data.js 可以正常提交。重构后 data.js 只含原始数据（computed 列为 null），各分支文件归属互不重叠，不存在合并冲突风险。

**main 分支合并后**（如 data-pipeline 有新数据需要重建）：

```bash
python3 build_html.py
git add data.js
git commit -m "rebuild: 合并后重建 data.js"
git push
```

---

## 项目路径

本项目位于本地 clone 后的仓库根目录。

## 核心架构（2026-03-19 重构后）

```
hk_stocks_data_new.json  →  build_html.py  →  data.js（只含原始数据 + 元数据）
                                                  ↓
                                          compute.js（浏览器运行时计算 TTM/排名）
                                                  ↓
                                          dashboard JS（渲染）
```

### 文件归属（各分支只改自己的文件，互不冲突）

| 文件 | 归属分支 | 说明 |
|------|---------|------|
| `scrape_iwencai_xhr.py` | data-pipeline | 数据抓取 |
| `hk_stocks_data_new.json` | data-pipeline | 原始数据 |
| `assets/scripts/compute.js` | **indicators** | **浏览器端计算引擎（TTM/排名/衍生指标）** |
| `validate.js` | indicators | Node.js 验证工具（规则迭代影响分析） |
| `stocks_build/*.py` | indicators | Python 配置（列定义、报期列表等，不含计算逻辑） |
| `index.html` | frontend | 页面结构 |
| `assets/styles/dashboard.css` | frontend | 样式 |
| `assets/scripts/dashboard/*.js` | frontend | 前端渲染逻辑 |
| `data.js` | 各分支均可提交 | 构建产物（computed 列为 null），由 build_html.py 生成 |

### 核心文件

- **`data.js`** — 构建产物，含原始数据 + 元数据，computed 列为 null（由 compute.js 运行时填充）
- **`assets/scripts/compute.js`** — 浏览器端计算引擎，移植自 Python metrics.py + ranking.py
- **`build_html.py`** — 简化后只做数据提取（JSON → flat array），不含计算逻辑
- **`index.html`** — 静态前端，加载顺序：data.js → compute.js → dashboard 脚本

生成命令：`python3 build_html.py`
输出：`data.js`（原始数据，computed 列为 null）
在线访问：https://flakegx5.github.io/stocks/

---

## 每日行情更新（iwencai 直接抓取）

### 快速运行（手动触发）

```bash
cd <repo-root>
python3 scrape_iwencai_xhr.py --build --push   # 抓取 + 重建 + git push
```

### 设置 crontab 自动运行（港股收盘后 17:00）

```bash
crontab -e   # 打开 crontab 编辑器，添加以下一行：
```

```
0 17 * * 1-5  cd <repo-root> && python3 scrape_iwencai_xhr.py --build --push >> /tmp/hk_stocks_daily.log 2>&1
```

> 注意：iwencai session（`iwencai_session.json`）过期后需手动重新登录：
> `python3 scrape_iwencai_xhr.py --login`

### 数据来源（单一来源，无 AKShare 依赖）

| 字段 | 来源 | 更新频率 |
|------|------|---------|
| 最新价、涨跌幅、总市值、PE、PB、总股本 | iwencai 每日抓取 | 每日（crontab） |
| 净资产、净利润、ROE 等财务数据 | iwencai | 每次抓取 |

> **MKT_KEY 自动探测**：`build_html.py` 会自动从数据中找到带日期后缀的字段名（如 `港股@总市值[20260309]`），
> 重新抓取后日期变化无需手动更新任何常量。

---

## 计算引擎（compute.js）

所有指标计算在浏览器端完成（~11ms / 698 只股票），不再依赖 Python 计算。

### 两阶段计算
```
Phase 1: computePhase1(row)  → 逐股计算 TTM 指标，写入 row[10..33]
Phase 2: computeRankings()   → 跨股排名，写入 row[34..39]
```

### 级联计算

```
row[40+]（原始报期数据）
  → TTM归母净利润 / TTM净利同比 / TTMROE / TTMROIC / TTM现金流...
    → 净现金 = 总现金 - 短期借款 - 长期借款
    → TTMFCF = max(OCF+capex, OCF+ICF)
    → 股东收益率 = TTMFCF / (总市值 - 净现金) × 100%
      → 低估排名（非金融股）→ 综合排名

row[6]（PE）
  → 低估排名（金融股）→ 综合排名
```

### 金融股判断
```javascript
JINRONG_SET = {'保险', '其他金融', '银行'}
// + 综合企业中含"中信股份"的股票（compute.js 会自动修正 row[9] 为"其他金融"）
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
- 成长：金融/非金融各自按 TTM净利同比 降序（None不参与，排名为空）
- 质量：金融股按 TTMROE 降序，非金融股按 TTMROIC 降序（None不参与，排名为空）
- 股东回报：按股东回报分配率降序，>0 正常排名；≤0 或 None → 末位（=队列总人数）
- 综合：低估×0.4 + 成长×0.2 + 质量×0.2 + 回报×0.2（任一子项为空则综合为空）

---

## 列布局（data.js flat array）

| 区间 | 内容 | 来源 |
|------|------|------|
| idx 0 | 序号 | 占位 |
| idx 1-9 | 股票代码/简称/最新价/涨跌幅/总市值/PE/PB/总股本/行业 | data.js（原始数据） |
| idx 10-39 | 30 个计算指标（COMPUTED_COL_DEFS） | **compute.js 运行时填充** |
| idx 40-243 | 12 报期 × 17 财务指标 | data.js（原始数据） |

### 索引常量（自动计算，勿手动修改）
```python
PERIOD_START    = 10 + len(COMPUTED_COL_DEFS)   # 当前 = 40
N_PERIODS       = len(PERIOD_DATES)              # 当前 = 12
```

### 修改计算逻辑时
- 修改 `assets/scripts/compute.js`（indicators 分支）
- 如需新增/删除计算列，同步修改 `stocks_build/config.py` 的 `COMPUTED_COL_DEFS`
- 本地验证：浏览器打开 index.html，F12 查看 console 确认 compute.js 无报错

### 验证工具（validate.js）

用于 compute.js 规则迭代时的影响分析，在 Node.js 环境运行：

```bash
# 查看当前所有计算指标统计（非空数/占比/min/median/max）
node validate.js

# 改规则前：保存快照
node validate.js --snapshot before.json

# 改规则后：对比差异
node validate.js --snapshot after.json --diff before.json
```

对比报告包含：
- 每个指标的非空数变化（旧 → 新，标记 ◀）
- **计算指标变化明细**：分类统计（空→有值 / 有值→空 / 值变化）+ 逐股样本（最多5条）
- **排名列传导变化**：仅汇总数量，不展示明细（低估/成长/质量/股东回报/综合分数/综合排名）

---

## 默认隐藏列（COMPUTED_HIDE_DEFAULT，共16列）
```python
{'最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款', '最新权益合计',
 'TTM经营现金流', 'TTM投资现金流', 'TTM资本支出', 'TTM融资现金流',
 'TTM股份回购', 'TTM支付股息', '预期25年度分红', '预期25股东回报', '有息负债', '综合分数'}
```

## JS 亿单位列（COMPUTED_YI_NAMES，共18列）
索引：11, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31
