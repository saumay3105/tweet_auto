"""
generation/thread_generator.py

Generates a Threads post thread for a topic using creative AI.
No fixed templates — Gemini writes freestyle based on a copywriting brief.

When Gemini is unavailable, a smart fallback uses fetched page context + 
keyword-aware writing to produce something specific and readable.

The only hard constraint: each post ≤ 500 characters (Threads limit).
"""
import json
import logging
import random
import re
import time

from config.settings import (
    GEMINI_API_KEY, GEMINI_MODEL,
    MAX_TWEET_CHARS, REQUEST_RETRIES, REQUEST_BACKOFF_FACTOR,
)
from generation.summarizer import fetch_page_context, extract_keywords

logger = logging.getLogger(__name__)

_gemini_client = None

SOURCE_EMOJIS = {
    "github": "💻",
    "hackernews": "📡",
    "arxiv": "🔬",
    "reddit": "🔥",
}


# ── Gemini client ─────────────────────────────────────────────────────────────

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            _gemini_client = genai.GenerativeModel(GEMINI_MODEL)
            logger.info("Gemini ready (model: %s).", GEMINI_MODEL)
        except Exception as exc:
            logger.error("Gemini init failed: %s", exc)
    return _gemini_client


# ── Post splitting, markdown cleanup & validation ────────────────────────

def strip_markdown(text: str) -> str:
    """
    Remove markdown formatting so posts render as clean plain text on Threads.
    Handles: **bold**, *italic*, __underline__, ~~strike~~, `code`,
    ```code blocks```, # headers, - bullets, > quotes, [links](url).
    """
    # Remove code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code (`...`)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold+italic (***text*** or ___text___)
    text = re.sub(r"[*_]{3}(.+?)[*_]{3}", r"\1", text)
    # Remove bold (**text** or __text__)
    text = re.sub(r"[*_]{2}(.+?)[*_]{2}", r"\1", text)
    # Remove italic (*text* or _text_) — careful not to break underscored_words
    text = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"\1", text)
    # Remove strikethrough (~~text~~)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # Remove headers (# Title)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove blockquotes (> text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Remove bullet points (- item or * item)
    text = re.sub(r"^[\-*]\s+", "", text, flags=re.MULTILINE)
    # Remove numbered lists (1. item)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    # Convert markdown links [text](url) to just text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Clean up any leftover multiple spaces/newlines
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def split_into_posts(raw: str, max_len: int = MAX_TWEET_CHARS) -> list[str]:
    """
    Take a raw multi-post string (separated by blank lines or '---') and
    return a list of clean post strings, each ≤ max_len characters.
    """
    # Split on blank lines or '---' dividers
    blocks = re.split(r"\n\s*---\s*\n|\n{2,}", raw.strip())
    posts = []
    for block in blocks:
        block = strip_markdown(block)
        if not block:
            continue
        # Hard-truncate if over limit
        if len(block) > max_len:
            block = block[:max_len - 1].rstrip() + "…"
        posts.append(block)
    return posts if posts else [strip_markdown(raw)[:max_len]]


def validate_thread(posts: list[str]) -> list[str]:
    """Ensure all posts are within the character limit and markdown-free."""
    valid = []
    for t in posts:
        t = strip_markdown(t)
        if len(t) > MAX_TWEET_CHARS:
            t = t[:MAX_TWEET_CHARS - 1].rstrip() + "…"
        if t.strip():
            valid.append(t)
    return valid


# ── Gemini-based thread generation ────────────────────────────────────────────

