from __future__ import annotations
import json
import re
from typing import Any

REPLACEMENT = "[REDACTED]"
SENSITIVE_KEYS = {"csrf", "csrf_token", "_csrf", "csrftoken", "token", "access_token", "refresh_token", "password", "passwd", "pwd", "secret", "cookie", "authorization", "api_key", "apikey", "x_api_key"}
_KEY_ALT = "|".join(sorted((re.escape(k) for k in SENSITIVE_KEYS), key=len, reverse=True))
_AUTH = re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)?\s*)([^\s,;\"']+)")
_BEARER = re.compile(r"(?i)(\bbearer\s+)([^\s,;\"']+)")
_SET_COOKIE = re.compile(r"(?i)(set-cookie\s*:\s*)([^\r\n]+)")
_COOKIE = re.compile(r"(?i)(?<![-\w])(cookie\s*:\s*)([^\r\n]+)")
_API_KEY = re.compile(r"(?i)((?:api[ _-]?key|x-api-key)\s*[:=]\s*)([\"']?)([^\s,;&\"']+)([\"']?)")
_QUOTED = re.compile(rf"(?i)([\"'](?:{_KEY_ALT})[\"']\s*:\s*)([\"'])(.*?)(\2)")
_PLAIN = re.compile(rf"(?i)(?<![\w-])((?:{_KEY_ALT})\s*[:=]\s*)([\"']?)([^\s,;&\"']+)([\"']?)")
_ENCODED = re.compile(rf"(?i)(?<![\w-])((?:{_KEY_ALT}|api(?:%20|\+|_)?key)%3[dD])([^%&\s]+)")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)([^/@\s:]+):([^/@\s]+)@")


def _key(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(value).strip().lower())


def redact_text(value: str, replacement: str = REPLACEMENT) -> str:
    text = str(value or "")
    stripped = text.strip()
    if stripped[:1] in "[{" and stripped[-1:] in "]}":
        try: parsed = json.loads(stripped)
        except (json.JSONDecodeError, TypeError): pass
        else: return json.dumps(redact_value(parsed, replacement), ensure_ascii=False, separators=(",", ":"))
    text = _JWT.sub(replacement, text)
    text = _URL_CREDENTIALS.sub(lambda m: m.group(1) + replacement + "@", text)
    text = _AUTH.sub(lambda m: m.group(1) + replacement, text)
    text = _BEARER.sub(lambda m: m.group(1) + replacement, text)
    text = _SET_COOKIE.sub(lambda m: m.group(1) + replacement, text)
    text = _COOKIE.sub(lambda m: m.group(1) + replacement, text)
    text = _API_KEY.sub(lambda m: m.group(1) + (m.group(2) or "") + replacement + (m.group(4) or ""), text)
    text = _QUOTED.sub(lambda m: m.group(1) + m.group(2) + replacement + m.group(4), text)
    text = _ENCODED.sub(lambda m: m.group(1) + replacement, text)
    text = _PLAIN.sub(lambda m: m.group(1) + (m.group(2) or "") + replacement + (m.group(4) or ""), text)
    return text


def redact_value(value: Any, replacement: str = REPLACEMENT) -> Any:
    if isinstance(value, str): return redact_text(value, replacement)
    if isinstance(value, dict): return {str(k): replacement if _key(k) in SENSITIVE_KEYS else redact_value(v, replacement) for k, v in value.items()}
    if isinstance(value, list): return [redact_value(v, replacement) for v in value]
    if isinstance(value, tuple): return tuple(redact_value(v, replacement) for v in value)
    return value


def safe_json_dumps(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(redact_value(value), ensure_ascii=False, indent=indent)
