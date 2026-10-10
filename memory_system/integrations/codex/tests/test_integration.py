from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from recall_memory import Candidate, score, tokens
from redact import redact_text, redact_value
from store_checkpoint import checkpoint_id, infer_checkpoint
from memory_client import load_settings
from consolidate_lab import normalize_payload, valid_completion


class IntegrationUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_settings()

    def test_redaction_preserves_conclusion(self) -> None:
        value = redact_text("每轮重新获取 Token。 Authorization: Bearer abc password=secret")
        self.assertIn("每轮重新获取 Token", value)
        self.assertNotIn("abc", value)
        self.assertNotIn("secret", value)

    def test_relevance_prefers_csrf_memory(self) -> None:
        query = "动态 CSRF Token 应当如何处理"
        relevant = Candidate("long", "动态 CSRF 场景中，每轮请求前应重新获取有效 Token", "", 1.0)
        unrelated = Candidate("short", "SQL 注入排序字段", "", 1.0)
        self.assertGreater(score(query, relevant), score(query, unrelated))
        self.assertIn("csrf", tokens(query))

    def test_checkpoint_is_structured_and_deterministic(self) -> None:
        item = infer_checkpoint("测试 CSRF", "下一步重新取 Token", self.settings)
        self.assertEqual(item["漏洞类别"], "CSRF")
        first = checkpoint_id("u", "s", "t", "p", "a")
        second = checkpoint_id("u", "s", "t", "p", "a")
        self.assertEqual(first, second)

    def test_consolidation_requires_verified_condition(self) -> None:
        payload = normalize_payload({"可复用经验": "经验", "成功判据": "待验证"})
        self.assertFalse(valid_completion(payload)[0])
        payload["成功判据"] = "当前靶场已完成并验证"
        self.assertTrue(valid_completion(payload)[0])

    def test_all_required_redaction_forms(self) -> None:
        markers = [
            "csrf=RAW1", "csrf_token=RAW2", "_csrf=RAW3", "csrftoken=RAW4",
            "token=RAW5", "access_token=RAW6", "refresh_token=RAW7",
            "password=RAW8", "passwd=RAW9", "secret=RAW10",
            '"csrf": "RAW11"', "'csrf': 'RAW12'", "csrf: RAW13", "csrf%3DRAW14",
            "https://host/path?csrf=RAW15&password=RAW16",
        ]
        output = redact_text(" | ".join(markers))
        for index in range(1, 17):
            self.assertNotIn(f"RAW{index}", output)
        self.assertIn("[REDACTED]", output)
        nested = redact_value({"outer": [{"csrf": "RAW17", "note": "???????? CSRF Token"}], "body": "password=RAW18&token=RAW19"})
        serialized = json.dumps(nested, ensure_ascii=False)
        for index in (17, 18, 19):
            self.assertNotIn(f"RAW{index}", serialized)
        self.assertIn("???????? CSRF Token", serialized)


if __name__ == "__main__":
    unittest.main()
