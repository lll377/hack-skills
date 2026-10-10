from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from memory_app.agent import MemorySystem
from memory_app.config import Settings
from memory_app.processor import DeepProcessor
from memory_app.llm import OpenAICompatibleClient


class MemorySystemTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f".test-memory-{uuid.uuid4().hex}.db"
        self.settings = Settings(
            db_path=self.db_path,
            distill_interval_seconds=60,
        )
        self.system = MemorySystem(self.settings)

    def tearDown(self) -> None:
        self.system.db.close_thread_connection()
        for suffix in ("", "-shm", "-wal"):
            (Path(str(self.db_path) + suffix)).unlink(missing_ok=True)

    def test_depth_processing_and_fact_extraction(self) -> None:
        processor = DeepProcessor(OpenAICompatibleClient(self.settings))
        shallow = processor.analyze("你好")
        deep = processor.analyze("我叫张三，今年25岁，职业是程序员，我喜欢咖啡")

        self.assertFalse(shallow.keep)
        self.assertTrue(deep.keep)
        facts = {(item.relation, item.target_name) for item in deep.facts}
        self.assertIn(("HAS_NAME", "张三"), facts)
        self.assertIn(("HAS_AGE", "25"), facts)
        self.assertIn(("HAS_OCCUPATION", "程序员"), facts)
        self.assertIn(("LIKES", "咖啡"), facts)

    def test_cross_session_recall_and_consolidation(self) -> None:
        first = self.system.agent("user_001", "session_a")
        result = first.chat_step("我叫张三，今年25岁，职业是程序员")
        self.assertTrue(result.encoded)
        self.assertEqual(self.system.stats("user_001")["short"], 1)

        second = self.system.agent("user_001", "session_b")
        recalled = second.chat_step("你记得我是谁吗？")
        self.assertTrue(recalled.short_recall)
        self.assertIn("张三", recalled.answer)

        consolidated = self.system.long.consolidate("user_001")
        self.assertGreaterEqual(consolidated["facts"], 3)
        graph = self.system.long.graph("user_001")
        targets = {node["name"] for node in graph["nodes"]}
        self.assertIn("张三", targets)
        self.assertIn("程序员", targets)

        long_recalled = self.system.agent("user_001", "session_c").chat_step("我是谁？")
        self.assertTrue(long_recalled.long_recall)
        self.assertIn("HAS_NAME：张三", long_recalled.answer)

    def test_user_isolation(self) -> None:
        self.system.agent("alice", "one").chat_step("我叫爱丽丝，我喜欢爵士乐")
        bob_result = self.system.agent("bob", "one").chat_step("你记得我是谁吗？")
        self.assertFalse(bob_result.short_recall)
        self.assertNotIn("爱丽丝", bob_result.answer)
        self.assertEqual(self.system.stats("bob")["short"], 0)

    def test_expired_vectors_are_really_deleted(self) -> None:
        self.system.agent("user_001", "one").chat_step("请记住我的目标是完成记忆系统")
        expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds")
        self.system.db.connection().execute(
            "UPDATE short_memories SET expires_at = ? WHERE user_id = ?",
            (expired, "user_001"),
        )
        deleted = self.system.short.purge_expired("user_001")
        self.assertEqual(deleted, 1)
        self.assertEqual(self.system.stats("user_001")["short"], 0)

    def test_clear_user_does_not_touch_other_users(self) -> None:
        self.system.agent("alice", "one").chat_step("我叫爱丽丝")
        self.system.agent("bob", "one").chat_step("我叫鲍勃")
        self.system.long.consolidate("alice")
        deleted = self.system.clear_user("alice")
        self.assertGreater(deleted["instant_messages"], 0)
        self.assertEqual(self.system.stats("alice")["instant"], 0)
        self.assertGreater(self.system.stats("bob")["instant"], 0)


if __name__ == "__main__":
    unittest.main()