def generate_with_gemini(topic: dict, context: str) -> list[str] | None:
    """
    Ask Gemini to freely write a 4-5 tweet thread.
    Returns a list of tweet strings, or None on total failure.
    """
    client = get_gemini_client()
    if not client:
        return None

    title = topic.get("title", "")
    url = topic.get("url", "")
    source = topic.get("source", "")
    emoji = SOURCE_EMOJIS.get(source, "🔥")

    prompt = f"""You are a viral tech personality on Threads — sharp, opinionated, slightly provocative.
Your posts make developers stop scrolling and actually read.

Write a Threads post thread of 4-5 posts about this trending tech topic.

Topic: {title}
Source: {source}
URL: {url}
Extra context: {context[:600] if context else "Not available"}

RULES (non-negotiable):
- Do NOT use a rigid template. Write naturally, like a real person sharing something exciting.
- Post 1 must be a killer hook — a surprising fact, a bold claim, a question, or a contrarian take. Use {emoji} once.
- Each subsequent post must flow from the previous and ADD new information or perspective.
- Use concrete specifics (numbers, names, comparisons) not vague statements.
- End the thread with the URL on its own post: "→ {url}"
- NO hashtags. NO "Follow for more". NO cringe phrases like "game-changing" or "revolutionizing".
- NO markdown formatting. No **bold**, no *italic*, no headers, no bullet points. Write plain text only.
- Each post MUST be under 500 characters.
- Separate posts with a blank line. Nothing else between them.

Write the thread now. Only output the posts, nothing else."""

    delay = 1.0
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            response = client.generate_content(prompt)
            raw = response.text.strip()
            tweets = split_into_posts(raw)
            tweets = validate_thread(tweets)
            if len(tweets) >= 3:
                logger.info("Gemini wrote %d-post thread for: %s", len(tweets), title[:50])
                return tweets
            logger.warning("Gemini output had only %d usable tweets — retrying.", len(tweets))
            raise ValueError("Not enough tweets")
        except Exception as exc:
            logger.warning("Gemini attempt %d/%d failed: %s", attempt, REQUEST_RETRIES, exc)
            if attempt < REQUEST_RETRIES:
                time.sleep(delay)
                delay *= REQUEST_BACKOFF_FACTOR

    return None


# ── Smart fallback thread ─────────────────────────────────────────────────────

