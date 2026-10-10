from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from redact import redact_value


class MemoryUnavailable(RuntimeError):
    pass


class MemoryAPIError(RuntimeError):
    pass


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    settings_path = Path(path) if path else Path(__file__).with_name("settings.json")
    data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    data["service_url"] = os.getenv("MEMORY_SYSTEM_URL", str(data["service_url"])).rstrip("/")
    data["user_id"] = os.getenv("MEMORY_SYSTEM_USER_ID", str(data["user_id"]))
    state_dir = Path(str(data.get("state_dir", ".codex/memory-state")))
    if not state_dir.is_absolute():
        state_dir = project_root() / state_dir
    data["state_dir"] = str(state_dir.resolve())
    data["enabled"] = not (state_dir / "disabled").exists()
    return data


@dataclass(slots=True)
class MemoryClient:
    base_url: str
    timeout: float = 1.5

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "MemoryClient":
        return cls(str(settings["service_url"]).rstrip("/"), float(settings.get("request_timeout_seconds", 1.5)))

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(redact_value(payload), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MemoryUnavailable(str(exc)) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MemoryAPIError(f"invalid JSON from {path}") from exc
        if not isinstance(data, dict):
            raise MemoryAPIError(f"unexpected response from {path}")
        if data.get("error"):
            raise MemoryAPIError(str(data["error"]))
        return data

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def memories(self, user_id: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"user_id": user_id})
        return self._request("GET", f"/api/memories?{query}")

    def sessions(self, user_id: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"user_id": user_id})
        return list(self._request("GET", f"/api/sessions?{query}").get("items", []))

    def history(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"user_id": user_id, "session_id": session_id})
        return list(self._request("GET", f"/api/history?{query}").get("items", []))

    def events(self, user_id: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"user_id": user_id})
        return list(self._request("GET", f"/api/events?{query}").get("items", []))

    def chat(self, user_id: str, session_id: str, message: str, image_description: str | None = None) -> dict[str, Any]:
        return self._request("POST", "/api/chat", {"user_id": user_id, "session_id": session_id, "message": message, "image_description": image_description})

    def consolidate(self, user_id: str) -> dict[str, Any]:
        return self._request("POST", "/api/consolidate", {"user_id": user_id})
