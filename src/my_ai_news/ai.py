from __future__ import annotations

import json
from dataclasses import dataclass

from openai import OpenAI

from .config import AppConfig


@dataclass(frozen=True)
class EnrichmentResult:
    title: str
    summary: str
    commentary: str
    tags: list[str]
    score_delta: int = 0


class AIEnricher:
    def enrich(self, *, category: str, source_name: str, title: str, summary: str, url: str) -> EnrichmentResult:
        raise NotImplementedError


class NoopEnricher(AIEnricher):
    def enrich(self, *, category: str, source_name: str, title: str, summary: str, url: str) -> EnrichmentResult:
        return EnrichmentResult(
            title=title,
            summary=summary or "暂无摘要",
            commentary=f"{source_name} 最新更新，当前为基础模式。",
            tags=[source_name],
            score_delta=0,
        )


class OpenAICompatibleEnricher(AIEnricher):
    def __init__(self, config: AppConfig):
        client_kwargs = {"api_key": config.llm_api_key}
        if config.llm_base_url:
            client_kwargs["base_url"] = config.llm_base_url
        self.client = OpenAI(**client_kwargs)
        self.model = config.llm_model

    def enrich(self, *, category: str, source_name: str, title: str, summary: str, url: str) -> EnrichmentResult:
        prompt = f"""
你是一个中文科技与资讯编辑。请把输入内容整理为严格 JSON。

要求：
1. title: 中文标题，保持信息准确，30字内。
2. summary: 中文摘要，80字内，不能空话。
3. commentary: 一句有判断的短评，30字内。
4. tags: 1到3个中文短标签。
5. score_delta: 0到10的整数，表示该内容相对普通内容的重要度增量。
6. 输出必须是 JSON object，不要 Markdown。

输入：
category={category}
source={source_name}
title={title}
summary={summary}
url={url}
""".strip()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是稳定、克制、准确的中文资讯编辑。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content or "{}"
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        payload = json.loads(content.strip())
        tags = [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()]

        return EnrichmentResult(
            title=str(payload.get("title", title)).strip() or title,
            summary=str(payload.get("summary", summary)).strip() or summary or "暂无摘要",
            commentary=str(payload.get("commentary", f"{source_name} 最新更新。")).strip() or f"{source_name} 最新更新。",
            tags=tags[:3] or [source_name],
            score_delta=max(0, min(int(payload.get("score_delta", 0)), 10)),
        )


def build_enricher(config: AppConfig) -> AIEnricher:
    if not config.llm_enabled or not config.llm_api_key:
        return NoopEnricher()
    return OpenAICompatibleEnricher(config)
