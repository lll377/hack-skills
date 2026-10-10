#!/usr/bin/env python3
"""Acceptance for the frozen SRC pipeline. Creates a throwaway project, then deletes it."""
from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/Users/l/Desktop/Grok/hack-skills")
PY = ROOT / "bin" / "python"
TOOLS = ROOT / "tools"
WORKS = ROOT / "works"
PROJECT = "_accept_pipeline"


def skill_path(name: str) -> Path:
    direct = ROOT / "skills" / name / "SKILL.md"
    if direct.is_file():
        return direct
    root = ROOT / "skills"
    if root.is_dir():
        for cat in root.iterdir():
            cand = cat / name / "SKILL.md"
            if cand.is_file():
                return cand
    return direct


def run(args: list[str], ok_codes=(0,)) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode not in ok_codes:
        raise SystemExit(f"FAIL {' '.join(args)}\n{proc.stdout}\n{proc.stderr}")
    return proc


def main() -> int:
    fails = []
    proj = WORKS / PROJECT
    if proj.exists():
        shutil.rmtree(proj)

    # 1. init format1
    proc = run([str(PY), str(TOOLS / "src_workspace.py"), "init", "--project", PROJECT, "--url", "https://example.com"])
    data = json.loads(proc.stdout)
    for key in ("project_dir", "index", "auth", "reports"):
        if not data.get(key):
            fails.append(f"init missing {key}")
    if not (proj / "state" / "001_example.com" / "map.md").exists():
        fails.append("map.md not created")
    if not (proj / "progress" / "index.json").exists():
        fails.append("index.json missing")
    if not (proj / "规则.md").exists():
        fails.append("规则.md not created")
    if not (ROOT / "learn").is_dir():
        fails.append("learn/ not created")
    if data.get("ok") is False:
        fails.append("init ok false on empty rules")

    # 2. format2 parse + same-cookie warning
    fixture = Path(tempfile.gettempdir()) / "accept_url2.txt"
    fixture.write_text(
        "账号A：\nGET / HTTP/1.1\nHost: example.com\nCookie: session=AAA\n\n"
        "账号B：\nGET / HTTP/1.1\nHost: example.com\nCookie: session=BBB\n\n"
        "https://example.com\n",
        encoding="utf-8",
    )
    proc = run([str(PY), str(TOOLS / "src_workspace.py"), "init", "--project", PROJECT, "--url-file", str(fixture)])
    data = json.loads(proc.stdout)
    if not data.get("has_user_a") or not data.get("has_user_b"):
        fails.append("format2 cookies not imported")
    if data.get("same_cookie"):
        fails.append("different cookies flagged same")

    same = Path(tempfile.gettempdir()) / "accept_url2_same.txt"
    same.write_text(
        "账号A：\nGET / HTTP/1.1\nHost: x\nCookie: session=SAME\n\n"
        "账号B：\nGET / HTTP/1.1\nHost: x\nCookie: session=SAME\n\n"
        "https://example.com\n",
        encoding="utf-8",
    )
    proc = run([str(PY), str(TOOLS / "src_workspace.py"), "init", "--project", PROJECT, "--url-file", str(same)])
    data = json.loads(proc.stdout)
    if not data.get("same_cookie") and "相同" not in (data.get("warning") or ""):
        # imported cookies overwrite to SAME
        acc = json.loads((proj / "auth" / "accounts.json").read_text())
        if acc["user_a"]["cookie"] == acc["user_b"]["cookie"] and acc["user_a"]["cookie"] == "session=SAME":
            if not data.get("same_cookie"):
                fails.append("same cookie not warned")

    # 3. method gate
    sys.path.insert(0, str(TOOLS))
    import src_runtime as runtime
    blocked = False
    try:
        runtime.request("DELETE", "https://example.com/", via_burp=False)
    except PermissionError:
        blocked = True
    if not blocked:
        fails.append("DELETE not blocked")

    # 5. hunt one target without requiring finding
    hunt = run(
        [str(PY), str(TOOLS / "src_runtime.py"), "hunt", "--project", PROJECT, "--limit", "1", "--no-burp"],
        ok_codes=(0, 1, 2),
    )
    try:
        h = json.loads(hunt.stdout)
    except json.JSONDecodeError:
        fails.append(f"hunt json parse: {hunt.stdout[:400]} {hunt.stderr[:200]}")
        h = {}
    if h.get("ok") is False:
        fails.append(f"hunt failed {h}")
    if h and not h.get("rules", {}).get("ready") and not h.get("warning"):
        fails.append("empty rules should warn but still hunt")
    tested = (proj / "tested.jsonl").read_text(encoding="utf-8")
    if "anonymous_get" not in tested:
        fails.append("tested.jsonl missing anonymous_get")
    idx = json.loads((proj / "progress" / "index.json").read_text())
    statuses = {t["target_id"]: t.get("status") for t in idx.get("targets", [])}
    if statuses.get("001_example.com") == "completed":
        fails.append("GET helper must not mark completed (that skips the real hunt)")
    if statuses.get("001_example.com") not in {"observed", "pending", "in_progress"}:
        fails.append("GET helper should leave target observed/pending")

    # 6. memory remember then compact so accept rows never stay in the ledger
    skill_md = skill_path("business-logic-vuln")
    skill_before = skill_md.read_bytes()
    mem = run(
        [
            str(PY),
            str(TOOLS / "src_memory.py"),
            "remember",
            "--skill",
            "business-logic-vuln",
            "--method",
            "accept_probe",
            "--trigger",
            "acceptance",
            "--oracle",
            "accept-only",
            "--project",
            PROJECT,
        ]
    )
    written = json.loads(mem.stdout)
    if not (written.get("stored") or {}).get("method"):
        fails.append("memory remember failed")
    mem2 = run(
        [
            str(PY),
            str(TOOLS / "src_memory.py"),
            "remember",
            "--skill",
            "business-logic-vuln",
            "--method",
            "accept_probe",
            "--trigger",
            "acceptance",
            "--oracle",
            "accept-only-again",
            "--steps",
            "second write must skip not duplicate",
            "--project",
            PROJECT,
        ]
    )
    again = json.loads(mem2.stdout)
    if again.get("skipped") is not True:
        fails.append("duplicate remember must skip, not write or overwrite")
    if skill_md.read_bytes() != skill_before:
        fails.append("remember mutated SKILL.md")
    compact = run([str(PY), str(TOOLS / "src_memory.py"), "compact"])
    compact_out = json.loads(compact.stdout)
    if compact_out.get("ok") is not True:
        fails.append("memory compact failed")
    exp = ROOT / "memory_system" / "data" / "experience.jsonl"
    leftover = exp.read_text(encoding="utf-8") if exp.exists() else ""
    if "accept_probe" in leftover or PROJECT in leftover:
        fails.append("accept rows leaked into experience.jsonl")
    recall = run([str(PY), str(TOOLS / "src_memory.py"), "recall", "--skill", "business-logic-vuln", "--limit", "5"])
    recalled = json.loads(recall.stdout)
    if recalled.get("ok") is not True:
        fails.append("memory recall failed")
    catalog = run([str(PY), str(TOOLS / "src_memory.py"), "catalog"])
    catalog_out = json.loads(catalog.stdout)
    if catalog_out.get("ok") is not True or not catalog_out.get("skills"):
        fails.append("memory catalog failed")

    # 7. Skill + constitution lock: AI must not write skills, knowledge, or AGENTS.md
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "永不由 AI 改" not in agents:
        fails.append("AGENTS.md missing skill read-only lock")
    if "knowledge/**" not in agents:
        fails.append("AGENTS.md missing knowledge read-only lock")
    if "追加到对应 Skill" in agents or "并追加对应 Skill" in agents:
        fails.append("AGENTS.md still tells AI to append Skill")
    if "禁止 AI 改本文件" not in agents:
        fails.append("AGENTS.md missing constitution lock")
    if "src_report.py" in agents or "通用漏洞报告模板" in agents:
        fails.append("AGENTS.md still points at removed report script or template")
    if "禁止打完一条就停" not in agents and "挖完一条就停" not in agents:
        fails.append("AGENTS.md missing continuous-hunt stop rule")
    if "src_spray_log.py" in agents or "src_hashcat_gen.py" in agents or "cn-admin-spray" in agents:
        fails.append("AGENTS.md still points at removed spray skill or scripts")
    if "立刻停止整场爆破" in agents:
        fails.append("AGENTS.md still stops the whole hunt on lockout")
    monte_adapted = ("arsenal", "methodology", "osint", "osint-offensive", "quill", "triage", "vulns")
    for name in monte_adapted:
        md = skill_path(name)
        if not md.exists():
            fails.append(f"adapted skill missing: {name}")
            continue
        body = md.read_text(encoding="utf-8")
        if "Load Gate" not in body:
            fails.append(f"{name} missing Load Gate")
        if "src_report.py" in body:
            fails.append(f"{name} still points at removed src_report.py")
        if "business-logic-vuln" not in body:
            fails.append(f"{name} missing default-skill reminder")
        if "recall --skill" not in body:
            fails.append(f"{name} missing recall --skill")
    for banned in ("recon", "web3"):
        if skill_path(banned).is_file():
            fails.append(f"banned Monte skill imported: {banned}")
    secret_scan = ROOT / "tools" / "secret_scan.py"
    if not secret_scan.exists():
        fails.append("osint-offensive secret_scan.py missing")
    feed = (ROOT / "启动挖洞.txt").read_text(encoding="utf-8")
    if "追加 Skill" in feed:
        fails.append("启动挖洞.txt still tells AI to append Skill")
    if "src_report.py" in feed:
        fails.append("启动挖洞.txt still points at removed report script")
    if "未导入 recon" not in feed:
        fails.append("启动挖洞.txt missing Monte-adapt routing")
    if "chrome_screenshot.py" in feed or "chrome_debug.sh" in feed:
        fails.append("启动挖洞.txt still points at removed Chrome debug tools")
    if (TOOLS / "chrome_screenshot.py").exists() or (TOOLS / "chrome_debug.sh").exists():
        fails.append("removed Chrome debug tools are still present")
    hack_skill = skill_path("hack").read_text(encoding="utf-8")
    if "追加路由行" in hack_skill and "不要往本文件追加" not in hack_skill:
        fails.append("skills/hack/SKILL.md still tells AI to append routing rows")
    if "新硬规则只写" in hack_skill:
        fails.append("skills/hack/SKILL.md still tells AI to write AGENTS.md")
    if "未导入" not in hack_skill or "osint-offensive" not in hack_skill:
        fails.append("skills/hack/SKILL.md missing Monte-adapt router rows")
    recon_router = skill_path("recon-for-sec").read_text(encoding="utf-8")
    if "osint-offensive" not in recon_router or "未导入" not in recon_router:
        fails.append("recon-for-sec missing osint routing / recon exclusion")
    mem_src = (TOOLS / "src_memory.py").read_text(encoding="utf-8")
    for line in mem_src.splitlines():
        if "SKILL.md" in line and any(tok in line for tok in ("write_text", "open(", "write(")):
            fails.append("src_memory.py looks able to write SKILL.md")
            break
    logic_first = (ROOT / "knowledge" / "logic_first.md").read_text(encoding="utf-8")
    if "本目录只读" not in logic_first:
        fails.append("knowledge/logic_first.md missing read-only note")
    for path in (
        ROOT / "AGENTS.md",
        skill_md,
        skill_path("hack"),
        skill_path("recon-for-sec"),
        skill_path("arsenal"),
        skill_path("methodology"),
        skill_path("osint"),
        skill_path("osint-offensive"),
        skill_path("quill"),
        skill_path("triage"),
        skill_path("vulns"),
        ROOT / "knowledge" / "logic_first.md",
        ROOT / "knowledge" / "loop.md",
        ROOT / "knowledge" / "patterns" / "INDEX.md",
    ):
        flags = getattr(path.stat(), "st_flags", 0)
        if not (flags & stat.UF_IMMUTABLE):
            fails.append(f"{path.relative_to(ROOT)} missing uchg")

    shutil.rmtree(proj, ignore_errors=True)
    if fails:
        print("ACCEPT FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("ACCEPT PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
