import sys
from playwright.sync_api import sync_playwright

def main() -> int:
    if len(sys.argv) < 2:
        print("Missing URL", file=sys.stderr)
        return 2

    url = sys.argv[1]

    with sync_playwright() as p:
        browser = None
        last_error = None

        launch_args = [
            {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            },
            {
                "channel": "chrome",
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            },
        ]

        for kwargs in launch_args:
            try:
                browser = p.chromium.launch(**kwargs)
                break
            except Exception as exc:
                last_error = exc

        if browser is None:
            print(f"Could not launch browser: {last_error}", file=sys.stderr)
            return 3

        context = browser.new_context(
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
        )

        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
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
            try:
                browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    raise SystemExit(main())
