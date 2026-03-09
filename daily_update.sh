#!/bin/bash
# daily_update.sh — 每日港股易变数据更新 + HTML 重建 + Git 推送
#
# 用法:
#   ./daily_update.sh          # 更新市场数据 + 重建 HTML
#   ./daily_update.sh --push   # 同上 + git push
#
# 建议添加到 crontab（港股收盘后，HKT 16:30 = 北京时间 16:30）：
#   30 16 * * 1-5  /Users/flakeliu/claude/stocks/daily_update.sh --push >> /tmp/hk_stocks_daily.log 2>&1

set -e
cd "$(dirname "$0")"

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始每日更新"
echo "========================================"

# 步骤1: 更新市场数据
echo ""
echo ">>> [1/2] 更新市场行情 (AKShare)..."
python3 update_market.py

# 步骤2: 重建 HTML（含所有计算列和排名）
echo ""
echo ">>> [2/2] 重建 hk_stocks.html..."
python3 build_html.py

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] HTML 重建完成"

# 可选步骤3: Git 推送
if [[ "$1" == "--push" ]]; then
    echo ""
    echo ">>> [3/3] 推送至 GitHub..."
    git add hk_stocks_market.json
    TS=$(date '+%Y-%m-%d %H:%M')
    git commit -m "市场数据更新: $TS" || echo "(无变更，跳过 commit)"
    git push
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 推送完成"
fi

echo ""
echo "========================================"
echo "完成！"
echo "========================================"
