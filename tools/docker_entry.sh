#!/bin/sh
# 容器入口：起一个虚拟显示，再把命令跑在里面。
set -e

Xvfb :99 -screen 0 1280x900x24 >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
sleep 1

# 等 X 起来
for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then break; fi
    sleep 0.3
done

export DISPLAY=:99
cd /work
set +e
"$@"
CODE=$?
set -e
kill $XVFB_PID 2>/dev/null || true
exit $CODE
