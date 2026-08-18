from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    source: str
    platform: str   # 'news' | 'twitter' | 'tiktok' | 'facebook' | 'instagram'
    title: str
    content: str
    url: str
    author: str = ""
    published: Optional[datetime] = None
    engagement: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "platform": self.platform,
            "title": self.title,
            "content": self.content[:3000],
            "url": self.url,
            "author": self.author,
            "published": self.published.isoformat() if self.published else None,
            "engagement": self.engagement,
        }
