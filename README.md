# Tech Trend AI Bot 🤖🔥

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

## Features

- **Freestyle AI Copywriting**: No templates. Gemini writes curiosity-driven hooks and insights.
- **Smart Fallback**: If Gemini hits a rate limit, the bot uses a rule-based generator with page context.
- **Markdown Stripping**: Automatic removal of `**bold**` and `*italic*` for clean Threads rendering.
- **Duplicate Prevention**: Remembers the last 200 topics in PostgreSQL to avoid reposting.
- **Auto-stop**: If posting fails, the bot stops immediately to prevent spamming the API.
