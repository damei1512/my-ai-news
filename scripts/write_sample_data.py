#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


SAMPLE_ARCHIVE = {
    "2026-03-17": {
        "week": "周二",
        "articles": [
            {
                "category": "人工智能",
                "tag": "OpenAI",
                "title": "示例：AI 管线重建进入可迁移阶段",
                "link": "https://example.com/ai-rebuild",
                "summary": "新的数据管线已经拆分为采集、处理、发布三层，旧前端也能继续读取兼容输出。",
                "comment": "先把链路跑稳，再谈花活，这是对的。",
                "image": "",
                "score": 96
            },
            {
                "category": "数码科技",
                "tag": "36Kr",
                "title": "示例：个人信息站开始采用结构化信源配置",
                "link": "https://example.com/source-config",
                "summary": "信源从脚本硬编码迁移到配置文件，后续新增和下线来源会更可控。",
                "comment": "以后不需要再在一个大脚本里翻箱倒柜。",
                "image": "",
                "score": 88
            }
        ]
    }
}

SAMPLE_STATUS = {
    "run_id": 1,
    "status": "success",
    "finished_at": "2026-03-17T08:00:00Z",
    "sources": 6,
    "raw_items": 18,
    "stories": 12,
    "publish_dir": "public/data",
    "status_path": "public/data/status.json",
    "source_statuses": [
        {"source_id": "openai_blog", "source_name": "OpenAI", "status": "success", "items_fetched": 3, "error_message": None},
        {"source_id": "jiqizhixin", "source_name": "机器之心", "status": "success", "items_fetched": 4, "error_message": None},
        {"source_id": "36kr", "source_name": "36Kr", "status": "success", "items_fetched": 4, "error_message": None},
        {"source_id": "ifanr", "source_name": "爱范儿", "status": "success", "items_fetched": 3, "error_message": None},
        {"source_id": "gcores", "source_name": "机核", "status": "success", "items_fetched": 2, "error_message": None},
        {"source_id": "bbc_world", "source_name": "BBC World", "status": "success", "items_fetched": 2, "error_message": None}
    ]
}


def main() -> int:
    publish_dir = PROJECT_ROOT / "public" / "data"
    daily_dir = publish_dir / "daily"
    publish_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)

    with (publish_dir / "latest.json").open("w", encoding="utf-8") as handle:
        json.dump(SAMPLE_ARCHIVE, handle, ensure_ascii=False, indent=2)

    with (daily_dir / "2026-03-17.json").open("w", encoding="utf-8") as handle:
        json.dump({"2026-03-17": SAMPLE_ARCHIVE["2026-03-17"]}, handle, ensure_ascii=False, indent=2)

    with (publish_dir / "status.json").open("w", encoding="utf-8") as handle:
        json.dump(SAMPLE_STATUS, handle, ensure_ascii=False, indent=2)

    print("sample data written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
