#!/usr/bin/env sh
set -e

export DISPLAY=:99
rm -f /tmp/.X99-lock

if ! pgrep -x Xvfb >/dev/null 2>&1; then
  echo "[entrypoint] Starting Xvfb on $DISPLAY"
  Xvfb $DISPLAY -screen 0 1920x1080x24 -nolisten tcp &
fi

# 等待 Xvfb 准备就绪
sleep 0.5

# 执行传入的命令
exec "$@"
