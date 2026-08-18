"""Reddit scraper — no credentials required, uses the public JSON API.

Monitors true crime subreddits for Lindsay Clancy case discussions,
theories, and community analysis.
"""

import re
import httpx
from datetime import datetime, timezone
from typing import List

from . import Article
from case_config import CASE_KEYWORDS

SUBREDDITS = [
    "TrueCrime",
    "UnresolvedMysteries",
    "CriminalCases",
    "LindsayClancy",   # dedicated sub if it exists
    "massachusetts",
    "MorbidReality",
    "crimejunkies",
]

REDDIT_HEADERS = {
    "User-Agent": "ClancyCaseMonitor/1.0 (personal research tool)"
}

_KEYWORD_RE = re.compile(
    "|".join(re.escape(kw) for kw in CASE_KEYWORDS),
    flags=re.IGNORECASE,
)


def _fetch_subreddit_search(client: httpx.Client, subreddit: str, query: str, limit: int) -> list:
    try:
        resp = client.get(
            f"https://www.reddit.com/r/{subreddit}/search.json",
            params={"q": query, "restrict_sr": "1", "sort": "new", "limit": limit, "t": "week"},
        )
        if resp.status_code == 404:
            return []  # sub doesn't exist
        resp.raise_for_status()
        return resp.json().get("data", {}).get("children", [])
    except Exception as exc:
        print(f"[reddit_scraper] Search failed for r/{subreddit}: {exc}")
        return []


def _fetch_subreddit_new(client: httpx.Client, subreddit: str, limit: int) -> list:
    try:
        resp = client.get(
            f"https://www.reddit.com/r/{subreddit}/new.json",
            params={"limit": limit},
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("data", {}).get("children", [])
    except Exception as exc:
        print(f"[reddit_scraper] Fetch failed for r/{subreddit}: {exc}")
        return []


def _post_to_article(post_data: dict, subreddit: str) -> Article:
    title = post_data.get("title", "")
    selftext = post_data.get("selftext", "")
    score = post_data.get("score", 0)
    num_comments = post_data.get("num_comments", 0)
    permalink = post_data.get("permalink", "")
    author = post_data.get("author", "[deleted]")

    published = None
    ts = post_data.get("created_utc")
    if ts:
        published = datetime.fromtimestamp(ts, tz=timezone.utc)

    # Include post flair as context if present
    flair = post_data.get("link_flair_text", "")
    content = selftext
    if flair:
        content = f"[{flair}] {selftext}"

    return Article(
        source=f"Reddit/r/{subreddit}",
        platform="reddit",
        title=title,
        content=content[:3000],
        url=f"https://reddit.com{permalink}",
        author=f"u/{author}",
        published=published,
        engagement={
            "upvotes": score,
            "comments": num_comments,
            "upvote_ratio": int(post_data.get("upvote_ratio", 0) * 100),
        },
    )


def scrape_reddit(max_per_sub: int = 25) -> List[Article]:
    articles: List[Article] = []
    seen_urls: set = set()

    with httpx.Client(headers=REDDIT_HEADERS, timeout=20, follow_redirects=True) as client:
        for subreddit in SUBREDDITS:
            # Search for case keywords within the subreddit
            posts = _fetch_subreddit_search(client, subreddit, "Lindsay Clancy", max_per_sub)

            # For the dedicated sub, also grab /new directly
            if subreddit == "LindsayClancy":
                posts += _fetch_subreddit_new(client, subreddit, max_per_sub)

            for child in posts:
                post = child.get("data", {})
                title = post.get("title", "")
                body = post.get("selftext", "")
                permalink = post.get("permalink", "")

                if not _KEYWORD_RE.search(title + " " + body):
                    continue
                if permalink in seen_urls:
                    continue
                seen_urls.add(permalink)

                articles.append(_post_to_article(post, post.get("subreddit", subreddit)))

    print(f"[reddit_scraper] Collected {len(articles)} case-relevant Reddit posts.")
    return articles
