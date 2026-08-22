#!/usr/bin/env bash
# 安装 UK House Invest 为 macOS 开机自启服务（launchd）。
# 服务每天 0 点（Europe/London）自动同步；登录即启动、崩溃自动重启。
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.ukhouseinvest.server"
PLIST_SRC="$ROOT/scripts/com.ukhouseinvest.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.ukhouseinvest.plist"

mkdir -p "$HOME/Library/LaunchAgents"

if [ ! -f "$PLIST_SRC" ]; then
  echo "缺少模板: $PLIST_SRC"
  exit 1
fi

# 生成真实路径的 plist（模板里用占位符）
sed -e "s|__ROOT__|$ROOT|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if ! launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"; then
  # bootout 在 macOS 上可能异步完成，给 launchd 一次短暂收尾时间。
  sleep 1
  launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
fi
echo "已安装并加载服务 → $PLIST_DST"
echo "服务地址: http://localhost:8000"
echo "日志: $ROOT/data/uvicorn.log"
echo ""
echo "常用命令："
echo "  启动/停止: launchctl start/stop $LABEL"
echo "  卸载: launchctl unload $PLIST_DST && rm $PLIST_DST"
