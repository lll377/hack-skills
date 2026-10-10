from __future__ import annotations

import argparse
import json
import mimetypes
import re
import signal
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

TOOLS = Path("/Users/l/Desktop/Grok/hack-skills/tools")
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from src_memory import catalog as experience_catalog  # noqa: E402
from src_memory import inventory as experience_inventory  # noqa: E402

from .agent import MemorySystem
from .config import Settings
from .memory_layers import ConsolidationScheduler


IDENTIFIER = re.compile(r"^[\w.@+-]{1,100}$", re.UNICODE)
STATIC_ROOT = Path(__file__).with_name("static")


class MemoryHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], system: MemorySystem):
        super().__init__(address, MemoryRequestHandler)
        self.system = system


class MemoryRequestHandler(BaseHTTPRequestHandler):
    server: MemoryHTTPServer
    protocol_version = "HTTP/1.1"

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            self.server.system.db.close_thread_connection()

    def do_GET(self) -> None:
        try:
            self._get()
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:
        try:
            self._post()
        except Exception as exc:
            self._error(exc)

    def do_DELETE(self) -> None:
        try:
            self._delete()
        except Exception as exc:
            self._error(exc)

    def _get(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            self._json(
                {
                    "status": "ok",
                    "service": "bionic-memory",
                    "version": "1.0.0",
                    "model": {
                        "enabled": self.server.system.llm.enabled,
                        "name": self.server.system.settings.openai_model,
                    },
                    "ledger": {
                        "count": experience_inventory()["count"],
                        "source": experience_inventory()["source"],
                    },
                }
            )
            return
        if parsed.path == "/api/experience":
            skill = (query.get("skill") or [""])[0]
            q = (query.get("q") or [""])[0]
            kind = (query.get("kind") or ["all"])[0] or "all"
            if kind not in {"all", "positive", "negative"}:
                kind = "all"
            self._json(experience_inventory(skill=skill, query=q, kind=kind))
            return
        if parsed.path == "/api/skills":
            self._json(experience_catalog())
            return
        if parsed.path == "/api/sessions":
            user_id = self._query_id(query, "user_id")
            self._json({"items": self.server.system.sessions(user_id)})
            return
        if parsed.path == "/api/history":
            user_id = self._query_id(query, "user_id")
            session_id = self._query_id(query, "session_id")
            items = self.server.system.instant.history(user_id, session_id, 100)
            self._json({"items": items})
            return
        if parsed.path == "/api/memories":
            user_id = self._query_id(query, "user_id")
            self._json(
                {
                    "stats": self.server.system.stats(user_id),
                    "short": self.server.system.short.list(user_id),
                    "graph": self.server.system.long.graph(user_id),
                }
            )
            return
        if parsed.path == "/api/events":
            user_id = self._query_id(query, "user_id")
            self._json({"items": self.server.system.events(user_id)})
            return
        if parsed.path.startswith("/api/"):
            self._json({"error": "route not found"}, HTTPStatus.NOT_FOUND)
            return
        self._static(parsed.path)

    def _post(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            data = self._body()
            user_id = self._body_id(data, "user_id")
            session_id = self._body_id(data, "session_id")
            message = str(data.get("message", "")).strip()
            if not message or len(message) > 16000:
                raise RequestError("message must contain 1 to 16000 characters")
            image_description = data.get("image_description")
            if image_description is not None and not isinstance(image_description, str):
                raise RequestError("image_description must be a string")
            result = self.server.system.agent(user_id, session_id).chat_step(
                message, image_description
            )
            self._json(result.to_dict(), HTTPStatus.CREATED)
            return
        if parsed.path == "/api/consolidate":
            data = self._body()
            user_id = self._body_id(data, "user_id")
            result = self.server.system.long.consolidate(user_id)
            self._json(result)
            return
        self._json({"error": "route not found"}, HTTPStatus.NOT_FOUND)

    def _delete(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/memories":
            user_id = self._query_id(query, "user_id")
            self._json({"deleted": self.server.system.clear_user(user_id)})
            return
        self._json({"error": "route not found"}, HTTPStatus.NOT_FOUND)

    def _static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (STATIC_ROOT / relative).resolve()
        try:
            target.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self._json({"error": "invalid path"}, HTTPStatus.BAD_REQUEST)
            return
        if not target.is_file():
            target = STATIC_ROOT / "index.html"
        content = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def _body(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
        if content_type != "application/json":
            raise RequestError("Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise RequestError("invalid Content-Length") from exc
        if length < 2 or length > 65536:
            raise RequestError("request body size is invalid")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise RequestError("request body must be a JSON object")
        return payload

    def _query_id(self, query: dict[str, list[str]], name: str) -> str:
        value = query.get(name, [""])[0]
        return self._validate_id(value, name)

    def _body_id(self, data: dict[str, Any], name: str) -> str:
        return self._validate_id(data.get(name), name)

    @staticmethod
    def _validate_id(value: Any, name: str) -> str:
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise RequestError(
                f"{name} must be 1 to 100 letters, numbers, or . _ @ + -"
            )
        return value

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(content)

    def _error(self, exc: Exception) -> None:
        if isinstance(exc, RequestError) or isinstance(exc, ValueError):
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        else:
            self.log_error("Unhandled error: %r", exc)
            self._json({"error": "internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


class RequestError(ValueError):
    pass


def build_server(settings: Settings) -> tuple[MemoryHTTPServer, ConsolidationScheduler]:
    system = MemorySystem(settings)
    scheduler = ConsolidationScheduler(
        system.short, system.long, settings.distill_interval_seconds
    )
    server = MemoryHTTPServer((settings.host, settings.port), system)
    return server, scheduler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bionic memory service")
    parser.add_argument("--host", help="Bind host (overrides MEMORY_HOST)")
    parser.add_argument("--port", type=int, help="Bind port (overrides MEMORY_PORT)")
    parser.add_argument("--db", type=Path, help="SQLite path (overrides MEMORY_DB_PATH)")
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.host or args.port or args.db:
        settings = Settings(
            **{
                **{field: getattr(settings, field) for field in settings.__dataclass_fields__},
                **({"host": args.host} if args.host else {}),
                **({"port": args.port} if args.port else {}),
                **({"db_path": args.db} if args.db else {}),
            }
        )
    settings.validate()
    server, scheduler = build_server(settings)
    scheduler.start()

    def shutdown(_signum: int, _frame: Any) -> None:
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)
    print(f"Bionic Memory is running at http://{settings.host}:{settings.port}")
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        scheduler.stop()
        server.server_close()


if __name__ == "__main__":
    main()
