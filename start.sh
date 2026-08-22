#!/usr/bin/env bash
# UK House Invest 启动脚本
# 用法：
#   ./start.sh            前台运行（Ctrl+C 停止）
#   ./start.sh --daemon   后台运行（日志 data/uvicorn.log，PID data/uvicorn.pid）
#   ./start.sh --stop     停止后台进程
#   ./start.sh --install-service  安装 macOS 开机自启服务（launchd，每日0点自动同步）
set -e
cd "$(dirname "$0")"

ROOT="$(pwd)"
DATA_DIR="$ROOT/data"
PID_FILE="$DATA_DIR/uvicorn.pid"
LOG_FILE="$DATA_DIR/uvicorn.log"
mkdir -p "$DATA_DIR"

stop_daemon() {
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && echo "已停止 (pid $pid)"
    else
      echo "后台进程已退出 (pid $pid)"
    fi
    rm -f "$PID_FILE"
  else
    echo "没有运行中的后台进程"
  fi
}

if [ "$1" = "--stop" ]; then
  stop_daemon
  exit 0
fi

echo "== 1/3 准备 Python 环境 =="
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi
backend/.venv/bin/pip install -q -r backend/requirements.txt

echo "== 2/3 构建前端 =="
cd frontend
if [ ! -d node_modules ]; then
  npm install
fi
npm run build
cd ..

echo "== 3/3 启动服务 http://localhost:8000 =="
cd backend

if [ "$1" = "--daemon" ]; then
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "后台服务已在运行 (pid $(cat "$PID_FILE"))"
    exit 0
  fi
  rm -f "$PID_FILE"
  nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "后台运行中 (pid $(cat "$PID_FILE")) · 日志 $LOG_FILE"
  exit 0
fi

# 前台运行（默认）
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
