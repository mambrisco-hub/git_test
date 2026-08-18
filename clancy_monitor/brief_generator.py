"""Generates a daily legal brief for the Lindsay Clancy case using Claude."""

import os
import json
from datetime import date
from typing import List

import anthropic

from scrapers import Article
from case_config import CASE_NAME, DOCKET_BASE

CLAUDE_MODEL = "claude-opus-5"

SYSTEM_PROMPT = f"""You are producing a daily briefing document on the Lindsay Clancy case
for an engaged private couple who have been closely following the proceedings.
They want two things equally: (1) a clear-eyed account of what actually happened in
court and in verified news today, and (2) a frank, organized summary of what the
internet sleuth community is currently theorizing, debating, and postulating —
including Reddit, social media, and true crime forums.

Write in a structured but readable style — not stuffy legal Latin, but organized and
precise. Use plain English. Call things what they are.

Structure the brief EXACTLY as follows:

═══════════════════════════════════════════════════
COMMONWEALTH v. LINDSAY CLANCY
Plymouth Superior Court | Daily Case Brief — [DATE]
Docket No. [DOCKET]
═══════════════════════════════════════════════════

AT A GLANCE — 3–5 bullet points summarizing the single most important things from today

─────────────────────────────────────────────────
I. TODAY IN THE CASE — VERIFIED FACTS
─────────────────────────────────────────────────
Numbered paragraphs (¶1, ¶2 …) of confirmed, sourced developments from news coverage.
Cite source in parentheses after each claim, e.g. (Boston Globe, 8/16/26).
Mark anything from a single unconfirmed source as [UNCONFIRMED].

─────────────────────────────────────────────────
II. MEDIA COVERAGE SNAPSHOT
─────────────────────────────────────────────────
How is the press framing today's events? Note tone, any shifts in narrative,
which outlets are sympathetic to defense vs. prosecution framing. Note viral posts.
Include notable social media reactions with engagement numbers where available.

─────────────────────────────────────────────────
III. WHAT THE SLEUTHS ARE SAYING
─────────────────────────────────────────────────
This is the heart of the document for these readers. Organize the internet sleuth
community's theories and discussions into named sub-topics, e.g.:

  The McLean Hospital Negligence Theory — What people are arguing, with the
  strongest points for and against.

  The Medication Theory — etc.

  Hot Reddit Threads — Summarize the top discussions with their vote counts and
  the core argument being made.

For each theory or claim:
  - State it plainly and fairly
  - Note how widely it's held (fringe / growing / mainstream sleuth consensus)
  - Note if it aligns with or contradicts established facts
  - Mark speculation clearly as [SLEUTH THEORY] and unverified claims as [UNVERIFIED]

─────────────────────────────────────────────────
IV. FACT-CHECK: VIRAL CLAIMS
─────────────────────────────────────────────────
Pick the top 3–5 claims circulating on social media today and assess each one:
TRUE / FALSE / UNVERIFIABLE / PARTIALLY TRUE, with a one-sentence explanation.

─────────────────────────────────────────────────
V. BACKGROUND CONTEXT
─────────────────────────────────────────────────
Brief standing summary of the case for reference (update only if new facts emerged).

─────────────────────────────────────────────────
APPENDIX — SOURCE INDEX
─────────────────────────────────────────────────

Tone: Clear, direct, engaged — like a smart friend who's been following the case
obsessively and is briefing you over coffee. Organized, not academic. Thorough, not dry.
"""

CLUSTER_SYSTEM = """You are a legal research assistant. Given a list of article titles,
identify the distinct factual sub-topics within them. Output a JSON array of objects
with keys "topic" (short label, ≤8 words) and "article_indices" (list of ints). Output
only valid JSON — no prose, no markdown fences."""


def _cluster_articles(client: anthropic.Anthropic, articles: List[Article]) -> List[dict]:
    index_lines = [
        f"{i}: [{a.platform.upper()}] {a.title} — {a.source}"
        for i, a in enumerate(articles)
    ]
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=CLUSTER_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                "Group these articles about the Lindsay Clancy case into sub-topics:\n\n"
                + "\n".join(index_lines[:200])
                + "\n\nIdentify up to 8 distinct sub-topics."
            ),
        }],
    )
    raw = next(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [{"topic": "General Case Coverage", "article_indices": list(range(len(articles)))}]


def _format_cluster(cluster: dict, articles: List[Article]) -> str:
    lines = [f"\n── TOPIC: {cluster['topic']} ──"]
    for idx in cluster.get("article_indices", [])[:20]:
        if idx >= len(articles):
            continue
        a = articles[idx]
        eng = ", ".join(f"{k}={v:,}" for k, v in a.engagement.items() if v)
        pub = a.published.strftime("%Y-%m-%d %H:%M UTC") if a.published else "Unknown"
        lines.append(
            f"\n[{a.platform.upper()}] {a.source}\n"
            f"Title: {a.title}\n"
            f"Content: {a.content[:800]}\n"
            f"URL: {a.url}\n"
            f"Engagement: {eng or 'N/A'} | Published: {pub}"
        )
    return "\n".join(lines)


def _source_index(articles: List[Article]) -> str:
    col_w = [4, 12, 28, 22, 60]
    header = (
        f"{'#':<{col_w[0]}} {'Platform':<{col_w[1]}} {'Source':<{col_w[2]}} "
        f"{'Published':<{col_w[3]}} {'URL'}"
    )
    sep = "─" * 130
    rows = ["\nAPPENDIX A — SOURCE INDEX\n", header, sep]
    for i, a in enumerate(articles):
        pub = a.published.strftime("%Y-%m-%d %H:%M UTC") if a.published else "Unknown"
        row = (
            f"{i:<{col_w[0]}} {a.platform:<{col_w[1]}} {a.source[:26]:<{col_w[2]}} "
            f"{pub:<{col_w[3]}} {a.url[:58]}"
        )
        rows.append(row)
    return "\n".join(rows)


def generate_brief(articles: List[Article]) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)
    today = date.today()
    docket = f"{DOCKET_BASE}-MEDIA-{today.strftime('%Y%m%d')}"

    print(f"[brief_generator] Clustering {len(articles)} items…")
    clusters = _cluster_articles(client, articles)
    print(f"[brief_generator] {len(clusters)} sub-topics identified.")

    cluster_text = "\n\n".join(_format_cluster(c, articles) for c in clusters)

    user_prompt = (
        f"Today's date: {today.strftime('%B %d, %Y')}\n"
        f"Docket: {docket}\n\n"
        f"Below are today's media items about the Lindsay Clancy case, organized by topic.\n"
        f"Generate the complete legal brief.\n\n"
        f"{cluster_text}"
    )

    print("[brief_generator] Generating brief with Claude…")
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    brief = next(b.text for b in msg.content if b.type == "text")
    brief += "\n\n" + _source_index(articles)
    return brief
