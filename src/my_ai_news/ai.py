from __future__ import annotations

import json
import re
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


ASCII_STOPWORDS = {
    "a", "an", "the", "its", "their", "his", "her", "to", "for", "with", "and", "or", "of", "in", "on", "at",
    "by", "from", "into", "across", "after", "before", "new", "more", "most", "less", "just", "than", "that", "this",
    "these", "those", "it", "is", "are", "was", "were", "be", "been", "being", "as", "has", "have", "had", "will",
    "can", "could", "should", "would", "help", "helps", "helping", "build", "builds", "building", "launching",
    "launched", "says", "said", "grew", "grows", "rose", "reaches", "reached", "fueled", "powered", "too",
}


ASCII_WORD_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bthe next evolution of\b", "下一阶段演进"),
    (r"\bupdates?\b", "更新"),
    (r"\bupdated\b", "已更新"),
    (r"\bhelp(?:ing)?\b", "帮助"),
    (r"\bbuild(?:ing)?\b", "构建"),
    (r"\bsafer\b", "更安全"),
    (r"\bsecure\b", "安全"),
    (r"\bmore capable\b", "更强大"),
    (r"\bcapable\b", "强大"),
    (r"\benterprises?\b", "企业"),
    (r"\bdevelopers?\b", "开发者"),
    (r"\bagents?\b", "智能体"),
    (r"\bsdk\b", "SDK"),
    (r"\bmodel-native\b", "模型原生"),
    (r"\bnative sandbox execution\b", "原生沙箱执行"),
    (r"\bsandbox\b", "沙箱"),
    (r"\bharness\b", "框架"),
    (r"\blong-running\b", "长时间运行"),
    (r"\btools?\b", "工具"),
    (r"\bfiles?\b", "文件"),
    (r"\bmarketing\b", "营销"),
    (r"\bplatform\b", "平台"),
    (r"\bpowered by ai\b", "由 AI 驱动"),
    (r"\bfueled by\b", "受益于"),
    (r"\breaches?\b", "达到"),
    (r"\bnews\b", "动态"),
    (r"\blatest\b", "最新"),
    (r"\bopenai\b", "OpenAI"),
    (r"\btechcrunch\b", "TechCrunch"),
    (r"\bai\b", "AI"),
]


class AIEnricher:
    def enrich(self, *, category: str, source_name: str, title: str, summary: str, url: str) -> EnrichmentResult:
        raise NotImplementedError


def contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -—:：，,。.\t\n")


def replace_english_phrases(value: str) -> str:
    text = normalize_spaces(value)
    for pattern, replacement in ASCII_WORD_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\bto\b", "以", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwith\b", "结合", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfor\b", "面向", text, flags=re.IGNORECASE)
    text = re.sub(r"\bacross\b", "覆盖", text, flags=re.IGNORECASE)
    text = re.sub(r"\band\b", "与", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcontinues?\b", "持续", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgrow(?:ing)?\b", "增长", text, flags=re.IGNORECASE)
    text = re.sub(r"\bin just\b", "在", text, flags=re.IGNORECASE)
    text = re.sub(r"\bafter\b", "在…之后", text, flags=re.IGNORECASE)
    return normalize_spaces(text)


def extract_anchor_terms(value: str) -> list[str]:
    anchors = re.findall(r"\b(?:[A-Z]{2,}|[A-Z][a-zA-Z0-9.+-]{1,}|\$?\d+(?:\.\d+)?[A-Za-z%]*)\b", value)
    deduped: list[str] = []
    for anchor in anchors:
        if anchor.lower() in ASCII_STOPWORDS:
            continue
        if anchor not in deduped:
            deduped.append(anchor)
    return deduped[:6]


def normalize_anchor_terms(*, source_name: str, anchors: list[str]) -> list[str]:
    source_parts = {part.lower() for part in re.findall(r"[A-Za-z0-9.+-]+", source_name)}
    replacements = {
        "agents": "智能体",
        "agent": "智能体",
        "developers": "开发者",
        "developer": "开发者",
        "enterprise": "企业",
        "enterprises": "企业",
        "models": "模型",
        "model": "模型",
        "features": "功能",
        "feature": "功能",
        "funding": "融资",
        "revenue": "营收",
    }
    filtered: list[str] = []
    for anchor in anchors:
        lowered = anchor.lower().strip()
        if lowered in source_parts:
            continue
        if lowered in {"ai", "news", "latest", "new", "now", "the", "this", "that"}:
            continue
        anchor = replacements.get(lowered, anchor)
        if filtered and filtered[-1] == anchor:
            continue
        if anchor not in filtered:
            filtered.append(anchor)
    return filtered[:3]


def build_anchor_phrase(*, source_name: str, title: str, summary: str) -> str:
    anchors = normalize_anchor_terms(source_name=source_name, anchors=extract_anchor_terms(f"{title} {summary}"))
    if anchors:
        return "、".join(anchors[:2])
    return "关键信息"


