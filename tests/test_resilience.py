from __future__ import annotations

import json
from pathlib import Path

import pytest

from my_ai_news.ai import AIEnricher, EnrichmentResult, NoopEnricher
from my_ai_news.cli import format_run_summary
from my_ai_news.config import load_sources
from my_ai_news.models import RawItem
from my_ai_news.pipeline import run_pipeline
from my_ai_news.processing import to_story


class FailingEnricher(AIEnricher):
    def enrich(self, *, category: str, source_name: str, title: str, summary: str, url: str) -> EnrichmentResult:
        raise TimeoutError("LLM timed out")


@pytest.fixture
def sample_item() -> RawItem:
    return RawItem(
        source_id="primary-source",
        source_name="Primary Source",
        category="ai",
        title="Test title",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        summary="<p>Story summary</p>",
        image_url="",
        published_at="2026-04-15T00:00:00Z",
        published_date="2026-04-15",
        fetched_at="2026-04-15T00:00:00Z",
        fingerprint="abc123",
        payload_json="{}",
    )


def test_load_sources_preserves_primary_and_backup_urls(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "category": "ai",
                        "type": "rss",
                        "url": "https://primary.example/rss",
                        "backup_urls": ["https://backup.example/rss"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    [source] = load_sources(config_path)

    assert source["url"] == "https://primary.example/rss"
    assert source["backup_urls"] == ["https://backup.example/rss"]
    assert source["urls"] == [
        "https://primary.example/rss",
        "https://backup.example/rss",
    ]


def test_noop_enricher_localizes_english_content_to_chinese(sample_item: RawItem) -> None:
    sample_item.source_name = "OpenAI"
    sample_item.title = "OpenAI updates its Agents SDK to help enterprises build safer, more capable agents"
    sample_item.summary = "OpenAI has expanded the capabilities of its agent-building toolkit, helping developers build safer long-running agents across files and tools."

    story = to_story(sample_item, 90, NoopEnricher())

    assert story.title != sample_item.title
    assert any("\u4e00" <= char <= "\u9fff" for char in story.title)
    assert "SDK" in story.title
    assert any("\u4e00" <= char <= "\u9fff" for char in story.summary)
    assert "智能体" in story.summary
    assert "我刚看到" not in story.summary
    assert story.summary.startswith("这条来自")
    assert "我的判断" in story.commentary


def test_noop_enricher_keeps_summary_neutral_for_chinese_content(sample_item: RawItem) -> None:
    sample_item.source_name = "爱范儿"
    sample_item.title = "OpenAI 推出新的智能体能力"
    sample_item.summary = "这次更新重点放在工具调用和长期任务执行。"

    story = to_story(sample_item, 90, NoopEnricher())

    assert story.title == "OpenAI 推出新的智能体能力"
    assert story.summary.startswith("这条来自")
    assert "这次更新重点放在工具调用和长期任务执行" in story.summary
    assert "我刚看到" not in story.summary
    assert story.commentary.startswith("我的判断：")


def test_noop_enricher_commentary_varies_by_business_signal(sample_item: RawItem) -> None:
    sample_item.source_name = "TechCrunch AI"
    sample_item.title = "Hightouch reaches $100M ARR fueled by marketing tools powered by AI"
    sample_item.summary = "The startup says it grew its ARR by $70 million in 20 months after launching an AI agent platform for marketers."

    story = to_story(sample_item, 90, NoopEnricher())

    assert "ARR" in story.title or "融资" in story.commentary or "商业" in story.commentary
    assert "商业" in story.commentary or "落地" in story.commentary


def test_run_pipeline_degrades_llm_and_writes_source_health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_item: RawItem) -> None:
    project_root = tmp_path
    (project_root / "config").mkdir()
    (project_root / "public" / "data").mkdir(parents=True)

    (project_root / ".env").write_text(
        "\n".join(
            [
                "LLM_ENABLED=true",
                "LLM_API_KEY=test-key",
                "LLM_BASE_URL=https://primary-llm.example/v1",
                "LLM_MODEL=test-model",
            ]
        ),
        encoding="utf-8",
    )
    (project_root / "config" / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "primary-source",
                        "name": "Primary Source",
                        "category": "ai",
                        "type": "rss",
                        "url": "https://primary.example/rss",
                        "backup_urls": ["https://backup.example/rss"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("my_ai_news.pipeline.build_enricher", lambda config: FailingEnricher())
    monkeypatch.setattr("my_ai_news.pipeline.fetch_source", lambda source: [sample_item])

    result = run_pipeline(project_root)

    assert result["status"] == "success"
    assert result["stories"] == 1
    assert result["llm"]["status"] == "degraded"
    assert result["llm"]["degraded_items"] == 1
    assert result["llm"]["base_urls"] == ["https://primary-llm.example/v1"]

    [source_status] = result["source_statuses"]
    assert source_status["status"] == "success"
    assert source_status["active_url"] == "https://primary.example/rss"
    assert source_status["backup_urls"] == ["https://backup.example/rss"]

    health_path = project_root / "public" / "data" / "source-health.json"
    health_payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert health_payload["run_id"] == result["run_id"]
    assert health_payload["summary"]["degraded_sources"] == 0
    assert health_payload["summary"]["healthy_sources"] == 1
    assert health_payload["sources"][0]["active_url"] == "https://primary.example/rss"


def test_format_run_summary_includes_llm_and_backup_context() -> None:
    summary = format_run_summary(
        {
            "run_id": 7,
            "status": "success",
            "sources": 2,
            "raw_items": 4,
            "stories": 3,
            "llm": {"status": "degraded", "degraded_items": 2},
            "source_statuses": [
                {"source_name": "Primary", "status": "fallback_success"},
                {"source_name": "Broken", "status": "timeout"},
            ],
            "status_path": "public/data/status.json",
            "source_health_path": "public/data/source-health.json",
        }
    )

    assert "llm_status: degraded" in summary
    assert "llm_degraded_items: 2" in summary
    assert "source_failed: Broken" in summary
    assert "source_degraded: Primary" in summary
    assert "source_health_path: public/data/source-health.json" in summary
