#!/bin/zsh
# Grok 底部状态栏用。只看端口，不启动 Burp，不做完整握手。
cat >/dev/null 2>&1 || true
ok8080=0
ok9876=0
lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1 && ok8080=1
lsof -nP -iTCP:9876 -sTCP:LISTEN >/dev/null 2>&1 && ok9876=1
g=$'\033[32m'
r=$'\033[31m'
z=$'\033[0m'
if (( ok8080 )); then
  s8080="${g}8080 OK${z}"
else
  s8080="${r}8080 NO${z}"
fi
if (( ok9876 )); then
  s9876="${g}MCP 9876 OK${z}"
else
  s9876="${r}MCP NO 先开Burp${z}"
fi
print -r -- "Burp ${s8080}  ${s9876}"
