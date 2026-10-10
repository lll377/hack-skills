#!/usr/bin/env python3
"""Open the project Chrome, then optionally attach Playwright MCP.

Paths come from this file's location, so the repo can move to another machine.
Override with env: BURP_PROXY, SRC_CHROME_CDP_PORT, CHROME_PATH, PLAYWRIGHT_MCP.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "works" / ".playwright-profile"
OLD_PROFILE = ROOT / "works" / ".chrome-profile"
PORT = int(os.environ.get("SRC_CHROME_CDP_PORT", "9222"))
PROXY = os.environ.get("BURP_PROXY", "http://127.0.0.1:8080")
OUTPUT = ROOT / "log" / "playwright"


def cdp(path: str, method: str = "GET") -> str:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    with urllib.request.urlopen(req, timeout=2) as resp:
        return resp.read().decode("utf-8", "replace")


def cdp_ok(path: str = "/json/version") -> bool:
    try:
        cdp(path)
        return True
    except Exception:
        return False


def chrome_executable() -> str:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("Chrome not found. Set CHROME_PATH.")


def profile_running() -> bool:
    needle = f"user-data-dir={PROFILE}"
    try:
        out = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=False)
    except Exception:
        return False
    return needle in out.stdout


def stop_old_debug_chrome() -> None:
    if not cdp_ok() or profile_running():
        return
    needle = f"user-data-dir={OLD_PROFILE}"
    try:
        out = subprocess.run(["ps", "ax", "-o", "pid=,command="], capture_output=True, text=True, check=False)
    except Exception:
        return
    for line in out.stdout.splitlines():
        if needle not in line:
            continue
        pid = line.strip().split(maxsplit=1)[0]
        if pid.isdigit():
            subprocess.run(["kill", pid], check=False)
    time.sleep(0.5)


def launch_chrome() -> None:
    PROFILE.mkdir(parents=True, exist_ok=True)
    exe = chrome_executable()
    args = [
        exe,
        f"--remote-debugging-port={PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir={PROFILE}",
        f"--proxy-server={PROXY}",
        "--ignore-certificate-errors",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    if sys.platform == "darwin":
        subprocess.run(["open", "-na", "Google Chrome", "--args", *args[1:]], check=False)
    elif sys.platform == "win32":
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    else:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def wait_cdp() -> None:
    for _ in range(50):
        if cdp_ok():
            return
        time.sleep(0.2)
    raise SystemExit(f"Chrome did not open on port {PORT}")


def ensure_page() -> None:
    try:
        pages = json.loads(cdp("/json/list"))
    except Exception:
        pages = []
    if any(item.get("type") == "page" for item in pages):
        return
    try:
        cdp("/json/new?about:blank", method="PUT")
    except Exception:
        pass


def activate() -> None:
    if sys.platform != "darwin":
        return
    subprocess.run(
        ["osascript", "-e", 'tell application "Google Chrome" to activate'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_browser() -> None:
    stop_old_debug_chrome()
    if not (profile_running() and cdp_ok()):
        launch_chrome()
        wait_cdp()
    ensure_page()
    activate()
    print(f"Playwright Chrome: http://127.0.0.1:{PORT}", file=sys.stderr)
    print(f"profile: {PROFILE}", file=sys.stderr)


def find_playwright_mcp() -> list[str]:
    env = os.environ.get("PLAYWRIGHT_MCP")
    if env and Path(env).exists():
        return [env]
    found = shutil.which("playwright-mcp")
    if found:
        return [found]
    npm = shutil.which("npm")
    if npm:
        prefix = subprocess.run([npm, "prefix", "-g"], capture_output=True, text=True, check=False)
        candidate = Path(prefix.stdout.strip()) / "bin" / "playwright-mcp"
        if candidate.exists():
            return [str(candidate)]
    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "@playwright/mcp@latest"]
    raise SystemExit("playwright-mcp not found. Install with: npm install -g @playwright/mcp")


def serve_mcp() -> None:
    open_browser()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cmd = find_playwright_mcp() + [
        "--cdp-endpoint",
        f"http://127.0.0.1:{PORT}",
        "--ignore-https-errors",
        "--output-dir",
        str(OUTPUT),
    ]
    os.execvp(cmd[0], cmd)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "open"
    if action == "open":
        open_browser()
    elif action == "mcp":
        serve_mcp()
    else:
        raise SystemExit("usage: playwright_browser.py [open|mcp]")


if __name__ == "__main__":
    main()
