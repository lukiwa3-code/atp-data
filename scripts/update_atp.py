import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

ATP_CALENDAR_URL = "https://www.atptour.com/en/-/tournaments/calendar/tour"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.atptour.com/en/tournaments",
}


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_year_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    match = re.search(r"/(20\d{2})/", url)
    if match:
        return match.group(1)

    return None


def fetch_calendar() -> Dict[str, Any]:
    response = requests.get(ATP_CALENDAR_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def flatten_tournaments(calendar: Dict[str, Any]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []

    for month in calendar.get("TournamentDates", []):
        display_month = month.get("DisplayDate")
        tournaments = month.get("Tournaments", [])

        for tournament in tournaments:
            draws_url = tournament.get("DrawsUrl")
            scores_url = tournament.get("ScoresUrl")

            year = (
                extract_year_from_url(draws_url)
                or extract_year_from_url(scores_url)
                or extract_year_from_url(tournament.get("ScheduleUrl"))
            )

            flat.append(
                {
                    "id": tournament.get("Id"),
                    "year": year,
                    "name": tournament.get("Name"),
                    "location": tournament.get("Location"),
                    "date": tournament.get("FormattedDate"),
                    "month": display_month,
                    "isLive": tournament.get("IsLive"),
                    "isPastEvent": tournament.get("IsPastEvent"),
                    "type": tournament.get("Type"),
                    "eventType": tournament.get("EventType"),
                    "surface": tournament.get("Surface"),
                    "indoorOutdoor": tournament.get("IndoorOutdoor"),
                    "singlesDrawSize": tournament.get("SglDrawSize"),
                    "doublesDrawSize": tournament.get("DblDrawSize"),
                    "scoresUrl": scores_url,
                    "drawsUrl": draws_url,
                    "scheduleUrl": tournament.get("ScheduleUrl"),
                    "overviewUrl": tournament.get("TournamentOverviewUrl"),
                    "countryFlagUrl": tournament.get("CountryFlagUrl"),
                    "badgeUrl": tournament.get("BadgeUrl"),
                    "prizeMoney": tournament.get("PrizeMoneyDetails"),
                    "totalFinancialCommitment": tournament.get("TotalFinancialCommitment"),
                }
            )

    return flat


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()

    calendar = fetch_calendar()
    flat_tournaments = flatten_tournaments(calendar)

    payload_calendar = {
        "source": ATP_CALENDAR_URL,
        "generatedAt": generated_at,
        "data": calendar,
    }

    payload_flat = {
        "source": ATP_CALENDAR_URL,
        "generatedAt": generated_at,
        "count": len(flat_tournaments),
        "tournaments": flat_tournaments,
    }

    save_json(DATA_DIR / "tournaments.json", payload_calendar)
    save_json(DATA_DIR / "tournaments_flat.json", payload_flat)

    print(f"Zapisano {len(flat_tournaments)} turniejów do data/tournaments_flat.json")


if __name__ == "__main__":
    main()
