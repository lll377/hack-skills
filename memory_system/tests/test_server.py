from __future__ import annotations

import json
import threading
import unittest
import urllib.request
import uuid
from pathlib import Path

from memory_app.config import Settings
from memory_app.server import build_server


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f".test-memory-{uuid.uuid4().hex}.db"
        settings = Settings(
            host="127.0.0.1",
            port=0,
            db_path=self.db_path,
            distill_interval_seconds=60,
        )
        self.server, self.scheduler = build_server(settings)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.server.system.db.close_thread_connection()
        for suffix in ("", "-shm", "-wal"):
            (Path(str(self.db_path) + suffix)).unlink(missing_ok=True)

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base_url + path, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json(self, path: str, body: dict) -> dict:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_static_and_chat_api(self) -> None:
        health = self.get_json("/api/health")
        self.assertEqual(health["status"], "ok")

        with urllib.request.urlopen(self.base_url + "/", timeout=3) as response:
            page = response.read().decode("utf-8")
        self.assertIn("仿生记忆控制台", page)

        chat = self.post_json(
            "/api/chat",
            {
                "user_id": "api_user",
                "session_id": "session_1",
                "message": "我叫小林，职业是设计师",
            },
        )
        self.assertTrue(chat["memory"]["encoded"])
        memories = self.get_json("/api/memories?user_id=api_user")
        self.assertEqual(memories["stats"]["short"], 1)


if __name__ == "__main__":
    unittest.main()
