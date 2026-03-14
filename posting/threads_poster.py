"""
posting/threads_poster.py
Posts to Meta Threads using the official Graph API.

No browser automation — just two REST calls:
  1. POST /{user_id}/threads  → create a media container
  2. POST /{user_id}/threads_publish → publish it

Setup:
  1. Create a Meta Developer app at https://developers.facebook.com
  2. Add "Threads API" product to your app
  3. Generate a long-lived access token with threads_content_publish permission
  4. Set THREADS_USER_ID and THREADS_ACCESS_TOKEN in .env

Rate limit: 250 posts per 24 hours.
Post limit: 500 characters per post.
"""
import logging
import time

import requests

from config.settings import THREADS_USER_ID, THREADS_ACCESS_TOKEN

logger = logging.getLogger(__name__)

API_BASE = "https://graph.threads.net/v1.0"


def create_container(text: str, reply_to_id: str = None) -> str | None:
    """
    Create a Threads media container for a text post.
    Returns the container ID, or None on failure.
    """
    url = f"{API_BASE}/{THREADS_USER_ID}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id

    try:
        resp = requests.post(url, data=params, timeout=30)
        resp.raise_for_status()
        container_id = resp.json().get("id")
        logger.debug("Container created: %s", container_id)
        return container_id
    except Exception as exc:
        logger.error("Failed to create container: %s", exc)
        if hasattr(exc, "response") and exc.response is not None:
            logger.error("Response: %s", exc.response.text[:500])
        return None


def publish_container(container_id: str) -> str | None:
    """
    Publish a media container. Returns the published post ID, or None on failure.
    """
    url = f"{API_BASE}/{THREADS_USER_ID}/threads_publish"
    params = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    try:
        resp = requests.post(url, data=params, timeout=30)
        resp.raise_for_status()
        post_id = resp.json().get("id")
        logger.debug("Published post: %s", post_id)
        return post_id
    except Exception as exc:
        logger.error("Failed to publish container: %s", exc)
        if hasattr(exc, "response") and exc.response is not None:
            logger.error("Response: %s", exc.response.text[:500])
        return None


def post_thread(thread: list[str]) -> bool:
    """
    Post a thread on Threads. The first post is a standalone post,
    subsequent posts are replies to build a thread.

    Returns True if at least the first post succeeded.
    """
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        logger.error(
            "THREADS_USER_ID and THREADS_ACCESS_TOKEN must be set in .env. "
            "See: https://developers.facebook.com/docs/threads/get-started"
        )
        return False

    if not thread:
        logger.warning("Empty thread — nothing to post.")
        return False

    # ── Post 1: standalone ────────────────────────────────────────────────────
    logger.info("Creating container for post 1/%d…", len(thread))
    container_id = create_container(thread[0])
    if not container_id:
        return False

    # Wait for server to process (Meta recommends ~30s, but text is fast)
    time.sleep(5)

    logger.info("Publishing post 1…")
    first_post_id = publish_container(container_id)
    if not first_post_id:
        return False

    logger.info("✅ Post 1 published (ID: %s).", first_post_id)

    # ── Posts 2–N: replies to build a thread ──────────────────────────────────
    last_post_id = first_post_id

    for i, text in enumerate(thread[1:], start=2):
        time.sleep(3)  # Brief delay between replies

        logger.info("Creating container for post %d/%d (reply)…", i, len(thread))
        container_id = create_container(text, reply_to_id=last_post_id)
        if not container_id:
            logger.error("Failed to create reply container for post %d.", i)
            break

        time.sleep(5)

        logger.info("Publishing post %d…", i)
        post_id = publish_container(container_id)
        if not post_id:
            logger.error("Failed to publish post %d.", i)
            break

        logger.info("✅ Post %d published (ID: %s).", i, post_id)
        last_post_id = post_id

    return True
