from __future__ import annotations

import json
import math
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import Settings
from .db import Database
from .embeddings import HashEmbedding, cosine_similarity, tokenize
from .models import Fact, RecallItem
from .processor import DeepProcessor


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


class InstantMemory:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.max_chars = settings.instant_max_chars

    def add(self, user_id: str, session_id: str, role: str, content: str) -> None:
        now = iso(utc_now())
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO instant_messages(user_id, session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, session_id, role, content, now),
            )
            rows = connection.execute(
                "SELECT id, length(content) AS size FROM instant_messages "
                "WHERE user_id = ? AND session_id = ? ORDER BY id DESC",
                (user_id, session_id),
            ).fetchall()
            kept = 0
            delete_ids: list[int] = []
            for row in rows:
                kept += int(row["size"] or 0)
                if kept > self.max_chars:
                    delete_ids.append(int(row["id"]))
            if delete_ids:
                connection.executemany(
                    "DELETE FROM instant_messages WHERE id = ?",
                    ((item,) for item in delete_ids),
                )

    def history(
        self, user_id: str, session_id: str, limit: int = 30
    ) -> list[dict[str, str]]:
        rows = self.db.connection().execute(
            "SELECT role, content, created_at FROM ("
            "SELECT id, role, content, created_at FROM instant_messages "
            "WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT ?"
            ") ORDER BY id",
            (user_id, session_id, max(1, min(limit, 200))),
        ).fetchall()
        return [dict(row) for row in rows]


class WorkingMemory:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.text_limit = settings.working_text_limit

    def add(self, user_id: str, session_id: str, channel: str, content: str) -> None:
        limit = self.text_limit if channel == "text" else 8
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO working_items(user_id, session_id, channel, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, session_id, channel, content, iso(utc_now())),
            )
            connection.execute(
                "DELETE FROM working_items WHERE id IN ("
                "SELECT id FROM working_items WHERE user_id = ? AND session_id = ? "
                "AND channel = ? ORDER BY id DESC LIMIT -1 OFFSET ?)",
                (user_id, session_id, channel, limit),
            )

    def fuse(self, user_id: str, session_id: str) -> str:
        rows = self.db.connection().execute(
            "SELECT channel, content FROM working_items WHERE user_id = ? "
            "AND session_id = ? ORDER BY id",
            (user_id, session_id),
        ).fetchall()
        text_items = [row["content"] for row in rows if row["channel"] == "text"]
        visual_items = [row["content"] for row in rows if row["channel"] == "visual"]
        parts: list[str] = []
        if text_items:
            parts.append("对话要点：" + "；".join(text_items[-6:]))
        if visual_items:
            parts.append("视觉信息：" + "；".join(visual_items[-3:]))
        summary = "\n".join(parts)[:5000]
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO working_buffers(user_id, session_id, summary, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(user_id, session_id) DO UPDATE SET "
                "summary = excluded.summary, updated_at = excluded.updated_at",
                (user_id, session_id, summary, iso(utc_now())),
            )
        return summary

    def snapshot(self, user_id: str, session_id: str) -> dict[str, Any]:
        items = self.db.connection().execute(
            "SELECT channel, content, created_at FROM working_items WHERE user_id = ? "
            "AND session_id = ? ORDER BY id",
            (user_id, session_id),
        ).fetchall()
        buffer_row = self.db.connection().execute(
            "SELECT summary, updated_at FROM working_buffers WHERE user_id = ? AND session_id = ?",
            (user_id, session_id),
        ).fetchone()
        return {
            "items": [dict(item) for item in items],
            "buffer": dict(buffer_row) if buffer_row else None,
        }


