"""Main orchestrator — scrapes all platforms, generates the daily legal brief."""

import os
import sys
import json
import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from scrapers.news_scraper import scrape_news
from scrapers.twitter_scraper import scrape_twitter
from scrapers.tiktok_scraper import scrape_tiktok
from scrapers.meta_scraper import scrape_facebook, scrape_instagram
from brief_generator import generate_brief


OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def collect_all() -> list:
    """Run all scrapers and return deduplicated articles."""
    print("\n=== Lindsay Clancy Case Monitor ===")
    print(f"Run time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    results = []
    results += scrape_news()
    results += scrape_twitter()
    results += scrape_tiktok()
    results += scrape_facebook()
    results += scrape_instagram()

    # Deduplicate by URL
    seen_urls: set = set()
    unique = []
    for a in results:
        key = a.url.strip().rstrip("/")
        if key and key not in seen_urls:
            seen_urls.add(key)
            unique.append(a)
        elif not key:
            unique.append(a)  # Keep URL-less items (e.g., some social posts)

    print(f"\n── Total unique items collected: {len(unique)} ──\n")
    return unique


def save_raw(articles: list, today: date) -> Path:
    raw_path = OUTPUT_DIR / f"raw_{today.isoformat()}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in articles], f, indent=2, default=str)
    print(f"[agent] Raw data saved → {raw_path}")
    return raw_path


def save_brief(brief_text: str, today: date) -> Path:
    brief_path = OUTPUT_DIR / f"brief_{today.isoformat()}.txt"
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(brief_text)
    print(f"[agent] Brief saved → {brief_path}")
    return brief_path


def run(dry_run: bool = False, load_raw: str | None = None) -> None:
    today = date.today()

    if load_raw:
        # Re-generate brief from a previously saved raw JSON (skip scraping)
        print(f"[agent] Loading raw data from {load_raw}")
        from scrapers import Article
        with open(load_raw, encoding="utf-8") as f:
            raw = json.load(f)
        articles = []
        for d in raw:
            pub = None
            if d.get("published"):
                try:
                    pub = datetime.fromisoformat(d["published"])
                except Exception:
                    pass
            articles.append(
                Article(
                    source=d["source"],
                    platform=d["platform"],
                    title=d["title"],
                    content=d["content"],
                    url=d["url"],
                    author=d.get("author", ""),
                    published=pub,
                    engagement=d.get("engagement", {}),
                )
            )
    else:
        articles = collect_all()
        save_raw(articles, today)

    if not articles:
        print("[agent] No case-relevant content found today. Exiting.")
        return

    if dry_run:
        print(f"[agent] Dry-run mode: {len(articles)} items collected, brief NOT generated.")
        print("Re-run without --dry-run to produce the brief.")
        return

    brief = generate_brief(articles)
    save_brief(brief, today)

    print("\n" + "=" * 70)
    print(brief[:3000] + ("\n\n[… brief continues in output file …]" if len(brief) > 3000 else ""))
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lindsay Clancy Case Monitor — daily legal brief generator"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and save raw data but do not call Claude to generate the brief.",
    )
    parser.add_argument(
        "--load-raw",
        metavar="FILE",
        help="Skip scraping; load a previously saved raw JSON and regenerate the brief.",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, load_raw=args.load_raw)


if __name__ == "__main__":
    main()
