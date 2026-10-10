#!/usr/bin/env python3
"""The only writable hunt-memory gate.

Writes memory_system/data/experience.jsonl and nothing else.
Never opens skills/**, knowledge/**, or AGENTS.md for write. Duplicate skill+trigger is skipped.
8765 is a viewer of the same jsonl, not a second store.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("/Users/l/Desktop/Grok/hack-skills")
EXP = ROOT / "memory_system" / "data" / "experience.jsonl"
SKILLS = ROOT / "skills"
TZ = timezone(timedelta(hours=8))
BANNED = ("cookie:", "pt_key=", "pt_pin=", "authorization:", "set-cookie")


def _reject_secrets(text: str) -> None:
    low = (text or "").lower()
    for token in BANNED:
        if token in low:
            raise SystemExit(f"refusing to store secret-like field: {token}")


def _load_rows() -> list[dict]:
    if not EXP.exists():
        return []
    rows: list[dict] = []
    for line in EXP.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_rows(rows: list[dict]) -> None:
    target = EXP.resolve()
    if target.parent.name != "data" or target.name != "experience.jsonl":
        raise SystemExit("refusing to write anywhere except experience.jsonl")
    EXP.parent.mkdir(parents=True, exist_ok=True)
    tmp = EXP.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(EXP)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def row_key(row: dict) -> tuple[str, str, bool]:
    skill = str(row.get("skill") or "")
    trigger = _norm(str(row.get("trigger") or row.get("method") or ""))[:96]
    return (skill, trigger, bool(row.get("negative")))


def is_junk(row: dict) -> bool:
    method = str(row.get("method") or "")
    project = str(row.get("project") or "")
    if method == "accept_probe":
        return True
    if project.startswith("_"):
        return True
    if not row.get("skill") or not row.get("trigger"):
        return True
    return False


def remember(
    skill: str,
    method: str,
    trigger: str,
    project: str = "",
    negative: bool = False,
    oracle: str = "",
    steps: str = "",
) -> dict:
    known = set(list_skill_dirs())
    if skill not in known:
        raise SystemExit(f"skill must be a folder in skills/: got {skill!r}")
    # Skill markdown is the library. This function must never write it.
    if method != "accept_probe":
        if len((trigger or "").strip()) < 8 or len((steps or "").strip()) < 20 or len((oracle or "").strip()) < 8:
            raise SystemExit("remember needs usable trigger, steps, and oracle (reusable method, not a lab dump)")
    for chunk in (skill, method, trigger, project, oracle, steps):
        _reject_secrets(chunk)
    payload = {
        "skill": skill,
        "method": method,
        "trigger": trigger,
        "steps": steps,
        "oracle": oracle,
        "project": project,
        "negative": negative,
        "at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    rows = _load_rows()
    key = row_key(payload)
    for row in rows:
        if row_key(row) == key:
            return {"ok": True, "skipped": True, "reason": "duplicate skill+trigger", "stored": row, "source": str(EXP)}
    rows.append(payload)
    _write_rows(rows)
    return {"ok": True, "skipped": False, "stored": payload, "source": str(EXP)}


def recall(skill: str = "", query: str = "", limit: int = 5) -> dict:
    rows: list[dict] = []
    for row in _load_rows():
        if is_junk(row):
            continue
        if skill and str(row.get("skill") or "") != skill:
            continue
        blob = json.dumps(row, ensure_ascii=False).lower()
        if query and query.lower() not in blob:
            continue
        rows.append(row)
    rows = rows[-max(1, limit) :]
    rows.reverse()
    return {"ok": True, "count": len(rows), "items": rows, "source": str(EXP)}


def inventory(skill: str = "", query: str = "", kind: str = "all") -> dict:
    raw = [row for row in _load_rows() if not is_junk(row)]
    skills = sorted({str(row.get("skill") or "") for row in raw if row.get("skill")})
    items: list[dict] = []
    for row in raw:
        if skill and str(row.get("skill") or "") != skill:
            continue
        if kind == "negative" and not row.get("negative"):
            continue
        if kind == "positive" and row.get("negative"):
            continue
        blob = json.dumps(row, ensure_ascii=False).lower()
        if query and query.lower() not in blob:
            continue
        items.append(row)
    items.reverse()
    pos = sum(1 for row in items if not row.get("negative"))
    neg = sum(1 for row in items if row.get("negative"))
    return {
        "ok": True,
        "count": len(items),
        "positive": pos,
        "negative": neg,
        "skills": skills,
        "items": items,
        "source": str(EXP),
    }


def list_skill_dirs() -> list[str]:
    if not SKILLS.is_dir():
        return []
    names: list[str] = []
    for entry in SKILLS.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if (entry / "SKILL.md").is_file():
            names.append(entry.name)
            continue
        for child in entry.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                names.append(child.name)
    names = sorted(set(names))
    return names


def catalog() -> dict:
    ledger = inventory()
    counts: dict[str, dict[str, int]] = {}
    for row in ledger["items"]:
        name = str(row.get("skill") or "")
        if not name:
            continue
        slot = counts.setdefault(name, {"all": 0, "positive": 0, "negative": 0})
        slot["all"] += 1
        if row.get("negative"):
            slot["negative"] += 1
        else:
            slot["positive"] += 1
    skills = []
    for name in list_skill_dirs():
        slot = counts.get(name, {"all": 0, "positive": 0, "negative": 0})
        skills.append({"name": name, **slot})
    extra = sorted(set(counts) - {s["name"] for s in skills})
    for name in extra:
        skills.append({"name": name, **counts[name]})
    return {
        "ok": True,
        "count": len(skills),
        "with_memory": sum(1 for s in skills if s["all"]),
        "skills": skills,
        "source": str(EXP),
    }


def compact() -> dict:
    before = _load_rows()
    best: dict[tuple[str, str, bool], dict] = {}
    for row in before:
        if is_junk(row):
            continue
        key = row_key(row)
        prev = best.get(key)
        if not prev or len(str(row.get("steps") or "")) >= len(str(prev.get("steps") or "")):
            best[key] = row
    kept = list(best.values())
    _write_rows(kept)
    return {"ok": True, "before": len(before), "kept": len(kept), "dropped": len(before) - len(kept), "source": str(EXP)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cmd",
        nargs="?",
        default="remember",
        choices=["remember", "recall", "compact", "inventory", "catalog"],
    )
    parser.add_argument("--skill", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--trigger", default="")
    parser.add_argument("--oracle", default="")
    parser.add_argument("--steps", default="")
    parser.add_argument("--project", default="")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--q", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--kind", default="all", choices=["all", "positive", "negative"])
    args = parser.parse_args()
    if args.cmd == "recall":
        out = recall(skill=args.skill, query=args.q, limit=args.limit)
    elif args.cmd == "compact":
        out = compact()
    elif args.cmd == "inventory":
        out = inventory(skill=args.skill, query=args.q, kind=args.kind)
    elif args.cmd == "catalog":
        out = catalog()
    else:
        if not args.skill or not args.method or not args.trigger:
            parser.error("remember needs --skill --method --trigger")
        out = remember(
            args.skill,
            args.method,
            args.trigger,
            args.project,
            args.negative,
            oracle=args.oracle,
            steps=args.steps,
        )
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