def build_fallback_thread(topic: dict, context: str) -> list[str]:
    """
    When Gemini is unavailable, write a specific, engaging thread using:
    - Page-fetched context
    - Keyword detection for specific insights
    - Varied, non-formulaic sentence patterns
    """
    title = topic.get("title", "")
    url = topic.get("url", "")
    source = topic.get("source", "").lower()
    emoji = SOURCE_EMOJIS.get(source, "🔥")
    keywords = [k.lower() for k in extract_keywords(title)]

    # ── Hook variants (pick based on topic type) ───────────────────────────────
    hooks = []

    if any(k in keywords for k in ["agent", "agents", "autonomous", "agentic"]):
        hooks = [
            f"{emoji} AI agents that run themselves without human input just got more capable.\n\nThis is the project everyone will be talking about next week: {title}",
            f"{emoji} What if your AI could write code, debug it, and ship it — all without you?\n\nThat's closer to reality now. Here's why: {title}",
        ]
    elif any(k in keywords for k in ["context", "tokens", "memory", "window", "1m", "million"]):
        hooks = [
            f"{emoji} Fitting an entire codebase into one AI prompt just became real.\n\n{title} — and it's free to try right now.",
            f"{emoji} Imagine asking an AI to review your entire repo in one shot.\n\nThat's what {title} unlocks.",
        ]
    elif any(k in keywords for k in ["llm", "gpt", "claude", "gemini", "model", "open-source", "mistral", "llama"]):
        hooks = [
            f"{emoji} Another AI model dropped — but this one is different.\n\n{title}",
            f"{emoji} The open-source AI race just got more competitive.\n\n{title} — here's what changed.",
        ]
    elif any(k in keywords for k in ["rust", "go", "python", "typescript", "zig", "language"]):
        hooks = [
            f"{emoji} The programming language wars are heating up.\n\n{title} is trending among engineers right now.",
            f"{emoji} Developers are switching tools — and this is causing it:\n\n{title}",
        ]
    elif any(k in keywords for k in ["security", "vulnerability", "exploit", "breach", "hack", "cve"]):
        hooks = [
            f"{emoji} There's a security issue making the rounds in the dev community.\n\nIf you ship software, read this: {title}",
            f"{emoji} A security flaw just surfaced that affects a lot of production systems.\n\n{title} — details inside.",
        ]
    elif any(k in keywords for k in ["paper", "research", "study", "benchmark", "arxiv"]):
        hooks = [
            f"{emoji} A new AI paper just dropped that challenges some widely held assumptions.\n\n{title}",
            f"{emoji} Researchers published something interesting that most engineers haven't seen yet:\n\n{title}",
        ]
    elif source == "github":
        hooks = [
            f"{emoji} A project just hit the GitHub trending page and it's surprisingly useful:\n\n{title}",
            f"{emoji} Open-source developers shipped something worth bookmarking today:\n\n{title}",
        ]
    elif source == "hackernews":
        hooks = [
            f"{emoji} This post hit the top of Hacker News today — and the comments are even more interesting:\n\n{title}",
            f"{emoji} Something on HN is generating serious discussion among engineers right now:\n\n{title}",
        ]

    # Default hook
    if not hooks:
        hooks = [
            f"{emoji} This tech topic is generating serious attention and it's easy to see why:\n\n{title}",
            f"{emoji} Developers across the internet are reacting to this right now:\n\n{title}",
        ]

    hook = random.choice(hooks)

    # ── Body tweet (context-driven) ────────────────────────────────────────────
    if context and len(context) > 40 and context.lower()[:60] != title.lower()[:60]:
        # Take the first clean sentence of the context
        first_sentence = re.split(r"(?<=[.!?])\s+", context.strip())[0]
        if len(first_sentence) > 220:
            first_sentence = first_sentence[:220] + "…"
        body = first_sentence
    else:
        # Derive a body from keywords
        kw_str = " + ".join(k.capitalize() for k in keywords[:3]) if keywords else title
        topic_bodies = [
            f"What makes this compelling: it addresses a problem most teams hit regularly but rarely talk about — {kw_str}.",
            f"The signal here isn't just the project itself, it's the community response. When engineers start discussing {kw_str} this seriously, a shift is coming.",
        ]
        body = random.choice(topic_bodies)

    # ── Insight tweet ──────────────────────────────────────────────────────────
    insights = []
    if any(k in keywords for k in ["agent", "autonomous", "agentic"]):
        insights = [
            "The bottleneck for AI adoption isn't intelligence anymore — it's autonomy. Tools that let models act independently are the ones getting traction.",
            "Every 6 months, autonomous AI gets one layer more capable. The compounding effect of that is something most organizations aren't prepared for.",
        ]
    elif any(k in keywords for k in ["open-source", "github", "library", "framework"]):
        insights = [
            "The fastest-growing open-source projects share one trait: they solve one problem extremely well. That focus is exactly why they spread.",
            "Open-source is eating commercial software — not because it's free, but because developers trust what they can read.",
        ]
    elif any(k in keywords for k in ["paper", "research", "arxiv"]):
        insights = [
            "Academic research and production engineering are closer than they've ever been. Papers from today ship as tools in 12 months.",
            "The most valuable papers aren't the ones with the boldest claims — they're the ones that quietly shift what's considered possible.",
        ]
    elif any(k in keywords for k in ["context", "tokens", "memory"]):
        insights = [
            "More context doesn't just mean bigger — it means fundamentally different product designs. Everything gets rethought when you remove the window limit.",
        ]
    elif any(k in keywords for k in ["security", "vulnerability"]):
        insights = [
            "The most dangerous vulnerabilities aren't the zero-days — they're the ones that sit unpatched for months because teams don't know they exist.",
        ]
    else:
        insights = [
            "What's interesting isn't just the announcement — it's the timing. The underlying need has been building for months.",
            "The developers paying attention to this kind of shift early are the ones who end up shaping how the rest of the industry responds to it.",
        ]

    insight = random.choice(insights)

    # ── Source tweet ───────────────────────────────────────────────────────────
    source_tweet = f"→ {url}"

    thread = [hook, body, insight, source_tweet]
    return validate_thread(thread)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_thread(topic: dict) -> list[str]:
    """
    Generate a creative, curiosity-driven Threads post thread.
    Tries Gemini first, falls back to smart heuristic generation.
    Returns a list of post strings, each ≤ 500 characters.
    """
    title = topic.get("title", "")
    url = topic.get("url", "")
    logger.info("Generating thread for: %s", title[:60])

    # Fetch richer context from the URL
    context = topic.get("description", "")
    if len(context) < 40 and url:
        logger.info("Fetching page context for %s…", url[:70])
        context = fetch_page_context(url)

    # Try Gemini (free creative generation)
    thread = generate_with_gemini(topic, context)

    # Smart fallback if Gemini unavailable or fails
    if not thread:
        logger.info("Using smart fallback thread generator.")
        thread = build_fallback_thread(topic, context)

    for i, tweet in enumerate(thread, 1):
        logger.debug("Tweet %d (%d chars): %s", i, len(tweet), tweet[:60].replace("\n", " "))

    return thread


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    sample = {
        "title": "New open-source autonomous AI agent framework released on GitHub",
        "url": "https://github.com/msitarzewski/agency-agents",
        "source": "github",
        "score": 1500,
        "description": "A complete AI agency at your fingertips — frontend wizards, Reddit community ninjas, whimsy injectors, and more.",
    }
    thread = generate_thread(sample)
    print("\n" + "=" * 60)
    for i, tweet in enumerate(thread, 1):
        print(f"\nTweet {i} ({len(tweet)} chars):\n{tweet}")
        print("-" * 40)