class ShortTermMemory:
    def __init__(self, db: Database, settings: Settings, embedding: HashEmbedding):
        self.db = db
        self.ttl = timedelta(days=settings.short_ttl_days)
        self.embedding = embedding

    def save(
        self,
        user_id: str,
        session_id: str,
        content: str,
        importance: float,
    ) -> str:
        memory_id = str(uuid.uuid4())
        now = utc_now()
        self.db.connection().execute(
            "INSERT INTO short_memories(id, user_id, session_id, content, embedding, "
            "importance, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                memory_id,
                user_id,
                session_id,
                content,
                self.embedding.dumps(self.embedding.embed(content)),
                max(0.0, min(1.0, importance)),
                iso(now),
                iso(now + self.ttl),
            ),
        )
        return memory_id

    def recall(self, user_id: str, query: str, top_k: int = 5) -> list[RecallItem]:
        self.purge_expired(user_id)
        query_vector = self.embedding.embed(query)
        now = utc_now()
        rows = self.db.connection().execute(
            "SELECT * FROM short_memories WHERE user_id = ? AND expires_at > ?",
            (user_id, iso(now)),
        ).fetchall()
        ranked: list[RecallItem] = []
        for row in rows:
            similarity = cosine_similarity(
                query_vector, self.embedding.loads(row["embedding"])
            )
            created = datetime.fromisoformat(row["created_at"])
            age_ratio = min(1.0, max(0.0, (now - created).total_seconds() / self.ttl.total_seconds()))
            recency = 1.0 - age_ratio
            reinforcement = min(1.0, math.log1p(row["recall_count"]) / 3.0)
            score = similarity * 0.72 + row["importance"] * 0.16 + recency * 0.08 + reinforcement * 0.04
            if similarity > 0.01 or _identity_query(query):
                ranked.append(
                    RecallItem(
                        id=row["id"],
                        content=row["content"],
                        score=round(score, 4),
                        importance=float(row["importance"]),
                        created_at=row["created_at"],
                        layer="short",
                    )
                )
        selected = sorted(ranked, key=lambda item: item.score, reverse=True)[: max(1, min(top_k, 20))]
        if selected:
            recalled_at = iso(now)
            with self.db.transaction() as connection:
                connection.executemany(
                    "UPDATE short_memories SET recall_count = recall_count + 1, "
                    "last_recalled_at = ? WHERE id = ?",
                    ((recalled_at, item.id) for item in selected),
                )
        return selected

    def purge_expired(self, user_id: str | None = None) -> int:
        connection = self.db.connection()
        if user_id is None:
            cursor = connection.execute(
                "DELETE FROM short_memories WHERE expires_at <= ?", (iso(utc_now()),)
            )
        else:
            cursor = connection.execute(
                "DELETE FROM short_memories WHERE user_id = ? AND expires_at <= ?",
                (user_id, iso(utc_now())),
            )
        return cursor.rowcount

    def list(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        self.purge_expired(user_id)
        rows = self.db.connection().execute(
            "SELECT id, session_id, content, importance, created_at, expires_at, "
            "last_recalled_at, recall_count, consolidated_at FROM short_memories "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, max(1, min(limit, 500))),
        ).fetchall()
        return [dict(row) for row in rows]


