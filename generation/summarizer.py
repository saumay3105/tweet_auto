"""
generation/summarizer.py
Fetches page context (meta description / Open Graph) for a given topic URL.
This is now a lightweight utility module — thread generation is handled entirely
by thread_generator.py which calls Gemini directly.
"""
import logging
import re
import requests
from bs4 import BeautifulSoup
from config.settings import REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


def fetch_page_context(url: str) -> str:
    """
    Fetch a rich description from a URL using:
      1. og:description (Open Graph)
      2. meta name=description
      3. First non-trivial paragraph (≥60 chars)
    Returns empty string on failure.
    """
    if not url:
        return ""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        og = soup.find("meta", property="og:description")
        if og and og.get("content", "").strip():
            return og["content"].strip()[:600]

        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content", "").strip():
            return meta["content"].strip()[:600]

        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) >= 60:
                return text[:600]
    except Exception as exc:
        logger.debug("fetch_page_context failed for %s: %s", url[:60], exc)
    return ""


def extract_keywords(title: str) -> list[str]:
    """Return meaningful words from a title, filtering common stop-words."""
    stop = {
        "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
        "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
        "that", "this", "it", "its", "be", "has", "have", "had", "now",
        "how", "why", "what", "can", "i", "you", "we", "just", "new",
        "vs", "via", "out", "up", "will", "more", "their", "using", "make",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", title)
    return [w for w in words if w.lower() not in stop and len(w) > 2]
