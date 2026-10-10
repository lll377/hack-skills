#!/bin/zsh
set -euo pipefail
# Grok SessionStart：检查 Burp，弹 macOS 通知。不启动 Burp。
CHECK="/Users/l/Desktop/Grok/hack-skills/tools/start_burp.sh"
out="$(mktemp)"
err="$(mktemp)"
code=0
GROK_HOOK_EVENT="${GROK_HOOK_EVENT:-session_start}" "$CHECK" >"$out" 2>"$err" || code=$?
summary="$(grep -E '^(OK|NO|结论)' "$out" | paste -sd ' / ' -)"
[[ -n "$summary" ]] || summary="Burp 检查无输出"
if [[ $code -eq 0 ]]; then
  title="Grok Burp 正常"
else
  title="Grok Burp 异常"
fi
osascript >/dev/null 2>&1 <<EOF || true
display notification "$summary" with title "$title"
EOF
# 失败时 Grok 会把 stderr 第一行写进滚动区；成功时靠通知和底部状态栏。
if [[ $code -ne 0 ]]; then
  echo "$title: $summary" >&2
fi
rm -f "$out" "$err"
exit "$code"
