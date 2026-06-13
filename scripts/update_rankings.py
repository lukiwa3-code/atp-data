import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RANKINGS_DIR = DATA_DIR / "rankings"

ATP_BASE_URL = "https://www.atptour.com"
REQUEST_SLEEP_SECONDS = 0.25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.atptour.com/en/rankings/singles",
}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_existing_json(path: Path) -> Optional[Any]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def player_key(name: Optional[str]) -> str:
    if not name:
        return ""
    value = unicodedata.normalize("NFKD", normalize_space(str(name)))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def full_name_from_player_href(href: Optional[str]) -> tuple[str, str]:
    if not href:
        return "", ""

    match = re.search(r"/players/([^/]+)/([^/?#]+)/overview", href, flags=re.IGNORECASE)
    if not match:
        return "", ""

    slug = match.group(1)
    player_id = match.group(2).upper()

    name = " ".join(part.capitalize() for part in slug.split("-") if part)
    return name, player_id


def looks_like_cloudflare_html(text: str) -> bool:
    low = (text or "").lower()
    return (
        "just a moment" in low
        or "cloudflare" in low and "ray id" in low
        or "performing security verification" in low
        or "enable javascript and cookies" in low
    )


def playwright_fetch_text_subprocess(url: str) -> str:
    helper = BASE_DIR / "scripts" / "playwright_fetch.py"
    if not helper.exists():
        raise RuntimeError(f"Missing Playwright helper: {helper}")

    timeout_seconds = int(os.environ.get("ATP_PLAYWRIGHT_TIMEOUT", "110"))
    result = subprocess.run(
        [sys.executable, str(helper), url],
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Playwright fetch failed for {url}: {err}")

    html_text = result.stdout or ""
    if looks_like_cloudflare_html(html_text):
        raise RuntimeError(f"Playwright returned Cloudflare page for {url}")

    return html_text


def fetch_text(url: str, referer: Optional[str] = None) -> str:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer

    try:
        response = requests.get(url, headers=headers, timeout=45)
        if response.status_code == 403 and os.environ.get("ATP_USE_PLAYWRIGHT", "1") == "1":
            print(f"WARN ranking requests got 403, trying Playwright subprocess: {url}")
            return playwright_fetch_text_subprocess(url)

        response.raise_for_status()
        text = response.text

        if looks_like_cloudflare_html(text) and os.environ.get("ATP_USE_PLAYWRIGHT", "1") == "1":
            print(f"WARN ranking requests got Cloudflare page, trying Playwright subprocess: {url}")
            return playwright_fetch_text_subprocess(url)

        return text

    except Exception:
        # Nie łykamy błędu tutaj. Wyżej decydujemy, czy zachować stare dane.
        raise


def ranking_candidate_urls(ranking_date: str, rank_range: str = "0-5000") -> List[str]:
    # ATP kilka razy zmieniało nazwę parametru daty. Próbujemy kilka wariantów.
    return [
        f"{ATP_BASE_URL}/en/rankings/singles?rankRange={rank_range}&dateWeek={ranking_date}",
        f"{ATP_BASE_URL}/en/rankings/singles?rankRange={rank_range}&rankDate={ranking_date}",
        f"{ATP_BASE_URL}/en/rankings/singles?rankRange={rank_range}&date={ranking_date}",
        f"{ATP_BASE_URL}/en/rankings/singles?dateWeek={ranking_date}&rankRange={rank_range}",
    ]


def parse_rank_from_row_text(row_text: str) -> Optional[int]:
    text = normalize_space(row_text)
    patterns = [
        r"^\s*(\d{1,4})\b",
        r"\bRank\s*#?\s*(\d{1,4})\b",
        r"\bSingles\s+Ranking\s*#?\s*(\d{1,4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None

    return None


def parse_points_from_row_text(row_text: str, rank: Optional[int]) -> Optional[int]:
    text = normalize_space(row_text)
    numbers = [n.replace(",", "") for n in re.findall(r"\b\d{1,3}(?:,\d{3})+|\b\d{2,5}\b", text)]
    parsed: List[int] = []

    for n in numbers:
        try:
            value = int(n)
            parsed.append(value)
        except Exception:
            pass

    # Pierwszą liczbą zwykle jest rank, punktów szukamy później.
    candidates = [v for v in parsed if rank is None or v != rank]
    if not candidates:
        return None

    # Punkty ATP w top 5000 zwykle są największą sensowną liczbą w wierszu.
    return max(candidates)


def parse_ranking_rows_from_html(html_text: str, ranking_date: str, source_url: str) -> Dict[str, Dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    players: Dict[str, Dict[str, Any]] = {}

    rows = soup.select("table tbody tr")
    if not rows:
        rows = soup.select("tr")

    for row in rows:
        row_text = normalize_space(row.get_text(" ", strip=True))
        if not row_text:
            continue

        link = row.select_one("a[href*='/en/players/']")
        if not link:
            continue

        full_name, player_id = full_name_from_player_href(link.get("href"))
        display_name = normalize_space(link.get_text(" ", strip=True)) or full_name

        if not full_name:
            full_name = display_name

        rank = parse_rank_from_row_text(row_text)
        if not rank:
            continue

        key = player_key(full_name or display_name)
        if not key:
            continue

        players[key] = {
            "key": key,
            "name": full_name or display_name,
            "displayName": display_name or full_name,
            "playerId": player_id,
            "rank": rank,
            "points": parse_points_from_row_text(row_text, rank),
            "rankingDate": ranking_date,
            "rankingType": "historical_week",
            "source": source_url,
        }

    # Awaryjnie: jeżeli tabela nie dała wierszy, bierzemy kolejność linków do zawodników.
    # To jest mniej pewne, ale lepsze niż pusty plik.
    if not players:
        seen: Set[str] = set()
        rank_counter = 0

        for link in soup.select("a[href*='/en/players/']"):
            full_name, player_id = full_name_from_player_href(link.get("href"))
            display_name = normalize_space(link.get_text(" ", strip=True)) or full_name

            if not full_name and not display_name:
                continue

            key = player_key(full_name or display_name)
            if not key or key in seen:
                continue

            seen.add(key)
            rank_counter += 1

            players[key] = {
                "key": key,
                "name": full_name or display_name,
                "displayName": display_name or full_name,
                "playerId": player_id,
                "rank": rank_counter,
                "points": None,
                "rankingDate": ranking_date,
                "rankingType": "historical_week_inferred_order",
                "source": source_url,
            }

    return players


def fetch_rankings_for_week(ranking_date: str, rank_range: str) -> tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    last_error: Optional[str] = None

    for url in ranking_candidate_urls(ranking_date, rank_range):
        try:
            html_text = fetch_text(url, referer="https://www.atptour.com/en/rankings/singles")
            players = parse_ranking_rows_from_html(html_text, ranking_date, url)

            if players:
                print(f"Ranking {ranking_date}: {len(players)} players from {url}")
                return players, url

            last_error = f"{url}: parsed 0 ranking players"
            print(f"WARN ranking parsed 0 players: {url}")

        except Exception as exc:
            last_error = f"{url}: {exc}"
            print(f"WARN ranking fetch failed {ranking_date}: {last_error}")
            time.sleep(REQUEST_SLEEP_SECONDS)

    print(f"WARN no ranking parsed for {ranking_date}: {last_error}")
    return {}, None


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def monday_for(value: date) -> date:
    return value - timedelta(days=value.weekday())


def next_monday(value: date) -> date:
    monday = monday_for(value)
    if monday < value:
        return monday + timedelta(days=7)
    return monday


def mondays_between(start: date, end: date) -> List[date]:
    if start > end:
        return []

    current = next_monday(start)
    result: List[date] = []

    while current <= end:
        result.append(current)
        current += timedelta(days=7)

    return result


def ranking_dates_from_args(args: argparse.Namespace) -> List[str]:
    today = datetime.now(timezone.utc).date()
    current_monday = monday_for(today)

    dates: Set[date] = set()

    if args.date:
        for item in args.date:
            for part in str(item).split(","):
                part = part.strip()
                if part:
                    dates.add(monday_for(parse_date(part)))

    if args.start_date:
        start = parse_date(args.start_date)
        end = parse_date(args.end_date) if args.end_date else current_monday
        dates.update(mondays_between(start, end))

    if not dates:
        weeks_back = int(args.weeks_back or 8)
        for i in range(max(1, weeks_back)):
            dates.add(current_monday - timedelta(days=7 * i))

    return [d.isoformat() for d in sorted(dates)]


def update_rankings_index(generated_at: str) -> None:
    items: List[Dict[str, Any]] = []

    for path in sorted(RANKINGS_DIR.glob("*.json")):
        payload = load_existing_json(path)
        if not isinstance(payload, dict):
            continue

        ranking_date = payload.get("rankingDate") or path.stem
        count = int(payload.get("count") or 0)

        items.append(
            {
                "rankingDate": ranking_date,
                "count": count,
                "path": f"data/rankings/{path.name}",
            }
        )

    save_json(
        DATA_DIR / "rankings_index.json",
        {
            "generatedAt": generated_at,
            "count": len(items),
            "items": items,
        },
    )


def save_ranking_week(ranking_date: str, players: Dict[str, Dict[str, Any]], source_url: Optional[str], generated_at: str) -> bool:
    path = RANKINGS_DIR / f"{ranking_date}.json"
    existing = load_existing_json(path)

    if not players:
        # Najważniejszy bezpiecznik: puste pobranie nie kasuje starego rankingu.
        if isinstance(existing, dict) and int(existing.get("count") or 0) > 0:
            print(f"KEEP existing ranking {ranking_date}: new parse empty/blocked")
            return False

        print(f"SKIP empty ranking {ranking_date}: no existing non-empty file")
        return False

    new_payload = {
        "generatedAt": generated_at,
        "rankingDate": ranking_date,
        "source": source_url,
        "count": len(players),
        "players": players,
    }

    # Nie dotykaj pliku, jeśli count i klucze są takie same, a nie wymuszono zapisu.
    if isinstance(existing, dict):
        old_players = existing.get("players")
        if isinstance(old_players, dict) and set(old_players.keys()) == set(players.keys()):
            old_count = int(existing.get("count") or 0)
            if old_count == len(players):
                print(f"UNCHANGED ranking {ranking_date}: {len(players)} players")
                return False

    save_json(path, new_payload)
    print(f"SAVED ranking {ranking_date}: {len(players)} players")
    return True


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update ATP rankings only.")
    parser.add_argument("--date", action="append", help="Specific ranking date, can be repeated or comma-separated.")
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD. Script will use Mondays in range.")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD. Default: current Monday.")
    parser.add_argument("--weeks-back", type=int, default=8, help="Used only when no dates/range are provided.")
    parser.add_argument("--rank-range", default="0-5000", help="ATP rankRange parameter, default 0-5000.")
    parser.add_argument("--force", action="store_true", help="Refetch even if ranking file already exists.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    RANKINGS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    dates = ranking_dates_from_args(args)
    print(f"Selected ranking weeks: {len(dates)}")
    if dates:
        print(f"Range: {dates[0]} -> {dates[-1]}")

    changed_any = False

    for ranking_date in dates:
        path = RANKINGS_DIR / f"{ranking_date}.json"
        existing = load_existing_json(path)

        if not args.force and isinstance(existing, dict) and int(existing.get("count") or 0) > 0:
            print(f"SKIP existing ranking {ranking_date}: count={existing.get('count')}")
            continue

        players, source_url = fetch_rankings_for_week(ranking_date, args.rank_range)
        changed = save_ranking_week(ranking_date, players, source_url, generated_at)
        changed_any = changed_any or changed
        time.sleep(REQUEST_SLEEP_SECONDS)

    # Indeks aktualizujemy po każdym uruchomieniu, ale tylko jeśli istnieją pliki rankingowe.
    if any(RANKINGS_DIR.glob("*.json")):
        update_rankings_index(generated_at)
    else:
        print("No ranking files exist, rankings_index.json not written.")

    if changed_any:
        print("Ranking update done with changes.")
    else:
        print("Ranking update done, no ranking changes.")


if __name__ == "__main__":
    main()
