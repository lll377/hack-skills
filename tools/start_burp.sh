#!/bin/zsh
set -euo pipefail
# 不启动 Burp。你自己开好之后，用这一条看 8080 / MCP 是否正常。
# 作为 Grok SessionStart hook 时，结果走 stderr（启动日志 / /hooks 能看见）。
PY="/Users/l/Desktop/Grok/hack-skills/bin/python"
RPC="/Users/l/Desktop/Grok/hack-skills/tools/burp-mcp/burp_mcp_rpc.py"
fail=0
as_hook=0
[[ -n "${GROK_HOOK_EVENT:-}" ]] && as_hook=1

say() {
  echo "$1"
  if [[ $as_hook -eq 1 ]]; then
    echo "$1" >&2
  fi
}

if lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
  say "OK  流量代理 127.0.0.1:8080"
else
  say "NO  8080 没在听。先自己启动 Burp，Proxy 监听 127.0.0.1:8080，Intercept Off。"
  fail=1
fi

if lsof -nP -iTCP:9876 -sTCP:LISTEN >/dev/null 2>&1; then
  say "OK  MCP 端口 127.0.0.1:9876"
else
  say "NO  9876 没在听。Burp 顶部 MCP 标签勾选 Enabled。"
  fail=1
fi

if [[ $fail -eq 0 ]]; then
  tmp="$(mktemp)"
  if "$PY" "$RPC" list-tools --timeout 10 --out-file "$tmp" >/dev/null 2>&1; then
    n="$("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d.get("response",{}).get("result",{}).get("tools",[])))' "$tmp")"
    say "OK  Burp MCP 握手（${n} 个工具）"
  else
    say "NO  Burp MCP 握手失败（9876 在听，但扩展没正常应答）"
    fail=1
  fi
  rm -f "$tmp"
fi

# 开 Grok 时 MCP 客户端自己会连，hook 里不再套一层 grok mcp doctor。
if [[ $as_hook -eq 0 ]]; then
  if command -v grok >/dev/null 2>&1; then
    doc="$(mktemp)"
    if grok mcp doctor burp --json >"$doc" 2>/dev/null; then
      if "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get("servers") and d["servers"][0].get("healthy") else 1)' "$doc"; then
        say "OK  Grok 已连上 Burp MCP"
      else
        say "NO  Grok 连不上 Burp MCP。看: grok mcp doctor burp"
        fail=1
      fi
    else
      say "NO  grok mcp doctor 执行失败"
      fail=1
    fi
    rm -f "$doc"
  else
    say "--  当前 shell 没有 grok 命令，跳过 Grok 侧检查。TUI 里用 /mcps 看 burp 是否绿。"
  fi
fi

if [[ $fail -eq 0 ]]; then
  say "结论: MCP 正常。你自己开 Burp 即可，不用再开一份。"
else
  say "结论: 还不正常。先自己打开 Burp，再重跑这一条。"
fi
exit "$fail"
