"""
scheduler/run_bot.py
Main entry point for the Tech Trend AI Bot.

Usage:
  python scheduler/run_bot.py              # Runs continuously on SCHEDULE_HOURS interval
  python scheduler/run_bot.py --once       # Run exactly once then exit (for GitHub Actions)
  python scheduler/run_bot.py --dry-run    # Run once, print output, skip posting & DB
"""
import argparse
import logging
import os
import sys
import time
import signal
import schedule
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import SCHEDULE_HOURS, DRY_RUN, LOG_FILE, LOG_LEVEL, POSTS_PER_RUN
from scrapers import hackernews_scraper, github_trending_scraper, arxiv_scraper, reddit_scraper
from ranking.topic_ranker import rank
from generation.thread_generator import generate_thread
from posting.threads_poster import post_thread
from storage import history_manager


# ── Logging Setup ─────────────────────────────────────────────────────────────

def setup_logging():
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    log_format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setStream(open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False))
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[file_handler, stream_handler],
    )

logger = logging.getLogger("run_bot")

# ── Graceful Shutdown ─────────────────────────────────────────────────────────

_shutdown = False

def handle_signal(sig, frame):
    global _shutdown
    if not _shutdown:
        logger.info("Shutdown signal received (%s). Finishing current run…", sig)
    _shutdown = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


# ── Core Pipeline ─────────────────────────────────────────────────────────────

def collect_topics() -> list[dict]:
    """Run all scrapers and combine results."""
    logger.info("=" * 60)
    logger.info("Starting topic collection…")
    all_topics = []

    scrapers = [
        ("hackernews", hackernews_scraper.scrape),
        ("github",     github_trending_scraper.scrape),
        ("arxiv",      arxiv_scraper.scrape),
        ("reddit",     reddit_scraper.scrape),
    ]

    for name, fn in scrapers:
        try:
            items = fn()
            logger.info("  %s: %d items", name, len(items))
            all_topics.extend(items)
        except Exception as exc:
            logger.error("Scraper '%s' failed: %s", name, exc)

    logger.info("Total topics collected: %d", len(all_topics))
    return all_topics


def run_pipeline(dry_run: bool = False):
    """Execute the full bot pipeline once."""
    logger.info("━" * 60)
    logger.info("BOT PIPELINE STARTED%s", " [DRY RUN]" if dry_run else "")
    logger.info("━" * 60)

    # 1. Collect
    topics = collect_topics()
    if not topics:
        logger.warning("No topics collected — aborting this run.")
        return

    # 2. Init storage FIRST so we can filter duplicates before ranking
    if not dry_run:
        try:
            history_manager.init()
        except RuntimeError as exc:
            logger.error("DB init failed: %s — aborting.", exc)
            return

        # Filter out already-posted topics BEFORE ranking
        fresh = [t for t in topics if not history_manager.is_duplicate(t.get("url", ""))]
        logger.info("Fresh topics (not yet posted): %d / %d", len(fresh), len(topics))
        if not fresh:
            logger.warning("All scraped topics already posted — nothing new to share.")
            return
    else:
        fresh = topics

    # 3. Rank only fresh topics
    logger.info("Ranking %d fresh topics…", len(fresh))
    ranked = rank(fresh)
    if not ranked:
        logger.warning("Ranker returned no topics — aborting.")
        return

    posted_count = 0
    max_posts = POSTS_PER_RUN if not dry_run else len(ranked)

    for topic in ranked:
        if posted_count >= max_posts:
            logger.info("Reached post limit (%d per run). Stopping.", max_posts)
            break

        title = topic.get("title", "")
        url = topic.get("url", "")
        source = topic.get("source", "")
        score = topic.get("trend_score", 0.0)

        logger.info("\n▶ Processing: [%.4f] %s (%s)", score, title[:70], source)

        # 4. Generate thread
        try:
            thread = generate_thread(topic)
        except Exception as exc:
            logger.error("Thread generation failed for '%s': %s", title[:50], exc)
            continue

        logger.info("  Generated %d-post thread:", len(thread))
        for i, post in enumerate(thread, 1):
            logger.info("  [%d] (%d chars) %s", i, len(post), post[:60].replace("\n", " "))

        if dry_run:
            print("\n" + "═" * 60)
            print(f"[DRY RUN] Thread for: {title}")
            print("═" * 60)
            for i, post in enumerate(thread, 1):
                print(f"\nPost {i} ({len(post)} chars):\n{post}")
            print()
            posted_count += 1
            continue

        # 5. Post to Threads
        logger.info("  Posting thread to Threads…")
        success = post_thread(thread)

        if success:
            history_manager.record(topic)
            posted_count += 1
            logger.info("  ✅ Thread posted and recorded.")
        else:
            logger.error("  ❌ Posting failed for topic: %s", title[:60])
            logger.info("  Stopping — will retry next run.")
            break

    logger.info("━" * 60)
    logger.info("Pipeline complete. Posted: %d thread(s).", posted_count)
    logger.info("━" * 60)


# ── Entrypoint ─────────────────────────────────────────────────────────────────

def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Tech Trend AI Bot")
    parser.add_argument("--once",    action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Run without posting or DB writes")
    args = parser.parse_args()

    effective_dry_run = args.dry_run or DRY_RUN

    if args.once or effective_dry_run:
        logger.info("Running bot once%s…", " (dry-run)" if effective_dry_run else "")
        run_pipeline(dry_run=effective_dry_run)
        logger.info("Single run complete. Exiting.")
        return

    # Continuous scheduler
    logger.info("Starting scheduler — runs every %d hour(s).", SCHEDULE_HOURS)
    schedule.every(SCHEDULE_HOURS).hours.do(run_pipeline)

    # Run immediately on startup
    run_pipeline()

    while not _shutdown:
        schedule.run_pending()
        time.sleep(30)

    logger.info("Bot shut down gracefully.")


if __name__ == "__main__":
    main()
