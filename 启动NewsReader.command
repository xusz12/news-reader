#!/bin/zsh

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR" || exit 1

python3 "$SCRIPT_DIR/launcher.py"
status=$?
if (( status != 0 )); then
  echo "NewsReader 启动失败（退出码 $status）。请查看此终端中的错误信息。"
  /usr/bin/osascript -e 'display alert "NewsReader 启动失败" message "请查看启动终端中的错误信息。"' >/dev/null 2>&1 || true
fi
exit "$status"
