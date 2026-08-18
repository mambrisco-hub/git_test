"""Central configuration for the Lindsay Clancy case monitoring agent."""

from datetime import date

CASE_NAME = "Commonwealth v. Lindsay Clancy"
DOCKET_BASE = "PLY-CR-2023-00118"  # Plymouth Superior Court

# All keywords/phrases to search across every platform.
# Items are matched case-insensitively; multi-word phrases must appear together.
CASE_KEYWORDS = [
    # People
    "Lindsay Clancy",
    "Patrick Clancy",
    "Cora Clancy",
    "Dawson Clancy",
    "Callan Clancy",
    # Places / institutions
    "Duxbury",
    "McLean Hospital",
    "Plymouth Superior Court",
    "Bennington",
    # Case descriptors (catch-all context)
    "Clancy case",
    "Clancy trial",
    "Clancy postpartum",
    "Clancy verdict",
    "Clancy defense",
    "Clancy prosecution",
    "Clancy sentencing",
]

# RSS feeds — broad news to filter locally (avoid missing small outlets)
NEWS_FEEDS = {
    "Reuters": "https://feeds.reuters.com/reuters/topNews",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "AP News": "https://feeds.apnews.com/rss/apf-topnews",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "The Guardian": "https://www.theguardian.com/us-news/rss",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "Washington Post": "https://feeds.washingtonpost.com/rss/national",
    "New York Times": "https://rss.nytimes.com/services/xml/rss/nf/HomePage.xml",
    "Boston Globe": "https://www.bostonglobe.com/rss/homepage",
    "Boston Herald": "https://www.bostonherald.com/feed/",
    "NBC News": "https://feeds.nbcnews.com/nbcnews/public/news",
    "CBS News": "https://www.cbsnews.com/latest/rss/main",
    "ABC News": "https://abcnews.go.com/abcnews/topstories",
    "WCVB Boston": "https://www.wcvb.com/rss",
    "WBZ Boston": "https://www.cbsnews.com/boston/latest/rss/main",
    "WBUR": "https://www.wbur.org/rss",
    "MassLive": "https://www.masslive.com/arc/outboundfeeds/rss/?outputType=xml",
    "Patriot Ledger": "https://www.patriotledger.com/rss",
    "The Pilot": "https://thepilot.news/feed/",
    "Law & Crime": "https://lawandcrime.com/feed/",
    "Crime Online": "https://www.crimeonline.com/feed/",
    "People": "https://people.com/feed/",
    "Daily Mail US": "https://www.dailymail.co.uk/news/us-news/index.rss",
    "Fox News": "https://moxie.foxnews.com/google-publisher/latest.xml",
    "Politico": "https://rss.politico.com/politics-news.xml",
}

# X/Twitter search queries — targeted to the case
TWITTER_QUERIES = [
    '"Lindsay Clancy" -is:retweet lang:en',
    '"Patrick Clancy" Duxbury -is:retweet lang:en',
    '"Clancy trial" OR "Clancy case" Massachusetts -is:retweet lang:en',
    '"McLean Hospital" Clancy -is:retweet lang:en',
    '"Plymouth Superior Court" Clancy -is:retweet lang:en',
    "Duxbury Clancy -is:retweet lang:en",
]

# Facebook pages to monitor (public pages, no token needed for mbasic fallback)
FACEBOOK_PAGES = [
    "lawandcrime",
    "crimeonline",
    "bostonglobe",
    "bostonherald",
    "wcvb5",
    "wbznews",
    "people",
]

# Instagram accounts covering crime/legal news
INSTAGRAM_ACCOUNTS_ENV_VAR = "META_IG_USER_IDS"
# Set META_IG_USER_IDS in .env to actual IG business account IDs

# TikTok hashtags/keywords to search
TIKTOK_KEYWORDS = [
    "LindsayClancy",
    "ClancyCase",
    "ClancyTrial",
    "DuxburyMassachusetts",
    "PostpartumPsychosis",
]
