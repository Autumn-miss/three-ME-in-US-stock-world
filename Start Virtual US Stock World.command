#!/bin/zsh
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
URL="http://localhost:8501"
LOG_DIR="$PROJECT_DIR/logs"
STREAMLIT_LOG="$LOG_DIR/streamlit.log"
UPDATE_LOG="$LOG_DIR/update.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR" || exit 1

echo "虚拟美股投资世界"
echo "项目目录: $PROJECT_DIR"
echo

echo "1/3 更新真实市场数据和虚拟交易..."
python3 run_daily.py 2>&1 | tee "$UPDATE_LOG"
UPDATE_STATUS=${pipestatus[1]}
if [[ "$UPDATE_STATUS" -ne 0 ]]; then
  echo
  echo "更新失败。详情见: $UPDATE_LOG"
  echo "按任意键关闭窗口。"
  read -k 1
  exit "$UPDATE_STATUS"
fi

echo
echo "2/3 检查网页服务..."
if curl -fsS "$URL" >/dev/null 2>&1; then
  echo "网页服务已经在运行。"
else
  echo "启动 Streamlit..."
  nohup python3 -m streamlit run app.py --server.headless true --browser.gatherUsageStats false --server.address 127.0.0.1 --server.port 8501 > "$STREAMLIT_LOG" 2>&1 &
  for attempt in {1..20}; do
    if curl -fsS "$URL" >/dev/null 2>&1; then
      echo "网页服务已启动。"
      break
    fi
    sleep 0.5
  done
fi

echo
echo "3/3 打开网页..."
open "$URL"
echo
echo "完成。以后双击这个文件即可更新并打开项目。"
echo "网页地址: $URL"
echo
echo "可以关闭这个窗口；网页服务会在后台继续运行。"
sleep 3
