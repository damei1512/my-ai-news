from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class RawItem:
    source_id: str
    source_name: str
    category: str
    title: str
    url: str
    canonical_url: str
    summary: str
    image_url: str
    published_at: str
    fetched_at: str
    fingerprint: str
    payload_json: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Story:
    source_id: str
    source_name: str
    category: str
    tags: list[str]
    title: str
    url: str
    summary: str
    commentary: str
    image_url: str
    score: int
    published_at: str
    story_date: str

    def to_dict(self) -> dict:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
