#!/bin/bash
# 启动 HTTP 服务并自动打开浏览器
# 用法: ./serve.sh [端口号]

PORT=${1:-8080}
DIR="sessions"

# 检查 sessions 目录
if [ ! -d "$DIR" ]; then
    echo "❌ 找不到 $DIR 目录，请先运行 fix-font.py"
    exit 1
fi

# 查找 HTML 文件
HTML_FILE=$(ls "$DIR"/*.html 2>/dev/null | head -1)

echo "🚀 启动 HTTP 服务 http://localhost:$PORT"
python3 -m http.server "$PORT" --directory "$DIR" &
SERVER_PID=$!

# 等服务器启动
sleep 1

if [ -n "$HTML_FILE" ]; then
    BASENAME=$(basename "$HTML_FILE")
    URL="http://localhost:$PORT/$BASENAME"
else
    URL="http://localhost:$PORT"
fi

echo "🌐 打开浏览器: $URL"
open "$URL"

echo ""
echo "按 Ctrl+C 停止服务"
trap "kill $SERVER_PID 2>/dev/null; exit" INT TERM
wait $SERVER_PID
