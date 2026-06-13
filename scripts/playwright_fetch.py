import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def looks_like_cloudflare(page) -> bool:
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""

    try:
        text = (page.locator("body").inner_text(timeout=2000) or "").lower()
    except Exception:
        text = ""

    needles = [
        "just a moment",
        "performing security verification",
        "security service to protect against malicious bots",
        "enable javascript and cookies",
        "ray id:",
        "cloudflare",
    ]
    hay = title + " " + text[:3000]
    return any(n in hay for n in needles)

def main() -> int:
    if len(sys.argv) < 2:
        print("Missing URL", file=sys.stderr)
        return 2

    url = sys.argv[1]
    profile_dir = Path(os.environ.get("ATP_PLAYWRIGHT_PROFILE", "/tmp/atp-playwright-profile"))
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = None
        last_error = None

        launch_options = [
            {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            },
            {
                "channel": "chrome",
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            },
        ]

        for kwargs in launch_options:
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    ),
                    locale="en-US",
                    viewport={"width": 1366, "height": 900},
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Referer": "https://www.atptour.com/en/tournaments",
                    },
                    **kwargs,
                )
                break
            except Exception as exc:
                last_error = exc

        if context is None:
            print(f"Could not launch browser: {last_error}", file=sys.stderr)
            return 3

        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Cloudflare czasem pokazuje "Verification successful. Waiting..."
            # więc czekamy dłużej i dopiero potem oddajemy HTML.
            deadline = time.time() + int(os.environ.get("ATP_CF_WAIT_SECONDS", "75"))
            while time.time() < deadline:
                if not looks_like_cloudflare(page):
                    break
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

            if looks_like_cloudflare(page):
                # Nie oddajemy Cloudflare jako normalnej strony, bo parser potem widzi 0.
                title = ""
                try:
                    title = page.title()
                except Exception:
                    pass
                print(f"Cloudflare page did not clear for {url}; title={title}", file=sys.stderr)
                return 7

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            print(page.content())
            return 0

        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass

if __name__ == "__main__":
    raise SystemExit(main())
