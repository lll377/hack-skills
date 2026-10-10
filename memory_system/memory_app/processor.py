from __future__ import annotations

import json
import re

from .llm import LLMError, OpenAICompatibleClient, parse_json_payload
from .models import ContentAnalysis, Fact


LOW_VALUE = re.compile(
    r"^(你好|嗨|哈喽|hello|hi|谢谢|好的|嗯+|哦+|再见|早上好|晚上好)[!！。.\s]*$",
    re.IGNORECASE,
)
HIGH_SIGNALS = re.compile(
    r"(我叫|我的名字|今年\s*\d+\s*岁|职业|工作是|我喜欢|我不喜欢|"
    r"记住|以后|必须|不要|偏好|目标|计划|需求|项目|截止|密码|地址|电话|邮箱)",
    re.IGNORECASE,
)


class DeepProcessor:
    def __init__(self, llm: OpenAICompatibleClient):
        self.llm = llm

    def analyze(self, text: str) -> ContentAnalysis:
        if self.llm.enabled:
            try:
                return self._analyze_with_model(text)
            except (LLMError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                pass
        return self._analyze_locally(text)

    def _analyze_with_model(self, text: str) -> ContentAnalysis:
        response = self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是记忆编码器。判断内容是否值得跨轮保存，并提取事实。"
                        "只输出 JSON：{keep:boolean,importance:0到1,summary:string,reason:string,"
                        "facts:[{source_type,source_name,relation,target_type,target_name,evidence}]}。"
                        "闲聊不保存；身份、偏好、规则、目标、承诺和关键数据应保存。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        data = parse_json_payload(response)
        facts = [
            Fact(
                source_type=str(item.get("source_type", "Person"))[:80],
                source_name=str(item.get("source_name", "用户"))[:200],
                relation=_normalize_relation(str(item.get("relation", "RELATED_TO"))),
                target_type=str(item.get("target_type", "Concept"))[:80],
                target_name=str(item["target_name"])[:200],
                evidence=str(item.get("evidence", text))[:1000],
            )
            for item in data.get("facts", [])
            if item.get("target_name")
        ]
        importance = max(0.0, min(1.0, float(data.get("importance", 0.5))))
        summary = str(data.get("summary", text)).strip()[:2000]
        return ContentAnalysis(
            keep=bool(data.get("keep", importance >= 0.45)),
            importance=importance,
            summary=summary or text,
            facts=facts,
            reason=str(data.get("reason", "model classification"))[:300],
        )

    def _analyze_locally(self, text: str) -> ContentAnalysis:
        cleaned = " ".join(text.strip().split())
        if not cleaned or LOW_VALUE.fullmatch(cleaned):
            return ContentAnalysis(False, 0.1, cleaned, reason="shallow conversation")

        facts = extract_local_facts(cleaned)
        signal_count = len(HIGH_SIGNALS.findall(cleaned))
        importance = 0.32
        if facts:
            importance = 0.82
        elif signal_count:
            importance = min(0.78, 0.5 + signal_count * 0.09)
        elif len(cleaned) >= 80:
            importance = 0.5
        keep = importance >= 0.45
        return ContentAnalysis(
            keep=keep,
            importance=importance,
            summary=cleaned[:2000],
            facts=facts,
            reason="local depth-of-processing rules",
        )


def _normalize_relation(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]", "_", value.strip())
    return (normalized or "RELATED_TO")[:80].upper()


def extract_local_facts(text: str) -> list[Fact]:
    patterns: list[tuple[re.Pattern[str], str, str]] = [
        (re.compile(r"(?:我的名字叫|我叫)\s*([^，。！？,!?\s]{1,30})"), "HAS_NAME", "Name"),
        (re.compile(r"(?:我)?今年\s*(\d{1,3})\s*岁"), "HAS_AGE", "Age"),
        (
            re.compile(r"(?:我的)?职业(?:是|为)?\s*([^，。！？,!?]{1,40})"),
            "HAS_OCCUPATION",
            "Occupation",
        ),
        (
            re.compile(r"(?:我的)?工作(?:是|为)?\s*([^，。！？,!?]{1,40})"),
            "HAS_OCCUPATION",
            "Occupation",
        ),
        (re.compile(r"我喜欢\s*([^，。！？,!?]{1,60})"), "LIKES", "Preference"),
        (re.compile(r"我不喜欢\s*([^，。！？,!?]{1,60})"), "DISLIKES", "Preference"),
        (re.compile(r"我的目标(?:是|为)?\s*([^。！？!?]{1,100})"), "HAS_GOAL", "Goal"),
        (re.compile(r"请记住\s*([^。！？!?]{1,120})"), "WANTS_REMEMBERED", "Fact"),
    ]
    facts: list[Fact] = []
    occupied: list[tuple[int, int]] = []
    # More specific negative preference must win over the generic positive pattern.
    patterns[4], patterns[5] = patterns[5], patterns[4]
    for pattern, relation, target_type in patterns:
        for match in pattern.finditer(text):
            span = match.span()
            if any(start <= span[0] < end for start, end in occupied):
                continue
            target = match.group(1).strip(" ，。.!！")
            if not target:
                continue
            occupied.append(span)
            facts.append(
                Fact(
                    source_type="Person",
                    source_name="用户",
                    relation=relation,
                    target_type=target_type,
                    target_name=target,
                    evidence=text[:1000],
                )
            )
    return facts
