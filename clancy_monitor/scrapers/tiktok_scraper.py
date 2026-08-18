"""TikTok scraper — searches for Lindsay Clancy case content.

Two modes (tried in order):
  1. Research API  — requires TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET
     Access: https://developers.tiktok.com/products/research-api/
  2. Public web fallback — parses trending/discover (no auth, may break).
"""

import os
import httpx
import re
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional

from . import Article
from case_config import CASE_KEYWORDS, TIKTOK_KEYWORDS

RESEARCH_API_BASE = "https://open.tiktokapis.com/v2"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

_KEYWORD_RE = re.compile(
    "|".join(re.escape(kw) for kw in CASE_KEYWORDS + TIKTOK_KEYWORDS),
    flags=re.IGNORECASE,
)


def _get_research_token() -> Optional[str]:
    key = os.getenv("TIKTOK_CLIENT_KEY", "")
    secret = os.getenv("TIKTOK_CLIENT_SECRET", "")
    if not (key and secret):
        return None
    try:
        resp = httpx.post(
            TOKEN_URL,
            data={
                "client_key": key,
                "client_secret": secret,
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        print(f"[tiktok_scraper] Could not obtain Research API token: {exc}")
        return None


def _scrape_via_research_api(token: str, max_results: int) -> List[Article]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    articles: List[Article] = []
    today = date.today()
    start = today - timedelta(days=7)  # 7-day window for case coverage

    for keyword in TIKTOK_KEYWORDS:
        payload = {
            "query": {
                "and": [
                    {"operation": "IN", "field_name": "keyword", "field_values": [keyword]}
                ]
            },
            "start_date": start.strftime("%Y%m%d"),
            "end_date": today.strftime("%Y%m%d"),
            "max_count": min(max_results, 100),
            "fields": (
                "id,video_description,create_time,share_url,"
                "like_count,comment_count,share_count,view_count,author_name"
            ),
        }
        try:
            resp = httpx.post(
                f"{RESEARCH_API_BASE}/research/video/query/",
                headers=headers,
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            for video in resp.json().get("data", {}).get("videos", []):
                desc = video.get("video_description", "")
                if not _KEYWORD_RE.search(desc):
                    continue
                published = None
                ts = video.get("create_time")
                if ts:
                    published = datetime.fromtimestamp(ts, tz=timezone.utc)
                articles.append(
                    Article(
                        source="TikTok",
                        platform="tiktok",
                        title=desc[:120] + ("…" if len(desc) > 120 else ""),
                        content=desc,
                        url=video.get("share_url", f"https://www.tiktok.com/video/{video.get('id')}"),
                        author=video.get("author_name", "Unknown"),
                        published=published,
                        engagement={
                            "likes": video.get("like_count", 0),
                            "comments": video.get("comment_count", 0),
                            "shares": video.get("share_count", 0),
                            "views": video.get("view_count", 0),
                        },
                    )
                )
        except Exception as exc:
            print(f"[tiktok_scraper] Research API error for keyword '{keyword}': {exc}")

    return articles


TIKTOK_WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.tiktok.com/",
}


def _scrape_via_public_web(max_results: int) -> List[Article]:
    """Try TikTok's public explore/search endpoint for case keywords."""
    articles: List[Article] = []

    with httpx.Client(headers=TIKTOK_WEB_HEADERS, timeout=20, follow_redirects=True) as client:
        for keyword in TIKTOK_KEYWORDS[:3]:  # Limit to avoid blocks
            try:
                resp = client.get(
                    "https://www.tiktok.com/api/search/item/full/",
                    params={
                        "keyword": keyword,
                        "count": str(min(max_results, 20)),
                        "type": "1",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("item_list", []):
                    desc = item.get("desc", "")
                    if not _KEYWORD_RE.search(desc):
                        continue
                    author = item.get("author", {})
                    stats = item.get("stats", {})
                    vid_id = item.get("id", "")
                    author_id = author.get("uniqueId", "unknown")

                    published = None
                    ts = item.get("createTime")
                    if ts:
                        published = datetime.fromtimestamp(int(ts), tz=timezone.utc)

                    articles.append(
                        Article(
                            source="TikTok",
                            platform="tiktok",
                            title=desc[:120] + ("…" if len(desc) > 120 else ""),
                            content=desc,
                            url=f"https://www.tiktok.com/@{author_id}/video/{vid_id}",
                            author=author.get("nickname", author_id),
                            published=published,
                            engagement={
                                "likes": stats.get("diggCount", 0),
                                "comments": stats.get("commentCount", 0),
                                "shares": stats.get("shareCount", 0),
                                "views": stats.get("playCount", 0),
                            },
                        )
                    )
            except Exception as exc:
                print(f"[tiktok_scraper] Public web search failed for '{keyword}': {exc}")

    return articles


def scrape_tiktok(max_results: int = 30) -> List[Article]:
    token = _get_research_token()
    if token:
        print("[tiktok_scraper] Using Research API.")
        articles = _scrape_via_research_api(token, max_results)
    else:
        print("[tiktok_scraper] No API credentials — trying public web fallback.")
        articles = _scrape_via_public_web(max_results)

    print(f"[tiktok_scraper] Collected {len(articles)} case-relevant TikTok items.")
    return articles
