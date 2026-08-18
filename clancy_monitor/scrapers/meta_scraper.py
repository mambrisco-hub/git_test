"""Facebook & Instagram scraper for Lindsay Clancy case coverage.

Two modes:
  1. Meta Graph API — requires META_ACCESS_TOKEN (long-lived page/user token)
     Get one at: https://developers.facebook.com/apps/
  2. mbasic.facebook.com public scrape — fallback, no auth required.

Env vars:
  META_ACCESS_TOKEN  — Graph API token
  META_PAGE_IDS      — comma-separated page IDs (default list provided)
  META_IG_USER_IDS   — comma-separated Instagram Business account IDs
"""

import os
import re
import httpx
from datetime import datetime, timezone
from typing import List
from bs4 import BeautifulSoup

from . import Article
from case_config import CASE_KEYWORDS, FACEBOOK_PAGES

GRAPH_API = "https://graph.facebook.com/v19.0"

_KEYWORD_RE = re.compile(
    "|".join(re.escape(kw) for kw in CASE_KEYWORDS),
    flags=re.IGNORECASE,
)


def _get_token() -> str:
    token = os.getenv("META_ACCESS_TOKEN", "")
    if not token:
        raise EnvironmentError("META_ACCESS_TOKEN not set.")
    return token


# ---------- Facebook Graph API --------------------------------------------

def _scrape_facebook_graph(token: str, page_ids: List[str], max_per_page: int) -> List[Article]:
    articles: List[Article] = []
    with httpx.Client(timeout=20) as client:
        for page_id in page_ids:
            try:
                resp = client.get(
                    f"{GRAPH_API}/{page_id}/posts",
                    params={
                        "access_token": token,
                        "fields": (
                            "message,story,created_time,permalink_url,"
                            "reactions.summary(true),shares,comments.summary(true)"
                        ),
                        "limit": max_per_page,
                    },
                )
                resp.raise_for_status()
                for post in resp.json().get("data", []):
                    text = post.get("message") or post.get("story") or ""
                    if not _KEYWORD_RE.search(text):
                        continue
                    published = None
                    ts = post.get("created_time")
                    if ts:
                        published = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    articles.append(
                        Article(
                            source=f"Facebook/{page_id}",
                            platform="facebook",
                            title=text[:120] + ("…" if len(text) > 120 else ""),
                            content=text,
                            url=post.get("permalink_url", ""),
                            author=page_id,
                            published=published,
                            engagement={
                                "reactions": post.get("reactions", {}).get("summary", {}).get("total_count", 0),
                                "shares": post.get("shares", {}).get("count", 0),
                                "comments": post.get("comments", {}).get("summary", {}).get("total_count", 0),
                            },
                        )
                    )
            except Exception as exc:
                print(f"[meta_scraper] Facebook Graph API error for {page_id}: {exc}")
    return articles


# ---------- mbasic public fallback ----------------------------------------

MBASIC_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClancyCaseBot/1.0)"}


def _scrape_facebook_public(page_ids: List[str], max_per_page: int) -> List[Article]:
    articles: List[Article] = []
    with httpx.Client(timeout=20, headers=MBASIC_HEADERS, follow_redirects=True) as client:
        for page_id in page_ids:
            try:
                resp = client.get(f"https://mbasic.facebook.com/{page_id}")
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                posts = soup.select("article") or soup.select("div[data-ft]")
                for post in posts[:max_per_page]:
                    text_el = post.find("p") or post.find("span")
                    text = text_el.get_text(" ", strip=True) if text_el else ""
                    if not text or not _KEYWORD_RE.search(text):
                        continue
                    link_el = post.find("a", href=True)
                    url = ""
                    if link_el:
                        href = link_el["href"]
                        url = (
                            f"https://www.facebook.com{href.split('?')[0]}"
                            if href.startswith("/")
                            else href
                        )
                    articles.append(
                        Article(
                            source=f"Facebook/{page_id}",
                            platform="facebook",
                            title=text[:120] + ("…" if len(text) > 120 else ""),
                            content=text,
                            url=url,
                            author=page_id,
                            published=datetime.now(timezone.utc),
                        )
                    )
            except Exception as exc:
                print(f"[meta_scraper] Public Facebook scrape failed for {page_id}: {exc}")
    return articles


# ---------- Instagram Graph API -------------------------------------------

def _scrape_instagram_graph(token: str, ig_ids: List[str], max_per_account: int) -> List[Article]:
    articles: List[Article] = []
    with httpx.Client(timeout=20) as client:
        for ig_id in ig_ids:
            try:
                resp = client.get(
                    f"{GRAPH_API}/{ig_id}/media",
                    params={
                        "access_token": token,
                        "fields": "caption,media_type,timestamp,permalink,like_count,comments_count,username",
                        "limit": max_per_account,
                    },
                )
                resp.raise_for_status()
                for media in resp.json().get("data", []):
                    caption = media.get("caption", "")
                    if not _KEYWORD_RE.search(caption):
                        continue
                    published = None
                    ts = media.get("timestamp")
                    if ts:
                        published = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    articles.append(
                        Article(
                            source=f"Instagram/{media.get('username', ig_id)}",
                            platform="instagram",
                            title=caption[:120] + ("…" if len(caption) > 120 else ""),
                            content=caption,
                            url=media.get("permalink", ""),
                            author=media.get("username", ig_id),
                            published=published,
                            engagement={
                                "likes": media.get("like_count", 0),
                                "comments": media.get("comments_count", 0),
                            },
                        )
                    )
            except Exception as exc:
                print(f"[meta_scraper] Instagram Graph API error for {ig_id}: {exc}")
    return articles


# ---------- Public entry points -------------------------------------------

def scrape_facebook(max_per_page: int = 20) -> List[Article]:
    page_ids_raw = os.getenv("META_PAGE_IDS", ",".join(FACEBOOK_PAGES))
    page_ids = [p.strip() for p in page_ids_raw.split(",") if p.strip()]

    try:
        token = _get_token()
        articles = _scrape_facebook_graph(token, page_ids, max_per_page)
        if articles:
            print(f"[meta_scraper] {len(articles)} Facebook posts via Graph API.")
            return articles
    except EnvironmentError as e:
        print(f"[meta_scraper] {e} — falling back to public scrape.")

    articles = _scrape_facebook_public(page_ids, max_per_page)
    print(f"[meta_scraper] {len(articles)} Facebook posts via public scrape.")
    return articles


def scrape_instagram(max_per_account: int = 20) -> List[Article]:
    ig_ids_raw = os.getenv("META_IG_USER_IDS", "")
    ig_ids = [i.strip() for i in ig_ids_raw.split(",") if i.strip()]
    if not ig_ids:
        print("[meta_scraper] META_IG_USER_IDS not set — skipping Instagram.")
        return []
    try:
        token = _get_token()
        articles = _scrape_instagram_graph(token, ig_ids, max_per_account)
        print(f"[meta_scraper] {len(articles)} Instagram posts.")
        return articles
    except EnvironmentError as e:
        print(f"[meta_scraper] Instagram skipped: {e}")
        return []
