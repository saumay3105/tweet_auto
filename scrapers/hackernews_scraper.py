"""
scrapers/hackernews_scraper.py
Fetches top stories from the Hacker News Algolia API (no key needed).
Returns up to SCRAPER_TOP_N normalized topic objects.
"""
import logging
import time
import requests
from config.settings import SCRAPER_TOP_N, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR, USER_AGENT

logger = logging.getLogger(__name__)

HN_API_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"


def get_with_retry(url: str) -> dict | None:
    """GET request with exponential-backoff retries."""
    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("HN scraper attempt %d/%d failed: %s", attempt, REQUEST_RETRIES, exc)
            if attempt < REQUEST_RETRIES:
                time.sleep(delay)
                delay *= REQUEST_BACKOFF_FACTOR
    return None


def scrape() -> list[dict]:
    """Return top HN stories as normalized topic dicts."""
    logger.info("Scraping Hacker News …")
    data = get_with_retry(HN_API_URL)
    if not data:
        logger.error("HN scraper returned no data.")
        return []

    results = []
    seen_urls: set[str] = set()

    for hit in data.get("hits", []):
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        title = hit.get("title", "").strip()
        score = int(hit.get("points") or 0)

        if not title or url in seen_urls:
            continue

        seen_urls.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "source": "hackernews",
                "score": score,
            }
        )

        if len(results) >= SCRAPER_TOP_N:
            break

    logger.info("HN scraper found %d items.", len(results))
    return results


if __name__ == "__main__":
    import json
    logging.basicConfig(level="INFO")
    items = scrape()
    print(json.dumps(items, indent=2))
