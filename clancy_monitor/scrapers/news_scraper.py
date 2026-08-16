"""RSS scraper filtered to Lindsay Clancy case keywords."""

import re
import requests
import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List

from . import Article
from case_config import CASE_KEYWORDS, NEWS_FEEDS

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ClancyCaseBot/1.0)"
}

_KEYWORD_RE = re.compile(
    "|".join(re.escape(kw) for kw in CASE_KEYWORDS),
    flags=re.IGNORECASE,
)


def _is_relevant(text: str) -> bool:
    return bool(_KEYWORD_RE.search(text))


def _parse_date(entry) -> datetime:
    for field in ("published", "updated"):
        val = entry.get(f"{field}_parsed") or entry.get(field)
        if val is None:
            continue
        if isinstance(val, str):
            try:
                return parsedate_to_datetime(val).astimezone(timezone.utc)
            except Exception:
                pass
        else:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _parse_content(entry) -> str:
    if entry.get("summary"):
        return entry.summary
    if entry.get("content"):
        return entry.content[0].value
    return ""


def scrape_news(max_per_feed: int = 50) -> List[Article]:
    articles: List[Article] = []

    for outlet, url in NEWS_FEEDS.items():
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                content = _parse_content(entry)

                # Only keep articles that mention the case
                if not _is_relevant(title + " " + content):
                    continue

                articles.append(
                    Article(
                        source=outlet,
                        platform="news",
                        title=title,
                        content=content,
                        url=entry.get("link", ""),
                        author=entry.get("author", ""),
                        published=_parse_date(entry),
                    )
                )
        except Exception as exc:
            print(f"[news_scraper] Failed to fetch {outlet}: {exc}")

    print(f"[news_scraper] Found {len(articles)} case-relevant articles across {len(NEWS_FEEDS)} outlets.")
    return articles
