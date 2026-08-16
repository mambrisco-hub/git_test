# Clancy Case Monitor

Daily legal brief agent for tracking the **Commonwealth v. Lindsay Clancy** case
(Plymouth Superior Court, Docket No. PLY-CR-2023-00118).

Every day the agent scrapes news outlets, X (Twitter), TikTok, Facebook, and
Instagram for coverage matching case keywords, then uses Claude to produce a
structured legal brief formatted like a court filing.

## Tracked Keywords

| Category | Terms |
|---|---|
| People | Lindsay Clancy, Patrick Clancy, Cora Clancy, Dawson Clancy, Callan Clancy |
| Places | Duxbury (MA), McLean Hospital, Plymouth Superior Court, Bennington |
| Case terms | Clancy case, Clancy trial, Clancy postpartum, Clancy verdict, Clancy defense, Clancy sentencing |

## Project Structure

```
clancy_monitor/
├── agent.py              # Main entry point — runs all scrapers then generates brief
├── scheduler.py          # Daily cron-style scheduler
├── case_config.py        # All keywords, feed URLs, and search queries
├── brief_generator.py    # Claude-powered legal brief generator
├── requirements.txt
├── .env.example          # Copy to .env and fill in API credentials
├── scrapers/
│   ├── __init__.py       # Shared Article dataclass
│   ├── news_scraper.py   # 25 RSS feeds filtered to case keywords
│   ├── twitter_scraper.py# X API v2 — case-targeted search queries
│   ├── tiktok_scraper.py # TikTok Research API + public web fallback
│   └── meta_scraper.py   # Facebook Graph API + mbasic public fallback
│                           Instagram Graph API
└── output/               # Brief TXT files and raw JSON saved here
```

## Setup

```bash
cd clancy_monitor
pip install -r requirements.txt
cp .env.example .env
# Edit .env — ANTHROPIC_API_KEY is the only required credential
```

## Running

```bash
# Run once immediately (full scrape + brief generation)
python agent.py

# Scrape only — save raw JSON, skip Claude (useful for testing)
python agent.py --dry-run

# Regenerate brief from previously saved raw data (skips scraping)
python agent.py --load-raw output/raw_2026-08-16.json

# Run daily at 06:00 UTC (background scheduler)
python scheduler.py

# Run daily at 08:30 UTC, and run once immediately on start
python scheduler.py --time 08:30 --run-now
```

## API Credentials

| Platform | Env Var | Required? | Where to Get |
|---|---|---|---|
| Claude | `ANTHROPIC_API_KEY` | **Yes** | https://console.anthropic.com/ |
| X (Twitter) | `TWITTER_BEARER_TOKEN` | Optional | https://developer.twitter.com/en/portal/dashboard |
| Facebook/Instagram | `META_ACCESS_TOKEN` | Optional | https://developers.facebook.com/apps/ |
| TikTok | `TIKTOK_CLIENT_KEY` + `TIKTOK_CLIENT_SECRET` | Optional | https://developers.tiktok.com/products/research-api/ |

The agent gracefully skips any platform whose credentials are missing.
News (RSS) requires no credentials and always runs.

## Brief Format

Each brief follows appellate court filing conventions:

```
IN THE PLYMOUTH SUPERIOR COURT
COMMONWEALTH OF MASSACHUSETTS

COMMONWEALTH v. LINDSAY CLANCY
Docket No. PLY-CR-2023-00118-MEDIA-[DATE]

I.   Statement of Purpose & Scope
II.  Case Background Synopsis
III. Today's Verified Facts (¶¶ with source citations)
IV.  Issues Presented
V.   Analysis
VI.  Evidentiary Notes (source reliability)
VII. Conclusion & Recommendations
     Appendix A — Full source index
```

Claims from social media are labeled `[UNVERIFIED]`, claims contradicting the
record are labeled `[DISPUTED]`, and narratives posing jury pool risk are
flagged `[JURY POOL RISK]`.

## Production Deployment (cron)

```cron
# Run daily at 6 AM UTC, log to file
0 6 * * *  cd /path/to/clancy_monitor && python agent.py >> logs/agent.log 2>&1
```

## Output Files

| File | Description |
|---|---|
| `output/raw_YYYY-MM-DD.json` | All scraped articles for that day |
| `output/brief_YYYY-MM-DD.txt` | The generated legal brief |
| `logs/run_YYYYMMDD_HHMMSS.log` | Scheduler run log |
