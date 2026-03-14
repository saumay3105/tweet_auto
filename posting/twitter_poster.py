"""
posting/twitter_poster.py
Posts a Twitter/X thread using Playwright with your real Edge profile.

Uses the same approach as save_session.py — copies your Edge profile
to a temp directory and launches Edge with it. This means:
  - You're already logged in (no login flow needed)
  - Twitter can't detect automation
  - No session.json needed

Requirements:
  - You must be logged into x.com in your normal Edge browser
  - Edge must be CLOSED before running (it locks the profile)
"""
import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from config.settings import TWITTER_USERNAME, TWEET_DELAY_SECONDS, PLAYWRIGHT_HEADLESS

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path("logs/screenshots")
EDGE_USER_DATA = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
EDGE_DEFAULT_PROFILE = EDGE_USER_DATA / "Default"


async def save_screenshot(page, name: str):
    """Save a debug screenshot."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f"{name}.png"
        await page.screenshot(path=str(path))
        logger.info("Screenshot saved: %s", path)
    except Exception as exc:
        logger.warning("Screenshot failed: %s", exc)


def copy_edge_profile() -> Path:
    """
    Copy essential Edge profile files to a temp directory.
    Returns the temp dir path.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="tweet_bot_"))
    tmp_default = tmp_dir / "Default"
    tmp_default.mkdir(parents=True, exist_ok=True)

    # Copy cookie and storage files
    for item in ["Cookies", "Local Storage", "Session Storage", "Web Data"]:
        src = EDGE_DEFAULT_PROFILE / item
        try:
            if src.is_file():
                shutil.copy2(src, tmp_default / item)
            elif src.is_dir():
                shutil.copytree(src, tmp_default / item, dirs_exist_ok=True)
        except Exception:
            pass

    # Copy config files
    for item in ["Local State"]:
        src = EDGE_USER_DATA / item
        try:
            if src.is_file():
                shutil.copy2(src, tmp_dir / item)
        except Exception:
            pass

    for item in ["Preferences", "Secure Preferences"]:
        src = EDGE_DEFAULT_PROFILE / item
        try:
            if src.is_file():
                shutil.copy2(src, tmp_default / item)
        except Exception:
            pass

    return tmp_dir


async def post_thread_async(thread: list[str]) -> bool:
    """
    Launch Edge with your real profile, then post the thread.
    Returns True on success, False on failure.
    """
    from playwright.async_api import async_playwright

    if not EDGE_DEFAULT_PROFILE.exists():
        logger.error("Edge profile not found at %s", EDGE_DEFAULT_PROFILE)
        return False

    logger.info("Copying Edge profile…")
    tmp_dir = copy_edge_profile()

    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                str(tmp_dir),
                headless=PLAYWRIGHT_HEADLESS,
                channel="msedge",
                viewport={"width": 1280, "height": 900},
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                # ── Navigate to home and verify login ────────────────────────
                await page.goto("https://x.com/home", wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)

                url = page.url.lower()
                if "login" in url or "flow" in url:
                    logger.error(
                        "Not logged in to Twitter in Edge. "
                        "Please log in to x.com in your normal Edge browser, "
                        "close Edge, and try again."
                    )
                    await save_screenshot(page, "not_logged_in")
                    return False

                logger.info("Logged in via Edge profile (URL: %s).", page.url[:60])

                # ── Post tweet 1 via compose button ──────────────────────────
                logger.info("Opening tweet composer…")
                compose_btn = page.locator(
                    '[data-testid="SideNav_NewTweet_Button"], '
                    '[aria-label="Post"], [aria-label="Tweet"]'
                ).first
                await compose_btn.wait_for(state="visible", timeout=15000)
                await compose_btn.click()
                await page.wait_for_timeout(2000)

                logger.info("Composing tweet 1/%d…", len(thread))
                tweet_box = page.locator('[data-testid="tweetTextarea_0"]').first
                await tweet_box.wait_for(state="visible", timeout=10000)
                await tweet_box.click()
                await tweet_box.type(thread[0], delay=25)
                await page.wait_for_timeout(800)

                post_btn = page.locator(
                    '[data-testid="tweetButtonInline"], [data-testid="tweetButton"]'
                ).first
                await post_btn.wait_for(state="visible", timeout=10000)
                await post_btn.click()
                logger.info("Tweet 1 posted.")
                await page.wait_for_timeout(TWEET_DELAY_SECONDS * 1000)

                # ── Reply chain (tweets 2–N) ─────────────────────────────────
                if len(thread) > 1:
                    await post_replies(page, thread[1:])

                return True

            except Exception as exc:
                logger.error("Twitter poster error: %s", exc, exc_info=True)
                try:
                    await save_screenshot(page, "error_state")
                except Exception:
                    pass
                return False
            finally:
                try:
                    await context.close()
                except Exception:
                    pass

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def post_replies(page, replies: list[str]):
    """Navigate to own profile and reply to the latest tweet to build a thread."""
    logger.info("Navigating to profile for reply chain…")
    await page.goto(f"https://x.com/{TWITTER_USERNAME}", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    first_tweet = page.locator('[data-testid="tweet"]').first
    await first_tweet.wait_for(state="visible", timeout=15000)
    await first_tweet.click()
    await page.wait_for_timeout(2000)

    for i, reply_text in enumerate(replies, start=2):
        logger.info("Composing tweet %d…", i)
        try:
            reply_area = page.locator('[data-testid="tweetTextarea_0"]').first
            await reply_area.wait_for(state="visible", timeout=12000)
            await reply_area.click()
            await reply_area.type(reply_text, delay=25)
            await page.wait_for_timeout(500)

            reply_btn = page.locator(
                '[data-testid="tweetButtonInline"], [data-testid="tweetButton"]'
            ).first
            await reply_btn.wait_for(state="visible", timeout=10000)
            await reply_btn.click()
            logger.info("Tweet %d posted.", i)
            await page.wait_for_timeout(TWEET_DELAY_SECONDS * 1000)
        except Exception as exc:
            logger.error("Failed posting tweet %d: %s", i, exc)
            try:
                await save_screenshot(page, f"error_tweet_{i}")
            except Exception:
                pass
            raise


def post_thread(thread: list[str]) -> bool:
    """Synchronous entry point."""
    return asyncio.run(post_thread_async(thread))
