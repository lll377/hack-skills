#!/usr/bin/env python3
"""Proxy an MCP stdio process and append every message in full.

A message whose URL matches a hunt target is written to
works/<项目>/evidence/<目标>/log/mcp.jsonl.
Messages with no matching host stay in log/mcp.jsonl.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
FALLBACK = ROOT / "log" / "mcp.jsonl"
WORKS = ROOT / "works"
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
HOST_RE = re.compile(r"(?im)^host:\s*([^\s:]+)")
TARGET_RE = re.compile(r"^\d+_(.+)$")
LOCK = threading.Lock()
INDEX: list[tuple[str, Path]] = []
INDEX_AT = 0.0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_of(url: str) -> str:
    if "://" not in url:
        url = "http://" + url
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host


def refresh_index() -> None:
    global INDEX, INDEX_AT
    if time.time() - INDEX_AT < 5 and INDEX:
        return
    found: list[tuple[str, Path]] = []
    if WORKS.is_dir():
        for project in WORKS.iterdir():
            evidence = project / "evidence"
            if not evidence.is_dir():
                continue
            for target in evidence.iterdir():
                if not target.is_dir():
                    continue
                match = TARGET_RE.match(target.name)
                if not match:
                    continue
                found.append((match.group(1).lower(), target))
    INDEX = found
    INDEX_AT = time.time()


def hosts_in(value, found: set[str]) -> None:
    if isinstance(value, str):
        for match in URL_RE.finditer(value):
            host = host_of(match.group(0))
            if host:
                found.add(host)
        for match in HOST_RE.finditer(value):
            found.add(match.group(1).lower().rstrip("."))
    elif isinstance(value, dict):
        for item in value.values():
            hosts_in(item, found)
    elif isinstance(value, list):
        for item in value:
            hosts_in(item, found)


def target_dirs(payload) -> list[Path]:
    refresh_index()
    hosts: set[str] = set()
    hosts_in(payload, hosts)
    if not hosts:
        return []
    dirs = []
    seen = set()
    for host, folder in INDEX:
        if host in hosts and folder not in seen:
            dirs.append(folder)
            seen.add(folder)
    return dirs


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_log(name: str, direction: str, body: bytes) -> None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        payload = body.decode("utf-8", "replace")
    row = {"at": now(), "tool": name, "dir": direction, "msg": payload}
    dirs = target_dirs(payload)
    with LOCK:
        if not dirs:
            append(FALLBACK, row)
            return
        for folder in dirs:
            append(folder / "log" / "mcp.jsonl", row)


def pump(src, dst, name: str, direction: str) -> None:
    buf = b""
    while True:
        chunk = src.read1(65536) if hasattr(src, "read1") else src.read(65536)
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            try:
                write_log(name, direction, line)
            except Exception:
                pass
            dst.write(line + b"\n")
            dst.flush()


def main() -> None:
    if "--" not in sys.argv:
        raise SystemExit("usage: mcp_stdio_log.py <name> -- <command> [args...]")
    split = sys.argv.index("--")
    name = sys.argv[1]
    cmd = sys.argv[split + 1 :]
    if not cmd:
        raise SystemExit("missing command")
    import subprocess

    child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None)

    def pump_in():
        try:
            pump(sys.stdin.buffer, child.stdin, name, "in")
        finally:
            child.stdin.close()

    threads = [
        threading.Thread(target=pump_in, daemon=True),
        threading.Thread(target=pump, args=(child.stdout, sys.stdout.buffer, name, "out"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    child.wait()
    raise SystemExit(child.returncode)


if __name__ == "__main__":
    main()
