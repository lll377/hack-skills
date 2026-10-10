#!/bin/sh
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
PY="$ROOT/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
exec "$PY" "$ROOT/tools/playwright_browser.py" open
