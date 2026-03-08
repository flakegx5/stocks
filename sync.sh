#!/bin/bash
# sync.sh - 一键同步脚本
# 用法：
#   ./sync.sh          → 拉取最新代码（开始工作前用）
#   ./sync.sh push     → 提交并推送到 GitHub（结束工作后用）
#   ./sync.sh build    → 拉取 + 重新生成 hk_stocks.html
#   ./sync.sh done     → 生成 HTML + 提交推送（一键收工）

set -e
cd "$(dirname "$0")"

case "${1:-pull}" in

  pull)
    echo "⬇️  拉取最新代码..."
    git pull
    echo "✅ 已同步到最新版本"
    ;;

  push)
    echo "⬆️  提交并推送..."
    git add -A
    MSG="${2:-$(date '+%Y-%m-%d %H:%M') 更新}"
    git diff --cached --quiet && echo "⚠️  没有新改动，无需提交" && exit 0
    git commit -m "$MSG"
    git push
    echo "✅ 已推送到 GitHub"
    ;;

  build)
    echo "⬇️  拉取最新代码..."
    git pull
    echo "🔨 重新生成 hk_stocks.html..."
    python3 build_html.py
    echo "✅ 完成，直接打开 hk_stocks.html 即可"
    ;;

  done)
    echo "🔨 生成 hk_stocks.html..."
    python3 build_html.py
    echo "⬆️  提交并推送..."
    git add -A
    MSG="${2:-$(date '+%Y-%m-%d %H:%M') 更新}"
    git diff --cached --quiet && echo "⚠️  没有新改动，无需提交" && exit 0
    git commit -m "$MSG"
    git push
    echo "✅ 全部完成，已推送到 GitHub"
    ;;

  *)
    echo "用法: ./sync.sh [pull|push|build|done] [commit消息]"
    exit 1
    ;;
esac
