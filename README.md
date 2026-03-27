# HK Stocks Dashboard

港股数据看板 —— 市值 ≥50 亿港元的港股，展示财务数据、TTM 指标、排名评分等。

**在线访问**：https://flakegx5.github.io/stocks/

本地使用：直接双击 `index.html` 用浏览器打开（与 `data.js` 放在同一目录即可）。

---


## 文件说明

| 文件 | 说明 |
|------|------|
| `build_html.py` | 构建脚本，读取 JSON 数据，输出 `data.js`（原始数据，computed 列为 null） |
| `scrape_iwencai_xhr.py` | 数据抓取脚本（问财网，Playwright 无头浏览器） |
| `hk_stocks_data_new.json` | 原始数据（iwencai 抓取结果，~760 只股票） |
| `assets/scripts/compute.js` | 浏览器端计算引擎（TTM/排名/衍生指标，~11ms 完成全部计算） |
| `validate.js` | Node.js 验证工具（计算规则迭代时的影响分析与快照对比） |
| `index.html` | 静态前端（加载顺序：data.js → compute.js → dashboard 脚本） |
| `data.js` | 构建产物（~1.6MB，原始数据 + 元数据，computed 列为 null） |

## 快速开始

### 环境要求

```bash
pip3 install playwright
python3 -m playwright install chromium
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

## 计算指标说明

| 指标 | 说明 |
|------|------|
| TTM归母净利润 | 最近四个季度净利润之和 |
| TTM净利同比 | 与去年同期 TTM 净利的增长率 |
| TTMROE / TTMROIC | TTM 股东权益回报率 / 投入资本回报率 |
| TTM经营/投资/融资现金流 | 最近四季度各类现金流 |
| 净现金 | 总现金 - 短期借款 - 长期借款（三项全空→空，金融股→空） |
| TTMFCF | 优先 OCF+资本支出，不可用时退回 OCF+投资现金流 |
| 股东收益率 | TTMFCF ÷ (总市值 - 净现金) × 100%（分母为企业价值） |
| 股东回报分配率 | 预期25股东回报 ÷ TTM归母净利润 × 100%（负值→0） |
| 低估排序分 | 金融股按PE升序，非金融股按股东收益率降序 |
| 成长排序分 | 按TTM净利同比降序（金融/非金融各自排名，None不参与） |
| 质量排序分 | 金融股按TTMROE，非金融股按TTMROIC降序 |
| 综合分数 | 低估×0.4 + 成长×0.2 + 质量×0.2 + 回报×0.2 |

补充说明：非金融股按统一规则计算排名；若缺少对应计算所需字段，则该维度排名或综合排名显示为空。

## 架构

```
scrape_iwencai_xhr.py   →   hk_stocks_data_new.json   →   build_html.py
      (Playwright)              (原始数据 ~7MB)                  ↓
                                                            data.js（原始数据 + 元数据）
                                                                 ↓
                                                          compute.js（浏览器运行时计算）
                                                                 ↓
                                                          dashboard JS（渲染）
```

- `data.js` 只含原始数据，computed 列为 null；`compute.js` 在浏览器端完成 TTM/排名计算（~11ms）
- `index.html` 加载顺序：data.js → compute.js → dashboard 脚本
- MKT 日期后缀字段（总市值、PE、PB、总股本）由 `build_html.py` 自动探测，重新抓取后无需手动修改
