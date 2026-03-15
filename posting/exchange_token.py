"""
posting/exchange_token.py
Exchange a short-lived Threads token for a long-lived one (60 days).

Usage:
  python posting/exchange_token.py

You need THREADS_APP_SECRET in your .env file (from Meta Developer Dashboard).
The long-lived token is printed — paste it into your .env as THREADS_ACCESS_TOKEN.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv

load_dotenv()

SHORT_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
APP_SECRET = os.environ.get("THREADS_APP_SECRET", "")


def exchange_for_long_lived():
    """Exchange short-lived token → long-lived token (60 days)."""
    if not SHORT_TOKEN:
        print("❌ Set THREADS_ACCESS_TOKEN in .env first (your short-lived token).")
        return
    if not APP_SECRET:
        print("❌ Set THREADS_APP_SECRET in .env first.")
        print("   Find it at: developers.facebook.com → Your App → App Settings → Basic → App Secret")
        return

    url = "https://graph.threads.net/access_token"
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": APP_SECRET,
        "access_token": SHORT_TOKEN,
    }

    resp = requests.get(url, params=params, timeout=30)

    if resp.status_code != 200:
        print(f"❌ Token exchange failed: {resp.text}")
        return

    data = resp.json()
    long_token = data.get("access_token", "")
    expires_in = data.get("expires_in", 0)
    days = expires_in // 86400

    print("=" * 60)
    print("✅ Long-lived token generated!")
    print(f"   Expires in: {days} days")
    print("=" * 60)
    print()
    print("Your new token:")
    print(long_token)
    print()
    print("👉 Paste this into your .env as THREADS_ACCESS_TOKEN")
    print("👉 Also update your GitHub Secret: THREADS_ACCESS_TOKEN")
    print(f"👉 Set a reminder to refresh it in ~{days - 5} days")


def refresh_long_lived():
    """Refresh an existing long-lived token (extends by another 60 days)."""
    if not SHORT_TOKEN:
        print("❌ Set THREADS_ACCESS_TOKEN in .env first.")
        return

    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": SHORT_TOKEN,
    }

    resp = requests.get(url, params=params, timeout=30)

    if resp.status_code != 200:
        print(f"❌ Token refresh failed: {resp.text}")
        print("   If your token is expired, generate a new short-lived one from the API Explorer")
        print("   and run: python posting/exchange_token.py --exchange")
        return

    data = resp.json()
    new_token = data.get("access_token", "")
    expires_in = data.get("expires_in", 0)
    days = expires_in // 86400

    print("=" * 60)
    print("✅ Token refreshed!")
    print(f"   Expires in: {days} days")
    print("=" * 60)
    print()
    print("Your refreshed token:")
    print(new_token)
    print()
    print("👉 Paste this into your .env as THREADS_ACCESS_TOKEN")
    print("👉 Also update your GitHub Secret: THREADS_ACCESS_TOKEN")


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh_long_lived()
    else:
        exchange_for_long_lived()
