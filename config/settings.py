"""
config/settings.py
Central configuration — all values loaded from environment variables.
Copy .env.example to .env and fill in your credentials.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Meta Threads API ──────────────────────────────────────────────────────────
THREADS_USER_ID: str = os.environ.get("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN: str = os.environ.get("THREADS_ACCESS_TOKEN", "")

# ── Gemini AI ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ── PostgreSQL ────────────────────────────────────────────────────────────────
# Option A (recommended for Neon.tech / hosted DBs): set the full connection URL
#   DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
# Option B (self-hosted): set individual DB_* vars
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_NAME: str = os.environ.get("DB_NAME", "tweet_bot")
DB_USER: str = os.environ.get("DB_USER", "postgres")
DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")


# ── Scraper Settings ──────────────────────────────────────────────────────────
SCRAPER_TOP_N: int = 10               # Items to return per scraper
REQUEST_TIMEOUT: int = 15             # Seconds before timeout
REQUEST_RETRIES: int = 3              # Number of retry attempts
REQUEST_BACKOFF_FACTOR: float = 1.5   # Exponential backoff multiplier

# ── Ranking ───────────────────────────────────────────────────────────────────
RANKING_TOP_N: int = 3               # How many top topics to evaluate
POSTS_PER_RUN: int = int(os.environ.get("POSTS_PER_RUN", "1"))  # Threads to post per run

SOURCE_WEIGHTS: dict = {
    "github": 1.0,
    "hackernews": 0.9,
    "arxiv": 0.8,
    "reddit": 0.7,
}

# ── Thread Generation ─────────────────────────────────────────────────────────
MAX_TWEET_CHARS: int = 500
THREAD_TWEET_COUNT: int = 5

# ── Posting ───────────────────────────────────────────────────────────────────
TWEET_DELAY_SECONDS: int = 5          # Delay between posts in a thread

# ── Storage ───────────────────────────────────────────────────────────────────
HISTORY_MAX_SIZE: int = 200          # Number of topics to remember

# ── Scheduling ────────────────────────────────────────────────────────────────
SCHEDULE_HOURS: int = int(os.environ.get("SCHEDULE_HOURS", "4"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE: str = "logs/bot.log"
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# ── Dry Run ───────────────────────────────────────────────────────────────────
DRY_RUN: bool = os.environ.get("DRY_RUN", "false").lower() == "true"

# ── User Agent ────────────────────────────────────────────────────────────────
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
