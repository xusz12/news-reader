#!/bin/zsh

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR" || exit 1

show_startup_error() {
  local message="$1"
  print -u2 -- "$message"
  if [[ "${NEWS_READER_NO_ALERT:-0}" != "1" ]]; then
    /usr/bin/osascript -e 'display alert "NewsReader 启动失败" message "请查看启动终端中的错误信息。"' >/dev/null 2>&1 || true
  fi
}

PYTHON_BIN="${NEWS_READER_PYTHON:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  show_startup_error "NewsReader 启动失败：找不到 $PYTHON_BIN。请先安装 Python 3.10+，或设置 NEWS_READER_PYTHON 指向可用的 Python。"
  exit 1
fi

if "$PYTHON_BIN" - <<'PY'
import importlib.util
import sys

required = (("flask", "Flask"), ("openai", "openai"))
missing = [display_name for module_name, display_name in required
           if importlib.util.find_spec(module_name) is None]
if missing:
    print("缺少 Python 依赖：" + ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
PY
then
  :
else
  dependency_status=$?
  show_startup_error "NewsReader 启动前检查失败。请在终端运行：$PYTHON_BIN -m pip install -r \"$SCRIPT_DIR/requirements.txt\"，然后重新双击此文件。"
  exit "$dependency_status"
fi

"$PYTHON_BIN" "$SCRIPT_DIR/launcher.py"
exit_code=$?
if (( exit_code != 0 )); then
  show_startup_error "NewsReader 启动失败（退出码 $exit_code）。请查看此终端中的错误信息。"
fi
exit "$exit_code"
