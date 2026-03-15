# Tech Trend AI Bot

A fully autonomous bot that discovers trending tech topics from Hacker News, GitHub Trending, arXiv, and Reddit — ranks them, generates viral Meta Threads threads using Gemini AI, and posts them automatically.

**Powered by the official Meta Threads API.**

---

## Architecture

```
scrapers/          → Collect topics from 4 sources
ranking/           → Score & rank by engagement + recency + source
generation/        → Summarize with Gemini AI → Build 5-post thread (markdown-free)
posting/           → Post thread via Meta Threads REST API
storage/           → PostgreSQL-backed duplicate prevention
scheduler/run_bot.py → Orchestrates everything
```

---

## Quick Start (Local)

### 1. Clone & set up environment

```bash
git clone https://github.com/YOUR_USERNAME/tweet_auto.git
cd tweet_auto
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your values:

```env
# Meta Threads API
THREADS_USER_ID=your_id
THREADS_ACCESS_TOKEN=your_token

# Gemini AI (Free)
GEMINI_API_KEY=your_key

# Database
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
```

### 3. Test with a dry run

```bash
python scheduler/run_bot.py --dry-run
```

### 4. Run once (posts for real)

```bash
python scheduler/run_bot.py --once
```

---

## 🧵 Threads API Setup

1. Create a Meta Developer account at [developers.facebook.com](https://developers.facebook.com).
2. Create a **Business App** and add the **Threads API** product.
3. Add your Threads account as a **Test User** in the app roles.
4. Generate a **Long-Lived User Access Token** with `threads_basic` and `threads_content_publish` permissions.
5. Get your `THREADS_USER_ID` from the token debugger or API explorer.

---

## 🚀 GitHub Actions Deployment

The bot runs automatically every 4 hours via GitHub Actions.

### Add Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add:

- `THREADS_USER_ID`
- `THREADS_ACCESS_TOKEN`
- `GEMINI_API_KEY`
- `DATABASE_URL` (e.g., from Neon.tech)

The workflow is located at `.github/workflows/post.yml`.

---

## Module Reference

| Module | Purpose |
|--------|---------|
| `scrapers/` | Scrapers for HN, GitHub, arXiv, and Reddit |
| `ranking/topic_ranker.py` | Weighted trend score: engagement + recency + source |
| `generation/thread_generator.py` | 5-post thread builder (≤500 chars, markdown stripped) |
| `posting/threads_poster.py` | Meta Threads REST API integration |
| `storage/history_manager.py` | PostgreSQL duplicate tracking |
| `scheduler/run_bot.py` | Pipeline orchestrator (posts 1 thread per run) |

---

## 📊 Ranking Matrix

Every run, the bot collects ~40 topics from 4 sources and scores each using a weighted formula:

```
trend_score = (engagement × 0.5) + (recency × 0.3) + (source_weight × 0.2)
```

### Scoring Components

| Component | Weight | How It Works |
|-----------|--------|-------------|
| **Engagement** | 50% | Log-normalized score (`log(1+score) / log(1+max_score)`). Prevents viral outliers from dominating. |
| **Recency** | 30% | Position-based: first item in list = 1.0, last = ~0.0. Favors freshly trending topics. |
| **Source Weight** | 20% | Fixed weight per source (see table below). Prioritizes higher-signal sources. |

### Source Weights

| Source | Weight | Why |
|--------|--------|-----|
| GitHub Trending | 1.0 | Strongest signal — repos trend based on real developer activity (stars, forks). |
| Hacker News | 0.9 | High-quality curation — community upvotes filter for technical depth. |
| arXiv CS.AI | 0.8 | Cutting-edge research — slightly lower since papers don't always have mass appeal. |
| Reddit | 0.7 | Broadest reach but noisier — popular posts can be opinion-heavy. |

### Pipeline Flow

```
40 topics scraped
    ↓
Filter out already-posted (DB check)
    ↓
Score & rank remaining fresh topics
    ↓
Pick #1 topic → Generate thread → Post to Threads
    ↓
Record in DB (won't be picked again)
```

---

## Features

- **Freestyle AI Copywriting**: No templates. Gemini writes curiosity-driven hooks and insights.
- **Smart Fallback**: If Gemini hits a rate limit, the bot uses a rule-based generator with page context.
- **Markdown Stripping**: Automatic removal of `**bold**` and `*italic*` for clean Threads rendering.
- **Duplicate Prevention**: Filters already-posted topics **before** ranking, so the bot always picks something fresh.
- **Auto-stop**: If posting fails, the bot stops immediately to prevent spamming the API.
- **1 Thread Per Run**: Posts only the single best topic per run — quality over quantity.

