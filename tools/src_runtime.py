#!/usr/bin/env python3
"""Stable hunt runtime: proxy HTTP, method gate, baseline, tested log, progress."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path("/Users/l/Desktop/Grok/hack-skills")
sys.path.insert(0, str(ROOT / "tools"))
from src_http import burp_request as _burp_req  # noqa: E402
from src_http import burp_response as _burp_resp  # noqa: E402
from src_workspace import (  # noqa: E402
    atomic_json,
    is_real_done,
    load_json,
    normalize_url,
    now_iso,
    rules_status,
    works_root,
)

DONE_STATUSES = {"completed", "skipped", "confirmed"}
# GET helper already ran; still needs a real logic hunt. Not a skip.
OBSERVED_STATUS = "observed"

BLOCKED = {"PUT", "DELETE", "PATCH", "UPDATE"}
ALLOWED = {"GET", "HEAD", "OPTIONS", "POST"}
DANGEROUS_POST = re.compile(
    r"(?i)(delete|remove|destroy|drop|pay|payment|order|checkout|refund|withdraw|"
    r"password|reset|bind|unbind|sms|sendcode|transfer)"
)
API_RE = re.compile(r"""(?i)(?:['"])(/[a-z0-9_./-]{2,120})(?:['"])""")
SCRIPT_RE = re.compile(r"""(?i)<script[^>]+src=['"]([^'"]+)['"]""")
PII_RE = re.compile(
    r"(手机|电话|身份证|姓名|地址|订单号|发票|memberPin|\"pin\"|\"erp\")"
)
TZ = timezone(timedelta(hours=8))


def project_dir(name: str) -> Path:
    return works_root() / name


def load_accounts(proj: Path) -> dict:
    return load_json(
        proj / "auth" / "accounts.json",
        {"anonymous": {}, "user_a": {}, "user_b": {}},
    )


def cookie_for(accounts: dict, who: str) -> str:
    if who in ("", "anonymous"):
        return ""
    key = {"a": "user_a", "b": "user_b", "user_a": "user_a", "user_b": "user_b"}.get(who, who)
    return str((accounts.get(key) or {}).get("cookie") or "")


def burp_up() -> bool:
    import socket
    try:
        sock = socket.create_connection(("127.0.0.1", 8080), timeout=2)
        sock.close()
        return True
    except OSError:
        return False


def request(
    method: str,
    url: str,
    *,
    cookie: str = "",
    json_body: Any = None,
    data: Any = None,
    timeout: int = 15,
    via_burp: bool = True,
) -> dict:
    method = method.upper()
    if method in BLOCKED or method == "UPDATE":
        raise PermissionError(f"blocked method {method}")
    if method not in ALLOWED:
        raise PermissionError(f"method not allowed {method}")
    if method == "POST":
        blob = url + json.dumps(json_body or {}, ensure_ascii=False) + str(data or "")
        if DANGEROUS_POST.search(blob):
            raise PermissionError("blocked POST looks state-changing")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    if cookie:
        headers["Cookie"] = cookie
    proxies = None
    if via_burp:
        proxies = {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"}
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            data=data,
            timeout=timeout,
            verify=False,
            proxies=proxies,
            allow_redirects=False,
        )
        body = resp.text[:200000]
        p = urlsplit(url)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        host = p.hostname or ""
        if p.port and p.port not in (80, 443):
            host = f"{host}:{p.port}"
        wire_headers = {"Host": host, **headers}
        req_body = ""
        if json_body is not None:
            req_body = json.dumps(json_body, ensure_ascii=False)
        elif data:
            req_body = data if isinstance(data, str) else str(data)
        raw_req_src = f"{method} {path} HTTP/1.1\n" + "\n".join(
            f"{k}: {v}" for k, v in wire_headers.items()
        ) + "\n\n" + req_body
        raw_req = _burp_req(raw_req_src, url=url)
        raw_resp = _burp_resp(
            f"HTTP/1.1 {resp.status_code}\n"
            + "\n".join(f"{k}: {v}" for k, v in list(resp.headers.items())[:40])
            + "\n\n"
            + body[:8000]
        )
        return {
            "ok": True,
            "status": resp.status_code,
            "url": url,
            "method": method,
            "headers": dict(resp.headers),
            "body": body,
            "sha256": hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest(),
            "length": len(body),
            "raw_request": raw_req,
            "raw_response": raw_resp,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url, "method": method, "status": 0, "body": "", "sha256": "", "length": 0}


def append_tested(proj: Path, row: dict) -> None:
    row = {**row, "at": now_iso()}
    path = proj / "tested.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def update_target(proj: Path, target_id: str, **fields) -> None:
    tpath = proj / "progress" / "targets" / f"{target_id}.json"
    data = load_json(tpath, {})
    data.update(fields)
    data["updated_at"] = now_iso()
    hist = data.setdefault("history", [])
    hist.append({"at": now_iso(), "event": fields.get("status", "update"), "summary": fields.get("last_added", "")})
    atomic_json(tpath, data)
    index_path = proj / "progress" / "index.json"
    index = load_json(index_path, {"targets": []})
    for item in index.get("targets", []):
        if item.get("target_id") == target_id:
            item.update({k: data.get(k) for k in ("status", "updated_at", "last_added", "result", "evidence_path")})
    index["updated_at"] = now_iso()
    atomic_json(index_path, index)


def collect_baseline(url: str, cookie: str = "", via_burp: bool = True) -> dict:
    page = request("GET", url, cookie=cookie, via_burp=via_burp)
    html = page.get("body") or ""
    scripts = []
    for src in SCRIPT_RE.findall(html)[:12]:
        abs_url = urljoin(url, src)
        js = request("GET", abs_url, cookie=cookie, via_burp=via_burp)
        scripts.append({"url": abs_url, "sha256": js.get("sha256") or "", "ok": js.get("ok"), "status": js.get("status")})
    apis = sorted(set(API_RE.findall(html)))[:80]
    return {
        "url": url,
        "updated_at": now_iso(),
        "root": {
            "status_code": page.get("status"),
            "body_sha256": page.get("sha256"),
            "length": page.get("length"),
            "ok": page.get("ok"),
        },
        "js_hashes": {s["url"]: s["sha256"] for s in scripts},
        "scripts": scripts,
        "api_paths": apis,
        "pages": [url],
    }


def diff_baseline(old: dict, new: dict) -> dict:
    old_js = old.get("js_hashes") or {}
    new_js = new.get("js_hashes") or {}
    changed_js = [u for u, h in new_js.items() if old_js.get(u) != h]
    added_js = [u for u in new_js if u not in old_js]
    old_api = set(old.get("api_paths") or [])
    new_api = set(new.get("api_paths") or [])
    return {
        "js_changed": changed_js,
        "js_added": added_js,
        "api_added": sorted(new_api - old_api),
        "page_changed": (old.get("root") or {}).get("body_sha256") != (new.get("root") or {}).get("body_sha256"),
        "has_delta": bool(changed_js or added_js or (new_api - old_api) or True),
    }


def looks_like_other_user(body_a: str, body_b: str) -> bool:
    if not body_a or not body_b:
        return False
    if body_a == body_b:
        return False
    if abs(len(body_a) - len(body_b)) < 20 and hashlib.sha256(body_a.encode()).hexdigest() == hashlib.sha256(body_b.encode()).hexdigest():
        return False
    return bool(PII_RE.search(body_b)) and body_a[:200] != body_b[:200]


def hunt_one(proj: Path, target: dict, via_burp: bool = True) -> dict:
    accounts = load_accounts(proj)
    url = target["url"]
    tid = target["target_id"]
    cookie_a = cookie_for(accounts, "user_a")
    cookie_b = cookie_for(accounts, "user_b")
    state_dir = proj / "state" / tid
    state_dir.mkdir(parents=True, exist_ok=True)
    evidence = proj / "evidence" / tid
    evidence.mkdir(parents=True, exist_ok=True)

    anon = request("GET", url, via_burp=via_burp)
    append_tested(proj, {"target_id": tid, "operator": "anonymous_get", "url": url, "status": anon.get("status"), "sha256": anon.get("sha256")})
    (evidence / "anon.json").write_text(json.dumps({k: anon.get(k) for k in ("status", "sha256", "length", "url", "ok", "error")}, ensure_ascii=False, indent=2), encoding="utf-8")

    with_a = request("GET", url, cookie=cookie_a, via_burp=via_burp) if cookie_a else None
    with_b = request("GET", url, cookie=cookie_b, via_burp=via_burp) if cookie_b else None
    if with_a:
        append_tested(proj, {"target_id": tid, "operator": "get_as_a", "url": url, "status": with_a.get("status"), "sha256": with_a.get("sha256")})
    if with_b:
        append_tested(proj, {"target_id": tid, "operator": "get_as_b", "url": url, "status": with_b.get("status"), "sha256": with_b.get("sha256")})

    finding = None
    if with_a and with_b and cookie_a != cookie_b and looks_like_other_user(with_a.get("body") or "", with_b.get("body") or ""):
        finding = {
            "operator": "swap_identity",
            "url": url,
            "raw_request": with_b.get("raw_request"),
            "raw_response": with_b.get("raw_response"),
        }
    if not finding and anon.get("ok") and PII_RE.search(anon.get("body") or "") and anon.get("status") == 200:
        # unauth PII-like — still need other-user proof; record as anomaly only
        append_tested(proj, {"target_id": tid, "operator": "unauth_pii_hint", "url": url, "status": 200})

    old = load_json(state_dir / "baseline.json", {})
    new_base = collect_baseline(url, cookie=cookie_a, via_burp=via_burp)
    delta = diff_baseline(old, new_base)
    new_base["delta"] = {k: delta[k] for k in ("js_changed", "js_added", "api_added", "page_changed")}
    atomic_json(state_dir / "baseline.json", new_base)

    summary = f"anon={anon.get('status')} a={with_a.get('status') if with_a else '-'} b={with_b.get('status') if with_b else '-'} js_added={len(delta['js_added'])} api_added={len(delta['api_added'])}"
    update_target(
        proj,
        tid,
        status=OBSERVED_STATUS,
        result="lead" if finding else "",
        last_added="GET观察: " + summary + "（不是挖完）",
        evidence_path=str(evidence),
    )
    return {"target_id": tid, "url": url, "finding": finding, "summary": summary, "delta": delta}


def round_urls(proj: Path) -> set[str]:
    path = proj / "url.txt"
    if not path.exists():
        return set()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        url = normalize_url(line)
        if url:
            found.add(url.lower())
    return found


def hunt_project(name: str, limit: int = 0, via_burp: bool = True, all_pending: bool = False) -> dict:
    proj = project_dir(name)
    rules = rules_status(proj)
    index = load_json(proj / "progress" / "index.json", {"targets": []})
    pending = [t for t in index.get("targets", []) if not is_real_done(t)]
    pending = [t for t in pending if t.get("status") != OBSERVED_STATUS]
    batch = round_urls(proj)
    if batch and not all_pending:
        pending = [t for t in pending if normalize_url(t.get("url") or "").lower() in batch]
    if limit:
        pending = pending[:limit]
    results = []
    for target in pending:
        results.append(hunt_one(proj, target, via_burp=via_burp))
    return {
        "ok": True,
        "project": name,
        "rules": rules,
        "warning": None if rules.get("ready") else rules.get("hint"),
        "round_only": bool(batch) and not all_pending,
        "ran": len(results),
        "findings": [r for r in results if r.get("finding")],
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("hunt")
    p.add_argument("--project", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--no-burp", action="store_true")
    p.add_argument("--all-pending", action="store_true", help="ignore url.txt and hunt every incomplete target")
    g = sub.add_parser("get")
    g.add_argument("--url", required=True)
    g.add_argument("--cookie", default="")
    g.add_argument("--no-burp", action="store_true")
    b = sub.add_parser("burp-up")
    args = parser.parse_args()
    if args.cmd == "burp-up":
        print(json.dumps({"burp_proxy": burp_up()}))
        return 0
    if args.cmd == "get":
        out = request("GET", args.url, cookie=args.cookie, via_burp=not args.no_burp)
        json.dump({k: out.get(k) for k in ("ok", "status", "sha256", "length", "error", "url")}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if out.get("ok") else 1
    if args.no_burp is False and not burp_up():
        print(json.dumps({"ok": False, "error": "Burp proxy 8080 is down"}, ensure_ascii=False))
        return 2
    out = hunt_project(
        args.project,
        limit=args.limit,
        via_burp=not args.no_burp,
        all_pending=args.all_pending,
    )
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
