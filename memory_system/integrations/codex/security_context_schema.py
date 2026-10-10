from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redact import redact_text, redact_value

FIELDS = (
    "project_name", "platform", "target", "scope", "lab_name",
    "vulnerability_type", "objective", "actions", "observations",
    "confirmed_findings", "unverified_items", "failed_attempts", "blocker",
    "next_step", "tools", "skills", "scripts", "evidence_paths",
    "report_paths", "reusable_lessons", "status", "solved", "updated_at",
)
LIST_FIELDS = {
    "actions", "observations", "confirmed_findings", "unverified_items",
    "failed_attempts", "tools", "skills", "scripts", "evidence_paths",
    "report_paths", "reusable_lessons",
}
VALID_STATUSES = {"IN_PROGRESS", "BLOCKED", "UNVERIFIED", "VERIFIED", "SOLVED", "ABORTED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list(value: Any, limit: int = 30) -> list[str]:
    if value is None:
        return []
    source = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for item in source:
        text = redact_text(str(item)).strip()
        if text and text not in result:
            result.append(text[:1000])
    return result[:limit]


def _text(value: Any, limit: int = 1200) -> str:
    return redact_text(str(value or "")).strip()[:limit]


def empty_context() -> dict[str, Any]:
    data: dict[str, Any] = {field: [] if field in LIST_FIELDS else "" for field in FIELDS}
    data.update({"status": "IN_PROGRESS", "solved": False, "updated_at": utc_now()})
    return data


def normalize_context(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = redact_value(payload or {})
    aliases = {
        "project_name": ("project_name", "project", "项目"),
        "platform": ("platform", "平台"),
        "target": ("target", "asset", "靶场或资产", "目标"),
        "scope": ("scope", "范围"),
        "lab_name": ("lab_name", "lab", "靶场名称", "靶场"),
        "vulnerability_type": ("vulnerability_type", "vulnerability", "漏洞类别"),
        "objective": ("objective", "当前目标", "当前任务", "任务"),
        "actions": ("actions", "已执行步骤", "已执行操作", "已完成步骤"),
        "observations": ("observations", "实际观察"),
        "confirmed_findings": ("confirmed_findings", "已确认结论"),
        "unverified_items": ("unverified_items", "尚未确认", "尚未确认内容"),
        "failed_attempts": ("failed_attempts", "失败尝试", "失败尝试及原因"),
        "blocker": ("blocker", "当前阻塞"),
        "next_step": ("next_step", "下一步"),
        "tools": ("tools", "工具"),
        "skills": ("skills", "Skill", "skills_used"),
        "scripts": ("scripts", "脚本路径"),
        "evidence_paths": ("evidence_paths", "证据路径"),
        "report_paths": ("report_paths", "报告路径"),
        "reusable_lessons": ("reusable_lessons", "可复用经验"),
        "status": ("status", "验证状态"),
        "solved": ("solved",),
        "updated_at": ("updated_at", "更新时间"),
    }
    result = empty_context()
    for field, names in aliases.items():
        value = None
        for name in names:
            if name in source and source[name] not in (None, "", []):
                value = source[name]
                break
        if value is None:
            continue
        if field in LIST_FIELDS:
            result[field] = _list(value)
        elif field == "solved":
            result[field] = bool(value)
        elif field == "status":
            status = str(value).upper().strip()
            legacy = {"IN_PROGRESS": "IN_PROGRESS", "VERIFIED": "VERIFIED", "SOLVED": "SOLVED", "BLOCKED": "BLOCKED", "UNVERIFIED": "UNVERIFIED", "ABORTED": "ABORTED", "IN_PROGRESS": "IN_PROGRESS", "VERIFIED": "VERIFIED"}
            result[field] = legacy.get(status, "IN_PROGRESS")
        elif field == "updated_at":
            result[field] = _text(value, 80) or utc_now()
        else:
            result[field] = _text(value)
    result["solved"] = bool(result["solved"] or result["status"] == "SOLVED")
    if result["status"] in {"VERIFIED", "SOLVED"} and (not result["confirmed_findings"] or not result["evidence_paths"]):
        result["status"] = "UNVERIFIED"
        result["solved"] = False
        if "缺少已确认结论或证据路径" not in result["unverified_items"]:
            result["unverified_items"].append("缺少已确认结论或证据路径")
    result["updated_at"] = utc_now()
    return result


def validate_context(context: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if set(context) != set(FIELDS):
        errors.append("schema_fields_mismatch")
    if context.get("status") not in VALID_STATUSES:
        errors.append("invalid_status")
    for field in LIST_FIELDS:
        if not isinstance(context.get(field), list):
            errors.append(f"{field}_must_be_list")
    if not isinstance(context.get("solved"), bool):
        errors.append("solved_must_be_bool")
    if context.get("status") == "SOLVED" and not context.get("solved"):
        errors.append("solved_status_requires_true")
    if context.get("status") in {"VERIFIED", "SOLVED"}:
        if not context.get("confirmed_findings"):
            errors.append("verified_requires_confirmed_findings")
        if not context.get("evidence_paths"):
            errors.append("verified_requires_evidence_paths")
    return not errors, errors


def merge_context(base: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
    left = normalize_context(base)
    right = normalize_context(update)
    result = dict(left)
    for field in FIELDS:
        value = right[field]
        if field in LIST_FIELDS:
            result[field] = _list([*left[field], *value])
        elif field in {"updated_at"}:
            continue
        elif field == "solved":
            result[field] = bool(left[field] or value)
        elif field == "status":
            order = {"ABORTED": 0, "IN_PROGRESS": 1, "UNVERIFIED": 2, "BLOCKED": 3, "VERIFIED": 4, "SOLVED": 5}
            result[field] = value if order.get(value, 1) >= order.get(left[field], 1) else left[field]
        elif value:
            result[field] = value
    if result["status"] in {"VERIFIED", "SOLVED"} and (not result["confirmed_findings"] or not result["evidence_paths"]):
        result["status"] = "UNVERIFIED"
        result["solved"] = False
    result["updated_at"] = utc_now()
    return normalize_context(result)


def existing_paths(values: list[str]) -> list[str]:
    return [value for value in values if Path(value).exists()]
