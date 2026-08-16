"""Generates a daily legal brief for the Lindsay Clancy case using Claude."""

import os
import json
from datetime import date
from typing import List

import anthropic

from scrapers import Article
from case_config import CASE_NAME, DOCKET_BASE

CLAUDE_MODEL = "claude-opus-5"

SYSTEM_PROMPT = f"""You are a senior criminal defense and appellate attorney at a top Boston
law firm, assigned to monitor and brief the firm's partners on the case of
{CASE_NAME} (Plymouth Superior Court).

Your task is to synthesize the day's news coverage and social media activity into a
rigorous legal brief — the kind circulated among senior partners and submitted to the
court. The brief must be factually grounded, scrupulously objective, and written in
precise legal prose.

Structure the brief EXACTLY as follows:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IN THE PLYMOUTH SUPERIOR COURT
COMMONWEALTH OF MASSACHUSETTS

COMMONWEALTH v. LINDSAY CLANCY
Docket No. [DOCKET]  |  Daily Media Brief — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TABLE OF CONTENTS
I.   Statement of Purpose & Scope
II.  Case Background Synopsis
III. Today's Verified Facts (Numbered ¶¶)
IV.  Issues Presented
V.   Analysis
VI.  Evidentiary Notes (reliability of sources)
VII. Conclusion & Recommendations
VIII.Appendix A — Source Index

GUIDELINES:
- Cite every factual claim in parenthetical source notation, e.g., (Reuters, [timestamp]).
- Differentiate between established court record, reported facts, and social media assertions.
- Label unverified social media claims as [UNVERIFIED].
- Label claims contradicting established record as [DISPUTED — see ¶X].
- Flag viral narratives that could affect jury pool as [JURY POOL RISK].
- Use Latin legal terms appropriately (inter alia, id., supra, infra, cf., see also).
- Note significant shifts in public sentiment and media framing.
- Every section begins after a page break (use ─────────────── as a separator).
- Tone: formal, neutral, analytical. No editorial opinion.
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
    raw = msg.content[0].text.strip()
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

    brief = msg.content[0].text
    brief += "\n\n" + _source_index(articles)
    return brief
