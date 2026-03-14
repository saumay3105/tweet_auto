"""
posting/save_session.py
Extracts Twitter session cookies from your REAL Edge browser profile
(where you're already logged in) and saves them for the bot.

No Playwright automation login needed — just reads your existing cookies.

Usage:
  1. Make sure you're logged into x.com in Edge (your normal browser)
  2. CLOSE Edge completely (important — Edge locks the profile while running)
  3. Run: python posting/save_session.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

SESSION_FILE = Path("posting/session.json")

# Edge user data directory on Windows
EDGE_USER_DATA = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
EDGE_DEFAULT_PROFILE = EDGE_USER_DATA / "Default"


def extract_cookies_from_edge():
    """
    Launch Edge via Playwright using a COPY of the user's real profile,
    navigate to x.com, and save the session state.
    """
    import asyncio

    async def run():
        from playwright.async_api import async_playwright

        if not EDGE_USER_DATA.exists():
            print("❌ Could not find Edge profile at:", EDGE_USER_DATA)
            print("   Make sure Microsoft Edge is installed.")
            return False

        # Copy profile to a temp dir (Edge locks the original while running)
        tmp_dir = Path(tempfile.mkdtemp(prefix="tweet_bot_edge_"))
        print(f"📂 Copying Edge profile to temp directory…")
        try:
            # Copy only essential cookie/storage files to keep it fast
            tmp_default = tmp_dir / "Default"
            tmp_default.mkdir(parents=True, exist_ok=True)

            for item in ["Cookies", "Local Storage", "Session Storage", "Web Data"]:
                src = EDGE_DEFAULT_PROFILE / item
                dst = tmp_default / item
                if src.is_file():
                    shutil.copy2(src, dst)
                elif src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)

            # Also need Local State and Preferences
            for item in ["Local State"]:
                src = EDGE_USER_DATA / item
                if src.is_file():
                    shutil.copy2(src, tmp_dir / item)

            for item in ["Preferences", "Secure Preferences"]:
                src = EDGE_DEFAULT_PROFILE / item
                if src.is_file():
                    shutil.copy2(src, tmp_default / item)

        except Exception as e:
            print(f"⚠️  Profile copy had some issues (non-fatal): {e}")

        print("🚀 Launching Edge with your profile to grab Twitter session…\n")

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                str(tmp_dir),
                channel="msedge",
                headless=False,
                viewport={"width": 1280, "height": 900},
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://x.com/home", wait_until="domcontentloaded")

            print("⏳ Checking if you're logged in to Twitter…")
            # Wait a bit for redirects
            for _ in range(15):
                await asyncio.sleep(1)
                url = page.url.lower()
                if "home" in url and "login" not in url:
                    break

            url = page.url.lower()
            if "login" in url or "flow" in url:
                print("\n⚠️  You're NOT logged in to Twitter in Edge.")
                print("   Please log in to x.com in your normal Edge browser first,")
                print("   then close Edge and re-run this script.\n")
                await context.close()
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return False

            # Save session state
            await context.storage_state(path=str(SESSION_FILE))
            print(f"\n✅ Session saved to: {SESSION_FILE}")
            print("   The bot will reuse this session automatically.")
            print("   Run: python scheduler/run_bot.py --once\n")

            await context.close()

        # Cleanup temp profile
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return True

    return asyncio.run(run())


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Twitter Session Extractor")
    print("=" * 50)

    if not EDGE_DEFAULT_PROFILE.exists():
        print("\n❌ Edge profile not found. Make sure Edge is installed")
        print(f"   Expected at: {EDGE_USER_DATA}\n")
        sys.exit(1)

    print("\n⚠️  IMPORTANT: Close Edge completely before running this!\n")

    success = extract_cookies_from_edge()
    if not success:
        sys.exit(1)
