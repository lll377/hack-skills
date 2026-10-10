from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory_client import MemoryClient, MemoryUnavailable, load_settings
from redact import redact_text, redact_value, safe_json_dumps


REQUIRED_FIELDS = (
    "平台", "靶场名称", "漏洞类别", "核心原理", "已验证步骤", "实际观察",
    "成功判据", "失败尝试及原因", "可复用经验", "证据路径", "验证状态",
)


def _state_path(settings: dict[str, Any]) -> Path:
    path = Path(str(settings["state_dir"]))
    path.mkdir(parents=True, exist_ok=True)
    return path / "consolidation-index.json"


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {"consolidated": {}}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"consolidated": {}}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(safe_json_dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "平台": payload.get("平台", payload.get("platform", "PortSwigger Web Security Academy")),
        "靶场名称": payload.get("靶场名称", payload.get("lab_name", "未识别靶场")),
        "漏洞类别": payload.get("漏洞类别", payload.get("vulnerability", "未识别")),
        "核心原理": payload.get("核心原理", payload.get("principle", payload.get("已确认结论", "待补充"))),
        "已验证步骤": payload.get("已验证步骤", payload.get("verified_steps", payload.get("已执行操作", "待补充"))),
        "实际观察": payload.get("实际观察", payload.get("observations", "待补充")),
        "成功判据": payload.get("成功判据", payload.get("success_criteria", "当前靶场已完成并验证")),
        "失败尝试及原因": payload.get("失败尝试及原因", payload.get("failed_attempts", "未记录明确失败尝试")),
        "可复用经验": payload.get("可复用经验", payload.get("reusable_experience", payload.get("已确认结论", "待补充"))),
        "证据路径": payload.get("证据路径", payload.get("evidence_paths", [])),
        "验证状态": payload.get("验证状态", payload.get("verification_status", "verified")),
    }
    if isinstance(mapping["证据路径"], str):
        mapping["证据路径"] = [mapping["证据路径"]] if mapping["证据路径"] else []
    return redact_value(mapping)


def valid_completion(payload: dict[str, Any]) -> tuple[bool, str]:
    text = json.dumps(payload, ensure_ascii=False)
    if re.search(r"(?i)\bsolved\b", text):
        return True, "solved_marker"
    if "当前靶场已完成并验证" in text:
        return True, "explicit_user_confirmation"
    for value in payload.get("证据路径", []):
        path = Path(str(value))
        if path.exists() and re.search(r"(?i)(solved|success|proof|evidence|完成|成功|验证)", path.name):
            return True, "success_evidence_path"
    return False, "completion_not_verified"


def consolidate_payload(payload: dict[str, Any], user_id: str, session_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_payload(payload)
    valid, reason = valid_completion(normalized)
    if not valid:
        return {"status": "not_consolidated", "reason": reason}
    digest = hashlib.sha256(json.dumps([user_id, normalized], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    marker = f"[codex_consolidation id={digest}]"
    path = _state_path(settings)
    index = _load(path)
    consolidated = index.setdefault("consolidated", {})
    if digest in consolidated:
        return {"status": "duplicate", "consolidation_id": digest}
    client = MemoryClient.from_settings(settings)
    memories = client.memories(user_id)
    if any(marker in str(item.get("content", "")) for item in memories.get("short", [])):
        consolidated[digest] = {"stored_at": datetime.now(timezone.utc).isoformat(), "source": "remote_dedup"}
        _save(path, index)
        return {"status": "duplicate", "consolidation_id": digest, "source": "remote"}
    reusable = str(normalized["可复用经验"])
    message = f"请记住 {reusable}\n靶场巩固经验：{marker}\n" + json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    stored = client.chat(user_id, session_id, message)
    result = client.consolidate(user_id)
    consolidated[digest] = {"stored_at": datetime.now(timezone.utc).isoformat(), "reason": reason, "api_result": result}
    _save(path, index)
    return {"status": "consolidated", "consolidation_id": digest, "reason": reason, "encoded": bool(stored.get("memory", {}).get("encoded")), "api_result": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings")
    parser.add_argument("--input", help="JSON file containing consolidation fields")
    parser.add_argument("--session-id", default="codex-consolidation")
    parser.add_argument("--experience")
    parser.add_argument("--lab-name", default="user_001 CSRF memory lab")
    parser.add_argument("--vulnerability", default="CSRF")
    parser.add_argument("--verified", action="store_true")
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args()
    settings = load_settings(args.settings)
    if args.input:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    else:
        experience = redact_text(args.experience or "")
        payload = {
            "平台": "PortSwigger Web Security Academy",
            "靶场名称": redact_text(args.lab_name),
            "漏洞类别": redact_text(args.vulnerability),
            "核心原理": experience or "待补充",
            "已验证步骤": experience or "待补充",
            "实际观察": experience or "待补充",
            "成功判据": "当前靶场已完成并验证" if args.verified else "待验证",
            "失败尝试及原因": "复用旧 Token 会因动态 Token 失效而失败" if "Token" in experience else "未记录明确失败尝试",
            "可复用经验": experience or "待补充",
            "证据路径": args.evidence,
            "验证状态": "verified" if args.verified else "in_progress",
        }
    try:
        if not settings.get("enabled", True):
            raise MemoryUnavailable("integration_disabled")
        result = consolidate_payload(payload, str(settings["user_id"]), args.session_id, settings)
    except (MemoryUnavailable, OSError, ValueError) as exc:
        result = {"status": "skipped", "reason": "service_unavailable", "detail": redact_text(str(exc))[:200]}
    print(safe_json_dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
