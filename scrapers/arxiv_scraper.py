"""
scrapers/arxiv_scraper.py
Fetches recent CS.AI papers from the arXiv Atom feed (no key needed).
Returns up to SCRAPER_TOP_N normalized topic objects.
"""
import logging
import time
import feedparser
import requests
from config.settings import SCRAPER_TOP_N, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR, USER_AGENT

logger = logging.getLogger(__name__)

# arXiv API — last 30 CS.AI submissions sorted by submission date descending
ARXIV_API_URL = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI"
    "&sortBy=submittedDate"
    "&sortOrder=descending"
    "&max_results=30"
)


def fetch_feed(url: str) -> feedparser.FeedParserDict | None:
    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return feedparser.parse(resp.text)
        except Exception as exc:
            logger.warning("arXiv scraper attempt %d/%d failed: %s", attempt, REQUEST_RETRIES, exc)
            if attempt < REQUEST_RETRIES:
                time.sleep(delay)
                delay *= REQUEST_BACKOFF_FACTOR
    return None


def scrape() -> list[dict]:
    """Return recent arXiv CS.AI papers as normalized topic dicts."""
    logger.info("Scraping arXiv CS.AI …")
    feed = fetch_feed(ARXIV_API_URL)
    if not feed or not feed.entries:
        logger.error("arXiv scraper returned no entries.")
        return []

    results = []
    seen_urls: set[str] = set()

    for entry in feed.entries:
        title = entry.get("title", "").replace("\n", " ").strip()
        url = entry.get("link", "").strip()
        summary = entry.get("summary", "").replace("\n", " ").strip()

        if not title or url in seen_urls:
            continue
        seen_urls.add(url)

        # Score proxy: arXiv papers don't have engagement scores,
        # so we use a constant so the recency_score drives ordering.
        results.append(
            {
                "title": title,
                "url": url,
                "source": "arxiv",
                "score": 50,          # constant — recency_score will differentiate
                "description": summary[:300] if summary else "",
            }
        )

        if len(results) >= SCRAPER_TOP_N:
            break

    logger.info("arXiv scraper found %d items.", len(results))
    return results


if __name__ == "__main__":
    import json
    logging.basicConfig(level="INFO")
    print(json.dumps(scrape(), indent=2))