def cleanup_mixed_text(value: str) -> str:
    text = replace_english_phrases(value)
    text = re.sub(r"[,:;]+", "，", text)
    parts = re.findall(r"[\u4e00-\u9fffA-Za-z0-9$%+.\-/]+", text)
    kept: list[str] = []
    for part in parts:
        lowered = part.lower()
        if re.fullmatch(r"[a-z]+", part) and lowered in ASCII_STOPWORDS:
            continue
        if re.fullmatch(r"[a-z]+", part):
            continue
        if kept and kept[-1] == part:
            continue
        kept.append(part)
    cleaned = " ".join(kept)
    cleaned = re.sub(r"\s+([，。；：])", r"\1", cleaned)
    cleaned = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，。；：")
    return cleaned


def classify_story_signal(*, title: str, summary: str, category: str) -> str:
    text = f"{title} {summary}".lower()
    if any(keyword in text for keyword in ["arr", "funding", "raises", "raised", "revenue", "$", "融资", "营收", "估值"]):
        return "business"
    if any(keyword in text for keyword in ["launch", "launched", "update", "updated", "sdk", "feature", "model", "release", "发布", "更新", "上线", "推出"]):
        return "product"
    if any(keyword in text for keyword in ["lawsuit", "risk", "ban", "probe", "controvers", "争议", "风险", "调查", "封禁"]):
        return "risk"
    if category == "时事热点":
        return "world"
    return "general"


def build_localized_title(*, source_name: str, category: str, title: str) -> str:
    clean_title = normalize_spaces(title)
    if contains_cjk(clean_title):
        return clean_title[:34]

    signal = classify_story_signal(title=title, summary=title, category=category)
    anchor_phrase = build_anchor_phrase(source_name=source_name, title=title, summary=title)
    if signal == "business":
        return f"{source_name}：{anchor_phrase}商业进展"[:34]
    if signal == "product":
        return f"{source_name}：{anchor_phrase}能力更新"[:34]
    if signal == "risk":
        return f"{source_name}：{anchor_phrase}风险动态"[:34]
    if signal == "world":
        return f"{source_name}：{anchor_phrase}事件进展"[:34]
    return f"{source_name}：{anchor_phrase}相关动态"[:34]


def build_localized_summary(*, source_name: str, category: str, title: str, summary: str) -> str:
    candidate = normalize_spaces(summary or title)
    if contains_cjk(candidate):
        return f"这条来自{source_name}的{category}消息主要提到：{candidate}"[:110]

    signal = classify_story_signal(title=title, summary=summary, category=category)
    anchor_phrase = build_anchor_phrase(source_name=source_name, title=title, summary=summary)
    if signal == "business":
        return f"这条来自{source_name}的{category}消息，重点围绕{anchor_phrase}等商业进展展开，适合快速判断增长和落地情况。"[:110]
    if signal == "product":
        return f"这条来自{source_name}的{category}消息，重点围绕{anchor_phrase}等能力更新展开，适合先快速抓住版本重点。"[:110]
    if signal == "risk":
        return f"这条来自{source_name}的{category}消息，重点围绕{anchor_phrase}等风险变化展开，值得继续关注后续回应。"[:110]
    if signal == "world":
        return f"这条来自{source_name}的{category}消息，重点围绕{anchor_phrase}等事件进展展开，适合先快速了解局势变化。"[:110]
    return f"这条来自{source_name}的{category}消息，重点围绕{anchor_phrase}展开，我已先提炼出关键词方便快速浏览。"[:110]


def build_editorial_commentary(*, source_name: str, category: str, title: str, summary: str) -> str:
    signal = classify_story_signal(title=title, summary=summary, category=category)
    if signal == "business":
        return "我的判断：这条更偏商业进展，重点要看它后续能不能真正转化成增长和落地。"[:60]
    if signal == "product":
        return "我的判断：这更像是产品能力前推一步，真正值不值得高看还要看后续实际效果。"[:60]
    if signal == "risk":
        return "我的判断：这类消息要继续盯后续回应和影响范围，短期内不宜过早下结论。"[:60]
    if signal == "world":
        return "我的判断：这类事件的关键不只在当下进展，还要看后续是否持续发酵。"[:60]
    return f"我的判断：这条来自{source_name}的{category}更新值得先记下，后续如果还有展开，我会继续帮你补充。"[:60]


class NoopEnricher(AIEnricher):
    def enrich(self, *, category: str, source_name: str, title: str, summary: str, url: str) -> EnrichmentResult:
        localized_title = build_localized_title(source_name=source_name, category=category, title=title)
        localized_summary = build_localized_summary(
            source_name=source_name,
            category=category,
            title=title,
            summary=summary,
        )
        return EnrichmentResult(
            title=localized_title,
            summary=localized_summary or "暂无摘要",
            commentary=build_editorial_commentary(
                source_name=source_name,
                category=category,
                title=title,
                summary=summary,
            ),
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
