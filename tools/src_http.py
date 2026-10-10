#!/usr/bin/env python3
"""Canonical Burp Repeater paste format: CRLF HTTP/1.1, query on the request line."""
from __future__ import annotations

import re
from urllib.parse import quote, urlsplit, urlunsplit

_STATUS_REASON = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    423: "Locked",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}

_JUNK_LINE = re.compile(
    r"(?i)^(sha256:|统计结果|=> |（cookie header|^\(cookie |禁止打码|【从 Burp|包含：请求行|必须含 Cookie)"
)


def _split_http(text: str) -> tuple[list[str], str]:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.replace("\u00a0", " ").replace("\u2028", "\n")
    parts = re.split(r"\n\s*\n", raw, maxsplit=1)
    head = parts[0]
    body = parts[1] if len(parts) > 1 else ""
    lines = [ln.rstrip() for ln in head.split("\n")]
    lines = [ln for ln in lines if ln and not _JUNK_LINE.search(ln)]
    # drop trailing commentary in body
    body_lines = []
    for ln in body.split("\n"):
        if _JUNK_LINE.search(ln.strip()):
            break
        body_lines.append(ln)
    body = "\n".join(body_lines).strip("\n")
    return lines, body


def _host_with_port(url: str = "", host_header: str = "") -> str:
    if host_header:
        return host_header.strip()
    p = urlsplit(url)
    host = p.hostname or ""
    if p.port and p.port not in (80, 443):
        return f"{host}:{p.port}"
    return host


def request_line_and_headers(method: str, url: str, headers: dict | None = None, body: str = "") -> str:
    p = urlsplit(url)
    path = p.path or "/"
    if p.query:
        path = f"{path}?{p.query}"
    hdrs = {str(k): str(v) for k, v in (headers or {}).items()}
    host = _host_with_port(url, hdrs.get("Host") or hdrs.get("host") or "")
    out = {}
    for k, v in hdrs.items():
        if k.lower() == "host":
            continue
        out[k] = v
    lines = [f"{method.upper()} {path} HTTP/1.1", f"Host: {host}"]
    for k, v in out.items():
        lines.append(f"{k}: {v}")
    method_u = method.upper()
    if method_u in {"GET", "HEAD"} and body.strip():
        extra = body.strip()
        if extra.lower().startswith("params=") or extra.startswith("{") or "=" in extra:
            q = extra
            if path.endswith("?") or "?" in path:
                path = path + "&" + q if not path.endswith("?") else path + q
            else:
                path = path + "?" + (q if "=" in q.split("\n", 1)[0] else "params=" + quote(q, safe="{},:[]\"'"))
            lines[0] = f"{method_u} {path} HTTP/1.1"
            body = ""
    raw = "\r\n".join(lines) + "\r\n\r\n"
    if body:
        raw += body if body.endswith("\n") else body
    return raw


def burp_request(text: str, *, url: str = "") -> str:
    lines, body = _split_http(text)
    if not lines:
        return (text or "").replace("\n", "\r\n")
    first = lines[0].strip()
    first = re.sub(r"HTTP/2\S*", "HTTP/1.1", first)
    m = re.match(r"^([A-Z]+)\s+(\S.*?)\s+(HTTP/\d(?:\.\d)?)$", first)
    if not m:
        return "\r\n".join(lines) + "\r\n\r\n" + body
    method, target = m.group(1), m.group(2)
    headers: dict[str, str] = {}
    for ln in lines[1:]:
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        headers[k.strip()] = v.strip()
    if url and (target == "/" or "?" not in target):
        p = urlsplit(url)
        if p.query and "?" not in target:
            path = p.path or target.split("?")[0]
            target = f"{path}?{p.query}"
        if p.hostname and "Host" not in headers and "host" not in {x.lower() for x in headers}:
            headers["Host"] = _host_with_port(url)
    method_u = method.upper()
    if method_u in {"GET", "HEAD"} and body.strip() and "?" not in target:
        extra = body.strip()
        if extra.startswith("{"):
            q = "params=" + quote(extra, safe="")
        elif extra.lower().startswith("params="):
            val = extra[7:]
            q = "params=" + quote(val, safe="") if val.startswith("{") else extra
        else:
            q = extra
        target = target + "?" + q
        body = ""
    host = headers.pop("Host", None) or headers.pop("host", None) or _host_with_port(url)
    lines_out = [f"{method_u} {target} HTTP/1.1"]
    if host:
        lines_out.append(f"Host: {host}")
    for k, v in headers.items():
        if k.lower() == "host":
            continue
        lines_out.append(f"{k}: {v}")
    raw = "\r\n".join(lines_out) + "\r\n\r\n"
    if body:
        raw += body
    return raw


def burp_response(text: str) -> str:
    lines, body = _split_http(text)
    if not lines:
        return (text or "").replace("\n", "\r\n")
    first = lines[0].strip()
    first = re.sub(r"^HTTP/2\S*", "HTTP/1.1", first)
    m = re.match(r"^HTTP/\d(?:\.\d)?\s+(\d{3})(?:\s+(.*))?$", first)
    if m:
        code = int(m.group(1))
        reason = (m.group(2) or "").strip() or _STATUS_REASON.get(code, "")
        first = f"HTTP/1.1 {code} {reason}".rstrip()
    out = [first]
    for ln in lines[1:]:
        if ":" not in ln:
            continue
        out.append(ln)
    raw = "\r\n".join(out) + "\r\n\r\n"
    if body:
        raw += body
    return raw
