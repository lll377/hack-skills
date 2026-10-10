from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable


LATIN_WORD = re.compile(r"[a-zA-Z0-9_]+")
CJK_RUN = re.compile(r"[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = LATIN_WORD.findall(lowered)
    for run in CJK_RUN.findall(lowered):
        tokens.extend(run)
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


class HashEmbedding:
    """Deterministic local embeddings suitable for private, dependency-free recall."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            index = value % self.dimensions
            vector[index] += 1.0 if value & 1 else -1.0
        magnitude = math.sqrt(sum(item * item for item in vector))
        if magnitude:
            return [item / magnitude for item in vector]
        return vector

    @staticmethod
    def dumps(vector: list[float]) -> str:
        return json.dumps(vector, separators=(",", ":"))

    @staticmethod
    def loads(raw: str) -> list[float]:
        return [float(item) for item in json.loads(raw)]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
