"""
posting/threads_poster.py
Posts to Meta Threads using the official Graph API.

Auto-refreshes the access token on every run so it never expires.
The token refresh extends the expiry by 60 days from current time.
As long as the bot runs at least once every 60 days, you never
need to manually update the token.

No browser automation — just REST calls:
  1. GET  /refresh_access_token    → refresh token (extends 60 days)
  2. POST /{user_id}/threads       → create a media container
  3. POST /{user_id}/threads_publish → publish it

Rate limit: 250 posts per 24 hours.
Post limit: 500 characters per post.
"""
import logging
import time

import requests

from config.settings import THREADS_USER_ID, THREADS_ACCESS_TOKEN

logger = logging.getLogger(__name__)

API_BASE = "https://graph.threads.net/v1.0"

# Module-level token that gets refreshed at runtime
_active_token = THREADS_ACCESS_TOKEN


def refresh_token() -> str:
    """
    Refresh the long-lived token. Returns the new token string,
    or falls back to the original if refresh fails.
    """
    global _active_token

    if not THREADS_ACCESS_TOKEN:
        return ""

    url = f"{API_BASE}/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": THREADS_ACCESS_TOKEN,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        new_token = data.get("access_token", "")
        expires_in = data.get("expires_in", 0)
        days = expires_in // 86400
        if new_token:
            _active_token = new_token
            logger.info("Token refreshed — valid for %d more days.", days)
            return new_token
    except Exception as exc:
        logger.warning("Token refresh failed (will use existing token): %s", exc)

    _active_token = THREADS_ACCESS_TOKEN
    return _active_token


def get_token() -> str:
    """Return the currently active (possibly refreshed) token."""
    return _active_token


def create_container(text: str, reply_to_id: str = None) -> str | None:
    """
    Create a Threads media container for a text post.
    Returns the container ID, or None on failure.
    """
    url = f"{API_BASE}/{THREADS_USER_ID}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": _active_token,
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
        "access_token": _active_token,
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
    Post a thread on Threads. Auto-refreshes the token first.
    The first post is standalone, subsequent posts are replies.

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

    # Refresh token before posting
    refresh_token()

    # ── Post 1: standalone ────────────────────────────────────────────────────
    logger.info("Creating container for post 1/%d…", len(thread))
    container_id = create_container(thread[0])
    if not container_id:
        return False

    # Wait for server to process
    time.sleep(5)

    logger.info("Publishing post 1…")
    first_post_id = publish_container(container_id)
    if not first_post_id:
        return False

    logger.info("✅ Post 1 published (ID: %s).", first_post_id)

    # ── Posts 2–N: replies to build a thread ──────────────────────────────────
    last_post_id = first_post_id

    for i, text in enumerate(thread[1:], start=2):
        time.sleep(3)

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
