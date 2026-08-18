"""X (Twitter) scraper — searches for Lindsay Clancy case tweets via API v2.

Required env var: TWITTER_BEARER_TOKEN
Get one at: https://developer.twitter.com/en/portal/dashboard

Free/Basic tier: ~500k tweet reads/month, recent-search endpoint (7-day window).
"""

import os
import httpx
from datetime import datetime, timezone
from typing import List

from . import Article
from case_config import TWITTER_QUERIES

API_BASE = "https://api.twitter.com/2"
TWEET_FIELDS = "created_at,author_id,public_metrics,entities,lang"
EXPANSIONS = "author_id"
USER_FIELDS = "name,username,verified"


def _get_headers() -> dict:
    token = os.getenv("TWITTER_BEARER_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "TWITTER_BEARER_TOKEN not set. "
            "Obtain at https://developer.twitter.com/en/portal/dashboard"
        )
    return {"Authorization": f"Bearer {token}"}


def _parse_tweet(tweet: dict, users_by_id: dict) -> Article:
    metrics = tweet.get("public_metrics", {})
    author = users_by_id.get(tweet.get("author_id", ""), {})
    username = author.get("username", "unknown")

    published = None
    ts = tweet.get("created_at")
    if ts:
        published = datetime.fromisoformat(ts.replace("Z", "+00:00"))

    text = tweet.get("text", "")
    return Article(
        source="X (Twitter)",
        platform="twitter",
        title=text[:120] + ("…" if len(text) > 120 else ""),
        content=text,
        url=f"https://x.com/{username}/status/{tweet['id']}",
        author=author.get("name", username),
        published=published,
        engagement={
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "impressions": metrics.get("impression_count", 0),
        },
    )


def scrape_twitter(max_per_query: int = 50) -> List[Article]:
    try:
        headers = _get_headers()
    except EnvironmentError as e:
        print(f"[twitter_scraper] Skipping: {e}")
        return []

    articles: List[Article] = []
    seen_ids: set = set()

    with httpx.Client(headers=headers, timeout=20) as client:
        for query in TWITTER_QUERIES:
            try:
                resp = client.get(
                    f"{API_BASE}/tweets/search/recent",
                    params={
                        "query": query,
                        "max_results": min(max_per_query, 100),
                        "tweet.fields": TWEET_FIELDS,
                        "expansions": EXPANSIONS,
                        "user.fields": USER_FIELDS,
                        "sort_order": "recency",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                users_by_id = {
                    u["id"]: u
                    for u in data.get("includes", {}).get("users", [])
                }
                for tweet in data.get("data", []):
                    tid = tweet.get("id")
                    if tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    articles.append(_parse_tweet(tweet, users_by_id))

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    print("[twitter_scraper] Rate limited — stopping.")
                    break
                print(f"[twitter_scraper] HTTP error for query '{query}': {exc}")
            except Exception as exc:
                print(f"[twitter_scraper] Error for query '{query}': {exc}")

    print(f"[twitter_scraper] Collected {len(articles)} case-relevant tweets.")
    return articles
