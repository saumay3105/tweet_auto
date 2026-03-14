"""
scrapers/github_trending_scraper.py
Scrapes GitHub Trending page with BeautifulSoup.
Returns up to SCRAPER_TOP_N normalized topic objects.
"""
import logging
import time
import requests
from bs4 import BeautifulSoup
from config.settings import SCRAPER_TOP_N, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR, USER_AGENT

logger = logging.getLogger(__name__)

GITHUB_TRENDING_URL = "https://github.com/trending"


def fetch_html(url: str) -> str | None:
    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            logger.warning("GitHub scraper attempt %d/%d failed: %s", attempt, REQUEST_RETRIES, exc)
            if attempt < REQUEST_RETRIES:
                time.sleep(delay)
                delay *= REQUEST_BACKOFF_FACTOR
    return None


def scrape() -> list[dict]:
    """Return trending GitHub repos as normalized topic dicts."""
    logger.info("Scraping GitHub Trending …")
    html = fetch_html(GITHUB_TRENDING_URL)
    if not html:
        logger.error("GitHub scraper returned no HTML.")
        return []

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article.Box-row")

    results = []
    seen_urls: set[str] = set()

    for article in articles:
        # Repo name
        h2 = article.select_one("h2.h3 a")
        if not h2:
            continue
        repo_path = h2.get("href", "").strip("/")
        title = repo_path.replace("/", " / ")
        url = f"https://github.com/{repo_path}"

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Description
        desc_el = article.select_one("p")
        # Stars today — used as proxy score
        stars_el = article.select_one("span.d-inline-block.float-sm-right")
        stars_text = stars_el.get_text(strip=True) if stars_el else "0"
        # Parse "1,234 stars today" → 1234
        stars_num = 0
        try:
            stars_num = int(stars_text.replace(",", "").split()[0])
        except (ValueError, IndexError):
            pass

        results.append(
            {
                "title": title,
                "url": url,
                "source": "github",
                "score": stars_num,
                "description": desc_el.get_text(strip=True) if desc_el else "",
            }
        )

        if len(results) >= SCRAPER_TOP_N:
            break

    logger.info("GitHub scraper found %d items.", len(results))
    return results


if __name__ == "__main__":
    import json
    logging.basicConfig(level="INFO")
    print(json.dumps(scrape(), indent=2))
