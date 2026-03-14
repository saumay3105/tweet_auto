"""
scrapers/reddit_scraper.py
Fetches top posts from tech-related subreddits via RSS feeds.
Uses .rss endpoint (not .json) to avoid 403 blocks on datacenter IPs.
Returns up to SCRAPER_TOP_N normalized topic objects (combined + deduplicated).
"""
import logging
import time
import feedparser
import requests
from config.settings import SCRAPER_TOP_N, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR, USER_AGENT

logger = logging.getLogger(__name__)

SUBREDDITS = [
    "MachineLearning",
    "artificial",
    "programming",
    "technology",
]


def fetch_subreddit(subreddit: str) -> list[dict]:
    """Fetch posts from a subreddit using its RSS feed."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss?limit=15"
    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            posts = []
            for entry in feed.entries:
                posts.append({
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", "").strip(),
                    "score": 0,  # RSS doesn't include score
                })
            return posts
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
        time.sleep(0.5)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    results: list[dict] = []

    for post in all_posts:
        url = post.get("url", "")
        title = post.get("title", "")

        if not title or not url or url in seen_urls:
            continue

        seen_urls.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "source": "reddit",
                "score": post.get("score", 0),
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
