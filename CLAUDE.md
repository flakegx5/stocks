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

## 核心文件

- **`build_html.py`** — 唯一需要编辑的核心文件（约1200行）
- **`hk_stocks_data_new.json`** — 原始数据源，不要修改
- **`hk_stocks.html`** — 由 `build_html.py` 生成，不在 git 中

生成命令：`python3 build_html.py`
输出：`hk_stocks.html`（约1.5MB，自包含，直接浏览器打开）

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
