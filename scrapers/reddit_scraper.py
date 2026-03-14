"""
scrapers/reddit_scraper.py
Fetches top posts from tech-related subreddits via public Reddit JSON endpoints.
No API key required — uses Reddit's public .json interface.
Returns up to SCRAPER_TOP_N normalized topic objects (combined + deduplicated).
"""
import logging
import time
import requests
from config.settings import SCRAPER_TOP_N, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR, USER_AGENT

logger = logging.getLogger(__name__)

SUBREDDITS = [
    "MachineLearning",
    "artificial",
    "programming",
    "technology",
]

# Limit per subreddit fetch
LIMIT_PER_SUB = 15


def fetch_subreddit(subreddit: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={LIMIT_PER_SUB}"
    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            return [p["data"] for p in posts if p.get("data")]
        except Exception as exc:
            logger.warning(
                "Reddit/%s attempt %d/%d failed: %s",
                subreddit, attempt, REQUEST_RETRIES, exc,
            )
            if attempt < REQUEST_RETRIES:
                time.sleep(delay)
                delay *= REQUEST_BACKOFF_FACTOR
    return []


def scrape() -> list[dict]:
    """Return hot Reddit posts from tech subs as normalized topic dicts."""
    logger.info("Scraping Reddit tech subreddits …")

    all_posts: list[dict] = []
    for sub in SUBREDDITS:
        posts = fetch_subreddit(sub)
        all_posts.extend(posts)
        time.sleep(0.5)   # small delay to be polite

    # Deduplicate by URL, sort by score descending
    seen_urls: set[str] = set()
    results: list[dict] = []

    for post in sorted(all_posts, key=lambda p: p.get("score", 0), reverse=True):
        url = post.get("url", "").strip()
        title = post.get("title", "").strip()
        score = int(post.get("score") or 0)

        if not title or not url or url in seen_urls:
            continue
        # Skip self-posts (text-only), keep them if the link is external
        if url.startswith("https://www.reddit.com"):
            url = f"https://www.reddit.com{post.get('permalink', '')}"

        seen_urls.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "source": "reddit",
                "score": score,
            }
        )

        if len(results) >= SCRAPER_TOP_N:
            break

    logger.info("Reddit scraper found %d items.", len(results))
    return results


if __name__ == "__main__":
    import json
    logging.basicConfig(level="INFO")
    print(json.dumps(scrape(), indent=2))
