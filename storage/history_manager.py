"""
storage/history_manager.py
PostgreSQL-backed history store for posted topics.

Schema:
  tweet_history (
    id            SERIAL PRIMARY KEY,
    url_hash      VARCHAR(64) UNIQUE NOT NULL,
    title         TEXT,
    url           TEXT,
    source        VARCHAR(32),
    trend_score   FLOAT,
    posted_at     TIMESTAMPTZ DEFAULT NOW()
  )

Exposes:
  - init()           — ensure table exists
  - is_duplicate(url) — True if already posted
  - record(topic)    — insert a new entry, prune to HISTORY_MAX_SIZE
  - get_history(n)   — fetch recent n entries
"""
import hashlib
import logging
import time
import psycopg2
import psycopg2.extras
from config.settings import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    HISTORY_MAX_SIZE, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR,
)

logger = logging.getLogger(__name__)

_conn = None


def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        from config.settings import DATABASE_URL, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
        if DATABASE_URL:
            # Neon.tech / hosted DB — full connection URL e.g.
            # postgresql://user:pass@host/dbname?sslmode=require
            _conn = psycopg2.connect(DATABASE_URL)
            logger.info("Connected via DATABASE_URL.")
        else:
            _conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
            logger.info("Connected to PostgreSQL at %s:%s/%s", DB_HOST, DB_PORT, DB_NAME)
        _conn.autocommit = True
    return _conn



def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:64]


def init():
    """Create the tweet_history table if it doesn't exist."""
    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tweet_history (
                        id          SERIAL PRIMARY KEY,
                        url_hash    VARCHAR(64) UNIQUE NOT NULL,
                        title       TEXT,
                        url         TEXT,
                        source      VARCHAR(32),
                        trend_score FLOAT,
                        posted_at   TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_tweet_history_hash
                        ON tweet_history (url_hash);
                    CREATE INDEX IF NOT EXISTS idx_tweet_history_posted_at
                        ON tweet_history (posted_at DESC);
                """)
            logger.info("tweet_history table ready.")
            return
        except Exception as exc:
            logger.warning("DB init attempt %d/%d failed: %s", attempt, REQUEST_RETRIES, exc)
            if attempt < REQUEST_RETRIES:
                time.sleep(delay)
                delay *= REQUEST_BACKOFF_FACTOR
    raise RuntimeError("Could not initialize the tweet_history table.")


def is_duplicate(url: str) -> bool:
    """Return True if this URL has already been posted."""
    try:
        conn = get_conn()
        h = url_hash(url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tweet_history WHERE url_hash = %s LIMIT 1;", (h,))
            return cur.fetchone() is not None
    except Exception as exc:
        logger.error("Duplicate check failed: %s", exc)
        # Fail open — treat as not a duplicate to avoid permanent blocking
        return False


def record(topic: dict):
    """Insert a posted topic into the history table, then prune oldest entries."""
    try:
        conn = get_conn()
        h = url_hash(topic.get("url", ""))
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tweet_history (url_hash, title, url, source, trend_score)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO NOTHING;
                """,
                (
                    h,
                    topic.get("title", "")[:500],
                    topic.get("url", "")[:1000],
                    topic.get("source", "")[:32],
                    float(topic.get("trend_score", 0.0)),
                ),
            )
        prune()
        logger.info("Recorded topic: %s", topic.get("title", "")[:60])
    except Exception as exc:
        logger.error("Failed to record topic: %s", exc)


def prune():
    """Keep only the most recent HISTORY_MAX_SIZE rows."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM tweet_history
                WHERE id NOT IN (
                    SELECT id FROM tweet_history
                    ORDER BY posted_at DESC
                    LIMIT %s
                );
                """,
                (HISTORY_MAX_SIZE,),
            )
    except Exception as exc:
        logger.warning("Prune failed: %s", exc)


def get_history(n: int = 10) -> list[dict]:
    """Fetch the most recent n posted topics."""
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT title, url, source, trend_score, posted_at
                FROM tweet_history
                ORDER BY posted_at DESC
                LIMIT %s;
                """,
                (n,),
            )
            return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.error("get_history failed: %s", exc)
        return []
