from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory_client import MemoryClient, MemoryUnavailable, load_settings
from redact import redact_text, redact_value, safe_json_dumps


VULN_KEYWORDS = {
    "csrf": "CSRF",
    "cross-site request forgery": "CSRF",
    "sql injection": "SQL injection",
    "sqli": "SQL injection",
    "xss": "Cross-site scripting",
    "ssrf": "SSRF",
    "request smuggling": "HTTP request smuggling",
    "idor": "IDOR/BOLA",
    "bola": "IDOR/BOLA",
    "oauth": "OAuth/OIDC",
    "jwt": "JWT",
    "race condition": "Race condition",
    "path traversal": "Path traversal",
    "file upload": "Insecure file upload",
    "ssti": "SSTI",
    "xxe": "XXE",
    "cors": "CORS",
    "clickjacking": "Clickjacking",
    "websocket": "WebSocket security",
}


def compact(text: str, limit: int) -> str:
    value = " ".join(redact_text(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def detect_platform(text: str, default: str) -> str:
    lowered = text.lower()
    if "portswigger" in lowered or "web security academy" in lowered or "靶场" in text:
        return "PortSwigger Web Security Academy"
    return default


def detect_lab(text: str, default: str) -> str:
    patterns = [
        r"(?im)(?:lab|靶场|实验)(?:名称|名)?\s*[:：]\s*([^\r\n]{3,160})",
        r"(?im)PortSwigger[^\r\n]{0,40}[-—:]\s*([^\r\n]{3,160})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return compact(match.group(1), 160)
    return default


def detect_vulnerability(text: str) -> str:
    lowered = text.lower()
    for keyword, label in VULN_KEYWORDS.items():
        if keyword in lowered:
            return label
    return "未识别"


def evidence_paths(text: str) -> list[str]:
    patterns = [
        r"(?<![\w])(?:[A-Za-z]:\\[^\r\n<>|\"]+)",
        r"(?<![\w])(?:\.?\.?[\\/][\w .()\-\\/]+\.[A-Za-z0-9]{1,8})",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            value = compact(match.rstrip(".,;，。；)】]"), 300)
            if value and value not in found:
                found.append(value)
    return found[:8]


def infer_checkpoint(prompt: str, assistant: str, settings: dict[str, Any]) -> dict[str, Any]:
    combined = f"{prompt}\n{assistant}"
    max_field = int(settings.get("checkpoint_max_field_chars", 800))
    failed_lines = [line for line in assistant.splitlines() if re.search(r"(?i)(fail|error|timeout|失败|错误|超时|未通过|无效)", line)]
    next_lines = [line for line in assistant.splitlines() if re.search(r"(?i)(next|下一步|随后|接下来|待办)", line)]
    confirmed = [line for line in assistant.splitlines() if re.search(r"(?i)(confirm|verified|已确认|验证通过|确定|显示 solved|成功)", line)]
    status = "verified" if re.search(r"(?i)(\bsolved\b|已完成并验证|验证通过|success evidence|成功判据)", combined) else "in_progress"
    return {
        "当前任务": compact(prompt, max_field),
        "平台": detect_platform(combined, str(settings.get("platform_default", "PortSwigger Web Security Academy"))),
        "靶场名称": detect_lab(combined, str(settings.get("lab_default", "未识别靶场"))),
        "漏洞类别": detect_vulnerability(combined),
        "已执行操作": compact(assistant, max_field),
        "实际观察": compact(assistant, max_field),
        "已确认结论": compact("；".join(confirmed), max_field) if confirmed else "尚无明确已确认结论",
        "尚未确认内容": "靶场最终完成状态" if status != "verified" else "无",
        "失败尝试及原因": compact("；".join(failed_lines), max_field) if failed_lines else "未记录明确失败尝试",
        "下一步": compact("；".join(next_lines), max_field) if next_lines else "继续执行当前靶场的下一项验证",
        "证据路径": evidence_paths(combined),
        "验证状态": status,
    }


def state_file(settings: dict[str, Any]) -> Path:
    path = Path(str(settings["state_dir"]))
    path.mkdir(parents=True, exist_ok=True)
    return path / "checkpoint-index.json"


def load_index(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {"stored": {}}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"stored": {}}


def save_index(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(safe_json_dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)


def checkpoint_id(user_id: str, session_id: str, turn_id: str, prompt: str, assistant: str) -> str:
    raw = json.dumps([user_id, session_id, turn_id, prompt, assistant], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def remote_has_id(client: MemoryClient, user_id: str, marker: str) -> bool:
    try:
        return any(marker in str(item.get("content", "")) for item in client.memories(user_id).get("short", []))
    except MemoryUnavailable:
        return False


def should_consolidate(prompt: str, assistant: str, checkpoint: dict[str, Any], settings: dict[str, Any]) -> bool:
    if not settings.get("auto_consolidate", True):
        return False
    combined = f"{prompt}\n{assistant}"
    if re.search(r"(?i)\bsolved\b", combined):
        return True
    if "当前靶场已完成并验证" in combined:
        return True
    success_pattern = re.compile(str(settings.get("success_evidence_name_pattern", r"(?i)(solved|success|proof|evidence|完成|成功|验证)")))
    return any(success_pattern.search(Path(path).name) and Path(path).exists() for path in checkpoint.get("证据路径", []))


def store_hook(hook: dict[str, Any], settings: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    user_id = str(settings["user_id"])
    session_id = str(hook.get("session_id") or "codex-unknown-session")
    turn_id = str(hook.get("turn_id") or "unknown-turn")
    assistant = redact_text(str(hook.get("last_assistant_message") or ""))
    if not hook.get("session_id") or not hook.get("turn_id"):
        return {"status": "invalid_hook_input", "reason": "session_id_and_turn_id_required"}
    prompt = ""
    pending_path = Path(str(settings["state_dir"])) / "pending-prompts.json"
    pending = load_index(pending_path)
    prompt = str(pending.get("prompts", {}).get(f"{session_id}:{turn_id}", ""))
    if not prompt:
        prompt = str(hook.get("prompt") or "未获取本轮用户问题")
    prompt = redact_text(prompt)
    cid = checkpoint_id(user_id, session_id, turn_id, prompt, assistant)
    marker = f"[codex_checkpoint id={cid} session={session_id} turn={turn_id}]"
    index_path = state_file(settings)
    index = load_index(index_path)
    stored = index.setdefault("stored", {})
    for existing_id, record in stored.items():
        if str(record.get("session_id")) == session_id and str(record.get("turn_id")) == turn_id:
            return {"status": "duplicate", "checkpoint_id": existing_id, "session_id": session_id, "turn_id": turn_id, "dedup_key": "user_session_turn"}
    if cid in stored:
        return {"status": "duplicate", "checkpoint_id": cid, "session_id": session_id, "turn_id": turn_id, "dedup_key": "content_hash"}
    checkpoint = infer_checkpoint(prompt, assistant, settings)
    content = "请记住以下 Codex 工作进度快照（默认工作/短时记忆，不代表长期结论）：\n" + marker + "\n" + json.dumps(redact_value(checkpoint), ensure_ascii=False, separators=(",", ":"))
    if dry_run:
        return {"status": "dry_run", "checkpoint_id": cid, "content": content, "checkpoint": checkpoint}
    client = MemoryClient.from_settings(settings)
    if remote_has_id(client, user_id, marker):
        stored[cid] = {"stored_at": datetime.now(timezone.utc).isoformat(), "source": "remote_dedup"}
        save_index(index_path, index)
        return {"status": "duplicate", "checkpoint_id": cid, "source": "remote"}
    # The existing API has no working-only endpoint. A locally classified shallow
    # message plus image_description writes instant + working without creating short memory.
    response = client.chat(user_id, session_id, "??", image_description=content)
    stored[cid] = {
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "turn_id": turn_id,
        "working_saved": True,
        "content": content,
        "checkpoint": checkpoint,
    }
    save_index(index_path, index)
    result: dict[str, Any] = {"status": "stored", "checkpoint_id": cid, "session_id": session_id, "turn_id": turn_id, "working_saved": True, "short_encoded": bool(response.get("memory", {}).get("encoded")), "checkpoint": checkpoint}
    if should_consolidate(prompt, assistant, checkpoint, settings):
        from consolidate_lab import consolidate_payload
        result["consolidation"] = consolidate_payload(checkpoint, user_id, session_id, settings)
    return result


def record_prompt_hook(hook: dict[str, Any], settings: dict[str, Any]) -> None:
    session_id = str(hook.get("session_id") or "codex-unknown-session")
    turn_id = str(hook.get("turn_id") or "unknown-turn")
    prompt = compact(str(hook.get("prompt") or ""), 4000)
    path = Path(str(settings["state_dir"])) / "pending-prompts.json"
    data = load_index(path)
    prompts = data.setdefault("prompts", {})
    prompts[f"{session_id}:{turn_id}"] = prompt
    if len(prompts) > 500:
        for key in list(prompts)[:-400]:
            prompts.pop(key, None)
    save_index(path, data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--capture-prompt", action="store_true")
    parser.add_argument("--settings")
    parser.add_argument("--input")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = load_settings(args.settings)
    try:
        if args.input:
            input_path = Path(args.input)
            if not input_path.is_file():
                print(json.dumps({"status": "invalid_input", "reason": "input_file_not_found"}, ensure_ascii=False))
                return 2
            hook = json.loads(input_path.read_text(encoding="utf-8-sig"))
        else:
            hook = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        hook = {}
    if not settings.get("enabled", True):
        print(json.dumps({"continue": True, "suppressOutput": True}, ensure_ascii=False) if args.hook or args.capture_prompt else json.dumps({"status": "skipped", "reason": "integration_disabled"}, ensure_ascii=False))
        return 0
    if args.capture_prompt:
        try:
            record_prompt_hook(hook, settings)
        except OSError:
            pass
        print(json.dumps({"continue": True}, ensure_ascii=False))
        return 0
    try:
        result = store_hook(hook, settings, args.dry_run)
    except (MemoryUnavailable, OSError, ValueError) as exc:
        result = {"status": "skipped", "reason": "service_unavailable", "detail": compact(str(exc), 200)}
    if args.hook:
        print(json.dumps({"continue": True, "suppressOutput": True}, ensure_ascii=False))
    else:
        print(safe_json_dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
