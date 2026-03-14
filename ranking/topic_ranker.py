"""
ranking/topic_ranker.py
Scores and ranks collected topics using the formula:

  trend_score = (engagement_score × 0.5) + (recency_score × 0.3) + (source_weight × 0.2)

Returns the top RANKING_TOP_N topics.
"""
import logging
import math
from datetime import datetime
from config.settings import RANKING_TOP_N, SOURCE_WEIGHTS

logger = logging.getLogger(__name__)


def engagement_score(raw_score: int, max_score: int) -> float:
    """Normalize engagement to [0, 1] using log scale."""
    if max_score <= 0:
        return 0.0
    if raw_score <= 0:
        return 0.0
    return math.log1p(raw_score) / math.log1p(max_score)


def recency_score(position: int, total: int) -> float:
    """
    Use list position as a proxy for recency (position 0 = most recent / top).
    Score goes from 1.0 (first) to ~0.1 (last).
    """
    if total <= 1:
        return 1.0
    return 1.0 - (position / total)


def rank(topics: list[dict]) -> list[dict]:
    """
    Score and rank a combined list of topic dicts from all scrapers.
    Each dict must have keys: title, url, source, score.
    Returns RANKING_TOP_N topics sorted by trend_score descending.
    """
    if not topics:
        logger.warning("Ranker received empty topic list.")
        return []

    # Max raw score for normalization
    max_raw = max((t.get("score", 0) for t in topics), default=1)
    if max_raw == 0:
        max_raw = 1

    scored: list[dict] = []
    for idx, topic in enumerate(topics):
        source = topic.get("source", "").lower()
        raw_score = int(topic.get("score") or 0)

        eng_s = engagement_score(raw_score, max_raw)
        rec_s = recency_score(idx, len(topics))
        src_w = SOURCE_WEIGHTS.get(source, 0.5)

        trend_score = (eng_s * 0.5) + (rec_s * 0.3) + (src_w * 0.2)

        scored.append({**topic, "trend_score": round(trend_score, 4)})

    scored.sort(key=lambda t: t["trend_score"], reverse=True)

    # Deduplicate by title similarity (basic — exact title match)
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for t in scored:
        norm = t["title"].lower().strip()
        if norm not in seen_titles:
            seen_titles.add(norm)
            unique.append(t)

    top = unique[:RANKING_TOP_N]
    for t in top:
        logger.info(
            "Ranked: [%.4f] %s (%s)",
            t["trend_score"], t["title"][:60], t["source"],
        )
    return top


if __name__ == "__main__":
    import json
    logging.basicConfig(level="INFO")
    # Quick integration test using live scrapers
    from scrapers import hackernews_scraper, github_trending_scraper, arxiv_scraper, reddit_scraper
    all_topics = (
        hackernews_scraper.scrape()
        + github_trending_scraper.scrape()
        + arxiv_scraper.scrape()
        + reddit_scraper.scrape()
    )
    print(f"\nTotal topics collected: {len(all_topics)}")
    ranked = rank(all_topics)
    print(json.dumps(ranked, indent=2))
