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

# 确保使用正确的虚拟环境
export PATH="/app/.venv/bin:${PATH}"
echo "[entrypoint] PATH: $PATH"
echo "[entrypoint] Using Python: $(which python)"
echo "[entrypoint] Python version: $(python --version)"

# 直接使用虚拟环境中的 Python 来验证
if ! /app/.venv/bin/python -c "import uvicorn" 2>/dev/null; then
  echo "[entrypoint] ❌ 错误: uvicorn 模块未找到"
  echo "[entrypoint] 检查虚拟环境目录:"
  ls -la /app/.venv/bin/ | head -10
  exit 1
fi

echo "[entrypoint] ✅ uvicorn 模块检查通过"

# 执行传入的命令
exec "$@"