class LongTermMemory:
    def __init__(self, db: Database, processor: DeepProcessor):
        self.db = db
        self.processor = processor

    def consolidate(self, user_id: str | None = None) -> dict[str, int]:
        query = "SELECT id, user_id, content FROM short_memories WHERE consolidated_at IS NULL"
        params: tuple[Any, ...] = ()
        if user_id is not None:
            query += " AND user_id = ?"
            params = (user_id,)
        rows = self.db.connection().execute(query, params).fetchall()
        memory_count = 0
        fact_count = 0
        for row in rows:
            analysis = self.processor.analyze(row["content"])
            with self.db.transaction() as connection:
                for fact in analysis.facts:
                    self._upsert_fact(connection, row["user_id"], fact)
                    fact_count += 1
                connection.execute(
                    "UPDATE short_memories SET consolidated_at = ? WHERE id = ?",
                    (iso(utc_now()), row["id"]),
                )
            memory_count += 1
        return {"memories": memory_count, "facts": fact_count}

    def _upsert_fact(self, connection: Any, user_id: str, fact: Fact) -> None:
        now = iso(utc_now())
        source_id = self._upsert_entity(
            connection, user_id, fact.source_type, fact.source_name, now
        )
        target_id = self._upsert_entity(
            connection, user_id, fact.target_type, fact.target_name, now
        )
        connection.execute(
            "INSERT INTO long_relations(user_id, source_id, relation_type, target_id, "
            "evidence, strength, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1.0, ?, ?) "
            "ON CONFLICT(user_id, source_id, relation_type, target_id) DO UPDATE SET "
            "evidence = excluded.evidence, strength = min(10.0, long_relations.strength + 0.2), "
            "updated_at = excluded.updated_at",
            (
                user_id,
                source_id,
                fact.relation,
                target_id,
                fact.evidence,
                now,
                now,
            ),
        )

    @staticmethod
    def _upsert_entity(
        connection: Any, user_id: str, entity_type: str, name: str, now: str
    ) -> int:
        connection.execute(
            "INSERT INTO long_entities(user_id, entity_type, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, entity_type, name) DO UPDATE SET "
            "strength = min(10.0, long_entities.strength + 0.1), updated_at = excluded.updated_at",
            (user_id, entity_type[:80], name[:200], now, now),
        )
        row = connection.execute(
            "SELECT id FROM long_entities WHERE user_id = ? AND entity_type = ? AND name = ?",
            (user_id, entity_type[:80], name[:200]),
        ).fetchone()
        return int(row["id"])

    def recall(self, user_id: str, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        rows = self.db.connection().execute(
            "SELECT r.id, s.name AS source, s.entity_type AS source_type, "
            "r.relation_type AS relation, t.name AS target, t.entity_type AS target_type, "
            "r.evidence, r.strength, r.recall_count "
            "FROM long_relations r JOIN long_entities s ON s.id = r.source_id "
            "JOIN long_entities t ON t.id = r.target_id WHERE r.user_id = ?",
            (user_id,),
        ).fetchall()
        query_tokens = set(tokenize(query))
        identity = _identity_query(query)
        ranked: list[tuple[float, Any]] = []
        for row in rows:
            haystack = f"{row['source']} {row['relation']} {row['target']} {row['evidence']}"
            overlap = len(query_tokens.intersection(tokenize(haystack)))
            if overlap or identity:
                score = overlap + min(2.0, float(row["strength"]) / 5.0)
                ranked.append((score, row))
        selected = sorted(ranked, key=lambda item: item[0], reverse=True)[: max(1, min(top_k, 50))]
        now = iso(utc_now())
        if selected:
            with self.db.transaction() as connection:
                connection.executemany(
                    "UPDATE long_relations SET recall_count = recall_count + 1, "
                    "last_recalled_at = ?, strength = min(10.0, strength + 0.05) WHERE id = ?",
                    ((now, row["id"]) for _, row in selected),
                )
        return [
            {
                "id": row["id"],
                "source": row["source"],
                "source_type": row["source_type"],
                "relation": row["relation"],
                "target": row["target"],
                "target_type": row["target_type"],
                "evidence": row["evidence"],
                "strength": round(float(row["strength"]), 3),
                "score": round(score, 3),
            }
            for score, row in selected
        ]

    def graph(self, user_id: str) -> dict[str, list[dict[str, Any]]]:
        entities = self.db.connection().execute(
            "SELECT id, entity_type AS type, name, strength, recall_count, created_at, "
            "updated_at FROM long_entities WHERE user_id = ? ORDER BY strength DESC, id",
            (user_id,),
        ).fetchall()
        relations = self.db.connection().execute(
            "SELECT id, source_id AS source, target_id AS target, relation_type AS type, "
            "strength, recall_count, evidence, updated_at FROM long_relations "
            "WHERE user_id = ? ORDER BY strength DESC, id",
            (user_id,),
        ).fetchall()
        return {
            "nodes": [dict(item) for item in entities],
            "edges": [dict(item) for item in relations],
        }


class ConsolidationScheduler:
    def __init__(
        self,
        short: ShortTermMemory,
        long: LongTermMemory,
        interval_seconds: int,
    ):
        self.short = short
        self.long = long
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._loop, name="memory-consolidation", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self.short.purge_expired()
            self.long.consolidate()


def _identity_query(query: str) -> bool:
    compact = "".join(query.lower().split())
    signals = ("我是谁", "关于我", "我的信息", "记得我", "你记得", "whoami")
    return any(signal in compact for signal in signals)
