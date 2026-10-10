#!/usr/bin/env python3
"""Mac hunt workspace helper.

Create or update a project under
/Users/l/Desktop/Grok/hack-skills/works
from a project name and one or more URLs. New URLs are appended.
GET-only / scanner completions are not real hunts: init/reopen flips them
to pending without deleting evidence, map, or reports.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

TZ = timezone(timedelta(hours=8))
DEFAULT_HACK_SKILLS = Path("/Users/l/Desktop/Grok/hack-skills")
DEFAULT_WORKS_ROOT = DEFAULT_HACK_SKILLS / "works"
TEMPLATE_NAME = "通用漏洞报告模板.docx"
LEGACY_TEMPLATE = DEFAULT_WORKS_ROOT / TEMPLATE_NAME
RULES_NAME = "规则.md"
RULES_READY_RE = re.compile(r"已填写\s*[:：]\s*是")
FAKE_DONE_MARKERS = (
    "GET-only scan",
    "incremental_get_scan",
    "deep JS chunk",
    "safe POST/parameter fuzz",
    "awaiting exploitability",
    "GET观察:",
)
REAL_DONE = {"completed", "skipped", "confirmed"}
RULES_TEMPLATE = """# 项目规则（厂商 SRC / 授权范围）

这是本项目的范围文件，不是 AGENTS.md。

## 状态
- 已填写：否

## 项目
- 名称：
- SRC/平台：

## 范围内
- 

## 范围外
- 

## 禁止测试
- 

