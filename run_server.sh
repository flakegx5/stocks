#!/bin/bash
# 启动数据接收服务器，必须在项目目录运行，这样数据才能保存到正确位置

cd "$(dirname "$0")"
echo "📂 工作目录: $(pwd)"
echo "🚀 启动 recv_server.py（端口 9876）..."
echo "   数据将保存至: $(pwd)/hk_stocks_data_new.json"
echo "   Ctrl+C 停止"
echo ""
python3 recv_server.py
