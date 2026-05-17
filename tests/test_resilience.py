from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from my_ai_news.ai import AIEnricher, EnrichmentResult, NoopEnricher
from my_ai_news.cli import format_run_summary
from my_ai_news.config import load_sources
from my_ai_news.fetchers import fetch_source
from my_ai_news.models import RawItem
from my_ai_news.pipeline import run_pipeline
from my_ai_news.processing import to_story
from my_ai_news.publish import publish
from my_ai_news.x_digest import build_account_feed_urls, run_x_digest


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


def test_publish_skips_invalid_story_dates_and_cleans_bad_daily_files(tmp_path: Path, sample_item: RawItem) -> None:
    publish_dir = tmp_path / "public" / "data"
    daily_dir = publish_dir / "daily"
    daily_dir.mkdir(parents=True)
    bad_daily_path = daily_dir / "Fri, 13 Ma.json"
    bad_daily_path.write_text("{}", encoding="utf-8")

    valid_story = to_story(sample_item, 90, NoopEnricher())
    invalid_item = RawItem(**sample_item.to_dict())
    invalid_item.published_date = "Fri, 13 Ma"
    invalid_story = to_story(invalid_item, 90, NoopEnricher())

    publish([valid_story, invalid_story], publish_dir)

    latest_payload = json.loads((publish_dir / "latest.json").read_text(encoding="utf-8"))
    assert list(latest_payload) == ["2026-04-15"]
    assert (daily_dir / "2026-04-15.json").exists()
    assert not bad_daily_path.exists()
    assert not (daily_dir / "Fri, 13 Ma.json").exists()


def test_fetch_source_supports_html_article_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <article class="article-item__container">
      <a href="/articles/2026-05-15-14"><img alt="备用标题" src="https://cdn.example/image.jpg"></a>
      <a class="article-item__title t-strong" href="/articles/2026-05-15-14">机器之心 HTML 源恢复</a>
      <p class="u-text-limit--two article-item__summary">服务端页面列表可作为 RSS 备用。</p>
    </article>
    """

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return html.encode("utf-8")

    monkeypatch.setattr("my_ai_news.fetchers.urlopen", lambda request, timeout: FakeResponse())

    result = fetch_source(
        {
            "id": "jiqizhixin",
            "name": "机器之心",
            "category": "ai",
            "type": "html",
            "url": "https://www.jiqizhixin.com/industry",
        }
    )

    assert result.status == "success"
    assert len(result.items) == 1
    [item] = result.items
    assert item.title == "机器之心 HTML 源恢复"
    assert item.summary == "服务端页面列表可作为 RSS 备用。"
    assert item.url == "https://www.jiqizhixin.com/articles/2026-05-15-14"
    assert item.published_date == "2026-05-15"


def test_x_digest_fetches_posts_from_configured_rss(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = SimpleNamespace(
        title="",
        summary='<p>AI agents are becoming useful in real workflows.</p><img src="https://pbs.twimg.com/media/demo.jpg?format=jpg&amp;name=orig"><video src="https://video.twimg.com/demo.mp4"></video>',
        link="https://x.com/example/status/1",
        published="Fri, 15 May 2026 08:00:00 GMT",
        published_parsed=None,
        links=[{"href": "https://video.twimg.com/enclosure.mp4", "type": "video/mp4"}],
    )
    feed = SimpleNamespace(
        feed={"image": {"href": "https://pbs.twimg.com/profile_images/example.jpg"}},
        entries=[entry],
    )
    monkeypatch.setattr("my_ai_news.x_digest.feedparser.parse", lambda url: feed)

    config = SimpleNamespace(
        llm_enabled=False,
        llm_api_key=None,
        llm_model="test-model",
        llm_base_url=None,
        x_config=tmp_path / "x_accounts.json",
        x_digest_path=tmp_path / "x-digest.json",
    )
    config.x_config.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "id": "example",
                        "handle": "example",
                        "name": "Example",
                        "role": "AI builder",
                        "rss_url": "https://rss.example/user/example",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_x_digest(config)

    assert payload["total"] == 1
    [item] = payload["items"]
    assert item["author_name"] == "Example"
    assert item["original_text"] == "AI agents are becoming useful in real workflows."
    assert item["avatar_url"] == "https://pbs.twimg.com/profile_images/example.jpg"
    assert item["media_urls"] == ["https://pbs.twimg.com/media/demo.jpg?format=jpg&name=orig"]
    assert item["image_urls"] == ["https://pbs.twimg.com/media/demo.jpg?format=jpg&name=orig"]
    assert item["video_urls"] == ["https://video.twimg.com/demo.mp4", "https://video.twimg.com/enclosure.mp4"]
    assert item["media_note"] == ""
    assert item["zh_text"] == ""
    assert item["url"] == "https://x.com/example/status/1"
    assert item["published_date"] == "2026-05-15"
    assert json.loads(config.x_digest_path.read_text(encoding="utf-8"))["total"] == 1


def test_x_digest_reports_unconfigured_accounts(tmp_path: Path) -> None:
    config = SimpleNamespace(
        llm_enabled=False,
        llm_api_key=None,
        llm_model="test-model",
        llm_base_url=None,
        x_config=tmp_path / "x_accounts.json",
        x_digest_path=tmp_path / "x-digest.json",
    )
    config.x_config.write_text(
        json.dumps({"accounts": [{"id": "example", "handle": "example", "name": "Example"}]}),
        encoding="utf-8",
    )

    payload = run_x_digest(config)

    assert payload["total"] == 0
    assert payload["accounts"][0]["status"] == "not_configured"
    assert config.x_digest_path.exists()


def test_x_digest_builds_rsshub_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_RSS_BASE_URL", "https://rss.example.com/")

    urls = build_account_feed_urls({"handle": "sama"})

    assert urls == ["https://rss.example.com/twitter/user/sama"]


def test_x_digest_flags_likely_unavailable_native_media(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = SimpleNamespace(
        title="Grok Imagine",
        summary="Grok Imagine",
        link="https://x.com/elonmusk/status/1",
        published="Fri, 15 May 2026 08:00:00 GMT",
        published_parsed=None,
    )
    monkeypatch.setattr("my_ai_news.x_digest.feedparser.parse", lambda url: SimpleNamespace(feed={}, entries=[entry]))

    config = SimpleNamespace(
        llm_enabled=False,
        llm_api_key=None,
        llm_model="test-model",
        llm_base_url=None,
        x_config=tmp_path / "x_accounts.json",
        x_digest_path=tmp_path / "x-digest.json",
    )
    config.x_config.write_text(
        json.dumps({"accounts": [{"id": "elonmusk", "handle": "elonmusk", "name": "Elon Musk", "rss_url": "https://rss.example/elonmusk"}]}),
        encoding="utf-8",
    )

    payload = run_x_digest(config)

    assert payload["items"][0]["media_note"].startswith("该动态可能包含 X 原生媒体")


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