## 备注
- 
"""


def ensure_project_rules(project_dir: Path) -> Path:
    path = project_dir / RULES_NAME
    if not path.exists():
        path.write_text(RULES_TEMPLATE, encoding="utf-8")
    return path


def rules_status(project_dir: Path) -> dict:
    path = ensure_project_rules(project_dir)
    text = path.read_text(encoding="utf-8-sig")
    ready = bool(RULES_READY_RE.search(text))
    return {
        "path": str(path),
        "ready": ready,
        "empty": not ready,
        "hint": None
        if ready
        else "规则.md 未填写。提醒一次：补范围内/外/禁测并改成「已填写：是」后会按厂商规则挖。未填则按 AGENTS 安全门禁照样挖。",
    }


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def works_root() -> Path:
    raw = os.environ.get("WORKS_ROOT") or os.environ.get("SRC_ROOT") or str(DEFAULT_WORKS_ROOT)
    return Path(raw).expanduser().resolve()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def normalize_url(raw: str) -> str:
    url = raw.strip()
    if not url or url.startswith("#"):
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url.rstrip("/")


def slug_from_url(url: str, idx: int) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "unknown").lower()
    host = re.sub(r"[^0-9a-z.-]+", "_", host).strip("._") or "unknown"
    port = parts.port
    suffix = ""
    if port and port not in (80, 443):
        suffix = f"_p{port}"
    return f"{idx:03d}_{host[:60]}{suffix}"


def account_side(line: str) -> str | None:
    key = re.sub(r"[\s:：]", "", line.strip().lower())
    if key in {"账号a", "acookie", "usera", "user_a"}:
        return "a"
    if key in {"账号b", "bcookie", "userb", "user_b"}:
        return "b"
    return None


def extract_cookie_header(raw_http: str) -> str:
    for line in raw_http.splitlines():
        if line.lower().startswith("cookie:"):
            return line.split(":", 1)[1].strip()
    return ""


def parse_asset_file(path: Path) -> dict:
    """Parse format1 (URL lines) or format2 (URL + 账号A/B Burp packets)."""
    text = path.read_text(encoding="utf-8-sig")
    urls: list[str] = []
    seen: set[str] = set()
    accounts = {
        "a": {"raw_http": "", "cookie": ""},
        "b": {"raw_http": "", "cookie": ""},
    }
    mode = None
    buf: list[str] = []

    def add_url(raw: str) -> None:
        url = normalize_url(raw)
        if not url:
            return
        key = url.lower()
        if key in seen:
            return
        seen.add(key)
        urls.append(url)

    def flush() -> None:
        nonlocal buf
        if mode and buf:
            raw = "\n".join(buf).strip()
            if raw:
                accounts[mode]["raw_http"] = raw
                cookie = extract_cookie_header(raw)
                if cookie:
                    accounts[mode]["cookie"] = cookie
        buf = []

    for line in text.splitlines():
        stripped = line.strip()
        side = account_side(stripped) if stripped else None
        if side:
            flush()
            mode = side
            continue
        if re.match(r"^https?://", stripped, re.I):
            flush()
            mode = None
            add_url(stripped)
            continue
        if mode is None:
            if not stripped or stripped.startswith("#"):
                continue
            continue
        buf.append(line)
    flush()
    same_cookie = bool(
        accounts["a"]["cookie"]
        and accounts["a"]["cookie"] == accounts["b"]["cookie"]
    )
    return {"urls": urls, "accounts": accounts, "same_cookie": same_cookie, "path": str(path)}


def read_assets(values: list[str], url_files: list[Path]) -> dict:
    urls: list[str] = []
    seen: set[str] = set()
    accounts = {
        "a": {"raw_http": "", "cookie": ""},
        "b": {"raw_http": "", "cookie": ""},
    }
    same_cookie = False

    def add(raw: str) -> None:
        url = normalize_url(raw)
        if not url:
            return
        key = url.lower()
        if key in seen:
            return
        seen.add(key)
        urls.append(url)

    for value in values:
        add(value)
    for path in url_files:
        if not path.exists():
            raise SystemExit(f"url file not found: {path}")
        parsed = parse_asset_file(path)
        for url in parsed["urls"]:
            add(url)
        for side in ("a", "b"):
            if parsed["accounts"][side]["cookie"] or parsed["accounts"][side]["raw_http"]:
                accounts[side] = parsed["accounts"][side]
        same_cookie = same_cookie or parsed["same_cookie"]
    return {"urls": urls, "accounts": accounts, "same_cookie": same_cookie}


def next_index(existing_ids: list[str]) -> int:
    highest = 0
    for target_id in existing_ids:
        match = re.match(r"^(\d+)_", target_id)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def ensure_template(root: Path) -> Path:
    dest = root / TEMPLATE_NAME
    if dest.exists():
        return dest
    for source in (LEGACY_TEMPLATE, DEFAULT_HACK_SKILLS / TEMPLATE_NAME):
        if source.exists():
            shutil.copy2(source, dest)
            return dest
    return dest


def append_unique_lines(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    existing = {
        normalize_url(line).lower()
        for line in current.splitlines()
        if normalize_url(line)
    }
    new_lines = [url for url in urls if url.lower() not in existing]
    if not new_lines:
        if not path.exists():
            path.write_text("", encoding="utf-8")
        return
    prefix = "" if (not current or current.endswith("\n")) else "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix)
        for url in new_lines:
            handle.write(url + "\n")


def empty_baseline(target_id: str, url: str) -> dict:
    return {
        "target_id": target_id,
        "url": url,
        "created_at": now_iso(),
        "js_hashes": {},
        "api_paths": [],
        "params": {},
        "pages": [],
        "forms": [],
        "domains": [],
    }


def empty_target(target_id: str, url: str, evidence_path: Path) -> dict:
    return {
        "target_id": target_id,
        "url": url,
        "history": [],
        "status": "pending",
        "result": "",
        "updated_at": now_iso(),
        "last_added": "workspace created",
        "evidence_path": str(evidence_path),
    }


def fake_done_blob(row: dict) -> str:
    parts = [str(row.get("last_added") or ""), str(row.get("result") or "")]
    for item in row.get("history") or []:
        if isinstance(item, dict):
            parts.append(json.dumps(item, ensure_ascii=False))
        else:
            parts.append(str(item))
    return "\n".join(parts)


def is_fake_done(row: dict) -> bool:
    blob = fake_done_blob(row)
    return any(marker in blob for marker in FAKE_DONE_MARKERS)


def is_real_done(row: dict) -> bool:
    status = row.get("status")
    if status in {"skipped", "confirmed"}:
        return True
    if status == "completed" and not is_fake_done(row):
        return True
    return False


def persist_target_status(project_dir: Path, target_id: str, status: str, last_added: str, result: str | None = None) -> dict:
    tpath = project_dir / "progress" / "targets" / f"{target_id}.json"
    data = load_json(tpath, {})
    data["status"] = status
    data["last_added"] = last_added
    data["updated_at"] = now_iso()
    if result is not None:
        data["result"] = result
    hist = data.setdefault("history", [])
    hist.append({"at": data["updated_at"], "event": status, "summary": last_added})
    atomic_json(tpath, data)
    index_path = project_dir / "progress" / "index.json"
    index = load_json(index_path, {"targets": []})
    for item in index.get("targets", []):
        if item.get("target_id") == target_id:
            item["status"] = status
            item["last_added"] = last_added
            item["updated_at"] = data["updated_at"]
            if result is not None:
                item["result"] = result
    index["updated_at"] = data["updated_at"]
    atomic_json(index_path, index)
    return data


def reopen_targets(project: str, *, urls: list[str] | None = None, fake_only: bool = True, target_ids: list[str] | None = None) -> dict:
    """Flip status to pending. Never deletes evidence, map, reports, or history rows."""
    project_dir = works_root() / project
    index_path = project_dir / "progress" / "index.json"
    index = load_json(index_path, {"targets": []})
    want_ids = {x for x in (target_ids or []) if x}
    want_urls = {normalize_url(u).lower() for u in (urls or []) if normalize_url(u)}
    opened = []
    skipped = []
    for item in index.get("targets", []):
        tid = item.get("target_id") or ""
        url = normalize_url(item.get("url") or "").lower()
        tpath = project_dir / "progress" / "targets" / f"{tid}.json"
        row = load_json(tpath, item)
        selected = False
        if want_ids:
            selected = tid in want_ids
        elif want_urls:
            selected = url in want_urls
        else:
            selected = True
        if not selected:
            continue
        if fake_only and not is_fake_done(row) and row.get("status") in {"completed", "confirmed"}:
            skipped.append(tid)
            continue
        if row.get("status") == "pending":
            skipped.append(tid)
            continue
        persist_target_status(
            project_dir,
            tid,
            "pending",
            "reopened: 不删历史，只改状态。GET-only/观察不算挖完，按逻辑重挖",
            result="",
        )
        opened.append(tid)
    index = load_json(index_path, {"targets": []})
    pending = [t["target_id"] for t in index.get("targets", []) if not is_real_done(t)]
    return {
        "ok": True,
        "project": project,
        "reopened": opened,
        "left_alone": skipped,
        "pending": pending,
        "note": "evidence/map/reports untouched",
    }


def index_entry(target: dict) -> dict:
    return {
        "target_id": target["target_id"],
        "url": target["url"],
        "status": target.get("status", "pending"),
        "updated_at": target.get("updated_at", now_iso()),
        "last_added": target.get("last_added", ""),
        "evidence_path": target.get("evidence_path", ""),
        "result": target.get("result", ""),
    }


def write_accounts(path: Path, accounts: dict) -> None:
    data = load_json(
        path,
        {
            "anonymous": {},
            "user_a": {"cookie": "", "headers": {}, "raw_http": "", "note": ""},
            "user_b": {"cookie": "", "headers": {}, "raw_http": "", "note": ""},
        },
    )
    for side, key in (("a", "user_a"), ("b", "user_b")):
        cookie = accounts.get(side, {}).get("cookie") or ""
        raw = accounts.get(side, {}).get("raw_http") or ""
        if cookie or raw:
            data[key]["cookie"] = cookie
            data[key]["raw_http"] = raw
            data[key]["note"] = "imported from url2 Burp packet"
    atomic_json(path, data)


def init_project(project: str, urls: list[str], accounts: dict | None = None) -> dict:
    if not project or project in {".", ".."} or "/" in project or "\\" in project:
        raise SystemExit("invalid project name")
    root = works_root()
    root.mkdir(parents=True, exist_ok=True)
    template = ensure_template(root)

    project_dir = root / project
    progress_dir = project_dir / "progress"
    targets_dir = progress_dir / "targets"
    state_dir = project_dir / "state"
    reports_dir = project_dir / "reports"
    evidence_root = project_dir / "evidence"
    auth_dir = project_dir / "auth"
    learn_dir = DEFAULT_HACK_SKILLS / "learn"
    for path in (targets_dir, state_dir, reports_dir, evidence_root, auth_dir, learn_dir):
        path.mkdir(parents=True, exist_ok=True)
    rules = rules_status(project_dir)

    accounts_path = auth_dir / "accounts.json"
    if not accounts_path.exists():
        atomic_json(
            accounts_path,
            {
                "anonymous": {},
                "user_a": {"cookie": "", "headers": {}, "raw_http": "", "note": "paste a logged-in session"},
                "user_b": {"cookie": "", "headers": {}, "raw_http": "", "note": "second account for IDOR/BOLA"},
            },
        )
    if accounts:
        write_accounts(accounts_path, accounts)

    tested = project_dir / "tested.jsonl"
    if not tested.exists():
        tested.write_text("", encoding="utf-8")

    index_path = progress_dir / "index.json"
    index = load_json(index_path, {"updated_at": now_iso(), "targets": []})
    if not isinstance(index, dict) or not isinstance(index.get("targets"), list):
        index = {"updated_at": now_iso(), "targets": []}

    by_url = {}
    for item in index["targets"]:
        if isinstance(item, dict) and item.get("url"):
            by_url[normalize_url(item["url"]).lower()] = item

    created = []
    reused = []
    if not urls:
        if not by_url:
            raise SystemExit("no URLs given and project has no existing targets")
    else:
        seq = next_index([item.get("target_id", "") for item in index["targets"]])
        for url in urls:
            key = url.lower()
            if key in by_url:
                old = by_url[key]
                reused.append(old["target_id"])
                tpath = targets_dir / f"{old['target_id']}.json"
                row = load_json(tpath, old)
                if is_fake_done(row) or (row.get("status") == "completed" and is_fake_done(old)):
                    persist_target_status(
                        project_dir,
                        old["target_id"],
                        "pending",
                        "reopened on init: GET-only/扫描完成不算挖完",
                        result="",
                    )
                    old["status"] = "pending"
                    old["last_added"] = "reopened on init: GET-only/扫描完成不算挖完"
                continue
            target_id = slug_from_url(url, seq)
            while (targets_dir / f"{target_id}.json").exists():
                seq += 1
                target_id = slug_from_url(url, seq)
            evidence_path = evidence_root / target_id
            evidence_path.mkdir(parents=True, exist_ok=True)
            target = empty_target(target_id, url, evidence_path)
            atomic_json(targets_dir / f"{target_id}.json", target)
            baseline_path = state_dir / target_id / "baseline.json"
            if not baseline_path.exists():
                atomic_json(baseline_path, empty_baseline(target_id, url))
            map_path = state_dir / target_id / "map.md"
            if not map_path.exists():
                map_path.write_text(
                    f"# {target_id}\n\n"
                    f"- url: {url}\n\n"
                    "## Actors\n\n- anonymous\n- user_a\n- user_b\n\n"
                    "## Resources\n\n- \n\n"
                    "## Boundaries\n\n- \n\n"
                    "## Anomalies\n\n- \n\n"
                    "## Dead\n\n- \n",
                    encoding="utf-8",
                )
            entry = index_entry(target)
            index["targets"].append(entry)
            by_url[key] = entry
            created.append(target_id)
            seq += 1

    index["updated_at"] = now_iso()
    atomic_json(index_path, index)

    if urls:
        append_unique_lines(project_dir / "url.txt", urls)

    pending = [t["target_id"] for t in index["targets"] if not is_real_done(t)]
    completed = [t["target_id"] for t in index["targets"] if t.get("status") == "completed" and not is_fake_done(t)]
    return {
        "ok": True,
        "works_root": str(root),
        "src_root": str(root),
        "project": project,
        "project_dir": str(project_dir),
        "template": str(template) if template.exists() else None,
        "url_file": str(project_dir / "url.txt"),
        "index": str(index_path),
        "reports": str(reports_dir),
        "auth": str(accounts_path),
        "rules": rules,
        "created": created,
        "reused": reused,
        "pending": pending,
        "completed": completed,
        "target_count": len(index["targets"]),
        "hack_skills": str(DEFAULT_HACK_SKILLS),
        "memory": str(DEFAULT_HACK_SKILLS / "memory_system" / "data" / "experience.jsonl"),
        "learn": str(DEFAULT_HACK_SKILLS / "learn"),
        "has_user_a": bool((accounts or {}).get("a", {}).get("cookie")),
        "has_user_b": bool((accounts or {}).get("b", {}).get("cookie")),
        "same_cookie": bool(
            (accounts or {}).get("a", {}).get("cookie")
            and (accounts or {}).get("a", {}).get("cookie") == (accounts or {}).get("b", {}).get("cookie")
        ),
        "warning": None if rules.get("ready") else rules.get("hint"),
        "next": (
            "format2 cookies imported; dual-account tests enabled"
            if (accounts or {}).get("a", {}).get("cookie")
            else "fill auth/accounts.json for user_a and user_b before logic tests"
        ),
    }


def show_project(project: str) -> dict:
    root = works_root()
    project_dir = root / project
    index = load_json(project_dir / "progress" / "index.json", {})
    targets = index.get("targets", []) if isinstance(index, dict) else []
    rules = rules_status(project_dir) if project_dir.exists() else {"ready": False, "empty": True, "path": "", "hint": "project missing"}
    return {
        "ok": project_dir.exists(),
        "works_root": str(root),
        "src_root": str(root),
        "project_dir": str(project_dir),
        "rules": rules,
        "target_count": len(targets),
        "pending": [t.get("target_id") for t in targets if not is_real_done(t)],
        "completed": [t.get("target_id") for t in targets if t.get("status") == "completed" and not is_fake_done(t)],
        "skipped": [t.get("target_id") for t in targets if t.get("status") == "skipped"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update a Mac SRC hunt project")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="create project dirs and register URLs")
    init.add_argument("--project", required=True, help="project name, e.g. 京东")
    init.add_argument("--url", action="append", default=[], help="repeatable target URL")
    init.add_argument("--url-file", action="append", default=[], type=Path, help="file with one URL per line")

    status = sub.add_parser("status", help="print project progress summary")
    status.add_argument("--project", required=True)

    reopen = sub.add_parser("reopen", help="re-hunt without deleting history/evidence/reports")
    reopen.add_argument("--project", required=True)
    reopen.add_argument("--url-file", action="append", default=[], type=Path)
    reopen.add_argument("--url", action="append", default=[])
    reopen.add_argument("--target-id", action="append", default=[])
    reopen.add_argument("--all-fake-done", action="store_true", help="reopen every GET-only/scanner completion")
    reopen.add_argument("--force", action="store_true", help="also reopen real completed hunts")

    args = parser.parse_args()
    if args.cmd == "init":
        assets = read_assets(args.url, args.url_file)
        result = init_project(args.project, assets["urls"], assets["accounts"])
        result["same_cookie"] = assets["same_cookie"] or result.get("same_cookie")
        if result["same_cookie"]:
            result["warning"] = "账号A和账号B的Cookie相同，无法做跨账号越权，请换成两个登录态"
    elif args.cmd == "reopen":
        assets = read_assets(args.url, args.url_file) if (args.url or args.url_file) else {"urls": []}
        if args.all_fake_done or (not args.url and not args.url_file and not args.target_id):
            result = reopen_targets(args.project, fake_only=True)
        else:
            result = reopen_targets(
                args.project,
                urls=assets.get("urls") or None,
                fake_only=not args.force,
                target_ids=args.target_id or None,
            )
    else:
        result = show_project(args.project)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
