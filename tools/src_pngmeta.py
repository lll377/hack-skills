#!/usr/bin/env python3
"""PNG src-url metadata for report screenshots.

PNG URL metadata helper. Report screenshots now come from Playwright MCP.
any PNG that does not carry a full http(s) URL — so a capture without the URL
bar cannot be stuffed into the Word report.
"""
from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path
from urllib.parse import urlsplit

PNG_SIG = b"\x89PNG\r\n\x1a\n"
SRC_URL_KEY = "src-url"
HTTP_URL_RE = re.compile(r"^https?://[^/\s]+/\S*", re.I)
HTTPS_URL_RE = re.compile(r"^https://[^/\s]+/\S*", re.I)


def is_full_http_url(url: str) -> bool:
    return bool(HTTP_URL_RE.match((url or "").strip()))


def is_full_https_url(url: str) -> bool:
    return bool(HTTPS_URL_RE.match((url or "").strip()))


def normalize_full_url(url: str) -> str:
    url = (url or "").strip()
    if re.match(r"^https?://[^/\s]+$", url, re.I):
        url += "/"
    return url


def url_core(url: str) -> str:
    p = urlsplit((url or "").strip())
    host = (p.netloc or "").lower()
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    scheme = (p.scheme or "https").lower()
    return f"{scheme}://{host}{path}"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def iter_chunks(png: bytes):
    if not png.startswith(PNG_SIG):
        raise ValueError("not a PNG")
    i = 8
    n = len(png)
    while i + 12 <= n:
        length = struct.unpack(">I", png[i : i + 4])[0]
        tag = png[i + 4 : i + 8]
        data_end = i + 8 + length
        if data_end + 4 > n:
            break
        yield tag, png[i + 8 : data_end]
        i = data_end + 4


def png_dimensions(png: bytes) -> tuple[int, int]:
    for tag, data in iter_chunks(png):
        if tag == b"IHDR" and len(data) >= 8:
            return struct.unpack(">II", data[:8])
    return 0, 0


def _is_src_url_chunk(tag: bytes, data: bytes) -> bool:
    if tag not in (b"tEXt", b"iTXt"):
        return False
    return data.startswith(SRC_URL_KEY.encode("ascii") + b"\x00")


def _text_chunk(url: str) -> bytes:
    try:
        data = f"{SRC_URL_KEY}\x00{url}".encode("latin-1")
        return _chunk(b"tEXt", data)
    except UnicodeEncodeError:
        data = SRC_URL_KEY.encode("ascii") + b"\x00\x00\x00\x00\x00" + url.encode("utf-8")
        return _chunk(b"iTXt", data)


def embed_src_url(png: bytes, url: str) -> bytes:
    url = normalize_full_url(url)
    if not is_full_http_url(url):
        raise ValueError(f"screenshot URL is not a full http(s) URL with path: {url!r}")
    out = PNG_SIG
    inserted = False
    for tag, data in iter_chunks(png):
        if _is_src_url_chunk(tag, data):
            continue
        out += _chunk(tag, data)
        if tag == b"IHDR" and not inserted:
            out += _text_chunk(url)
            inserted = True
    if not inserted:
        raise ValueError("PNG has no IHDR")
    return out


def read_src_url(png: bytes) -> str:
    for tag, data in iter_chunks(png):
        if tag == b"tEXt" and data.startswith(b"src-url\x00"):
            return data.split(b"\x00", 1)[1].decode("latin-1")
        if tag == b"iTXt" and data.startswith(b"src-url\x00"):
            rest = data[len(b"src-url\x00") :]
            # comp_flag, comp_method, lang\0, translated\0, text
            if len(rest) < 2:
                continue
            rest = rest[2:]
            parts = rest.split(b"\x00", 2)
            if len(parts) < 3:
                continue
            return parts[2].decode("utf-8")
    return ""


def write_stub_png(path: Path, url: str = "", width: int = 640, height: int = 160) -> Path:
    """Dark PNG used by tests. Real report shots come from Playwright MCP."""
    rows = []
    for y in range(height):
        row = bytearray(1 + width * 3)
        row[0] = 0
        for x in range(width):
            i = 1 + x * 3
            row[i] = 0x20
            row[i + 1] = 0x21
            row[i + 2] = 0x24 + ((x * 13 + y * 7) % 80)
        rows.append(bytes(row))
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
    if url:
        png = embed_src_url(png, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path
