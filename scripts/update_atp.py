import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

ATP_BASE_URL = "https://www.atptour.com"
ATP_CALENDAR_URL = "https://www.atptour.com/en/-/tournaments/calendar/tour"

# Bezpieczny start: wyniki generujemy dla turniejów live + ostatnich zakończonych.
# Jak będziesz chciał pełne archiwum 2026, zwiększymy tę wartość albo zrobimy osobny workflow nocny.
PAST_TOURNAMENTS_TO_UPDATE = 16
REQUEST_SLEEP_SECONDS = 0.12

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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_text(url: str, referer: Optional[str] = None) -> str:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=40)
    response.raise_for_status()
    return response.text


def fetch_json(url: str, referer: Optional[str] = None) -> Any:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=40)
    response.raise_for_status()
    return response.json()


def absolute_url(path_or_url: Optional[str]) -> Optional[str]:
    if not path_or_url:
        return None
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if path_or_url.startswith("/"):
        return ATP_BASE_URL + path_or_url
    return ATP_BASE_URL + "/" + path_or_url


def extract_year_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"/(20\d{2})/", url)
    return match.group(1) if match else None


def extract_year_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else None


def fetch_calendar() -> Dict[str, Any]:
    return fetch_json(ATP_CALENDAR_URL)


def flatten_tournaments(calendar: Dict[str, Any]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []

    for month in calendar.get("TournamentDates", []):
        display_month = month.get("DisplayDate")
        tournaments = month.get("Tournaments", [])

        for tournament in tournaments:
            draws_url = tournament.get("DrawsUrl")
            scores_url = tournament.get("ScoresUrl")
            schedule_url = tournament.get("ScheduleUrl")
            singles_pdf = tournament.get("SinglesDrawPrintUrl")

            year = (
                extract_year_from_url(draws_url)
                or extract_year_from_url(scores_url)
                or extract_year_from_url(schedule_url)
                or extract_year_from_url(singles_pdf)
                or extract_year_from_text(tournament.get("FormattedDate"))
                or extract_year_from_text(display_month)
            )

            flat.append(
                {
                    "id": str(tournament.get("Id") or ""),
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
                    "scheduleUrl": schedule_url,
                    "overviewUrl": tournament.get("TournamentOverviewUrl"),
                    "countryFlagUrl": tournament.get("CountryFlagUrl"),
                    "badgeUrl": tournament.get("BadgeUrl"),
                    "prizeMoney": tournament.get("PrizeMoneyDetails"),
                    "totalFinancialCommitment": tournament.get("TotalFinancialCommitment"),
                }
            )

    return flat


def extract_players_from_draw_html(html_text: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    players: Dict[str, Dict[str, str]] = {}

    for option in soup.select("option[data-value]"):
        player_id = (option.get("data-value") or "").strip()
        if not player_id:
            continue

        first = html.unescape(option.get("data-first") or "").strip()
        last = html.unescape(option.get("data-last") or "").strip()
        country_code = html.unescape(option.get("data-country-code") or "").strip()
        country_name = html.unescape(option.get("data-country-name") or "").strip()
        label = html.unescape(option.get_text(" ", strip=True))

        name = (first + " " + last).strip() or label
        if not name or name.lower() == "player draw":
            continue

        players[player_id.upper()] = {
            "id": player_id.upper(),
            "firstName": first,
            "lastName": last,
            "name": name,
            "countryCode": country_code,
            "countryName": country_name,
        }

    return list(players.values())


def build_score(details: Dict[str, Any]) -> str:
    sets: List[str] = []
    for idx in range(1, 6):
        p = details.get(f"Set{idx}Player")
        o = details.get(f"Set{idx}Opponent")
        tie = details.get(f"Set{idx}Tie")
        if p is None or o is None or str(p).strip() == "" or str(o).strip() == "":
            continue
        set_text = f"{p}-{o}"
        if tie is not None and str(tie).strip() != "":
            set_text += f"({tie})"
        sets.append(set_text)
    return " ".join(sets)


def normalize_match(player: Dict[str, str], result_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    round_obj = result_item.get("Round") or {}
    details = round_obj.get("MatchDetails") or {}
    match_id = details.get("MatchId")
    if not match_id:
        return None

    opponent_first = html.unescape(str(details.get("OpponentFirstName") or "")).strip()
    opponent_last = html.unescape(str(details.get("OpponentLastName") or "")).strip()
    opponent_name = (opponent_first + " " + opponent_last).strip()
    is_player_winner = bool(details.get("IsPlayerWinner"))
    winner_name = player["name"] if is_player_winner else opponent_name

    return {
        "matchId": match_id,
        "roundId": str(round_obj.get("Id") or ""),
        "round": round_obj.get("ShortName"),
        "roundLong": round_obj.get("LongName"),
        "playerId": player["id"],
        "playerName": player["name"],
        "opponentId": str(details.get("OpponentId") or "").upper(),
        "opponentName": opponent_name,
        "winnerPlayerId": details.get("WinnerPlayerId"),
        "winnerName": winner_name,
        "isPlayerWinner": is_player_winner,
        "matchState": details.get("MatchState"),
        "reason": details.get("Reason"),
        "formattedScore": build_score(details),
        "sets": [
            {
                "set": idx,
                "player": details.get(f"Set{idx}Player"),
                "opponent": details.get(f"Set{idx}Opponent"),
                "tie": details.get(f"Set{idx}Tie"),
            }
            for idx in range(1, 6)
            if details.get(f"Set{idx}Player") is not None and details.get(f"Set{idx}Opponent") is not None
        ],
    }


def fetch_tournament_matches(tournament: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    year = str(tournament.get("year") or "").strip()
    event_id = str(tournament.get("id") or "").strip()
    draws_url = absolute_url(tournament.get("drawsUrl"))

    if not year or not event_id or not draws_url:
        return [], []

    html_text = fetch_text(draws_url, referer="https://www.atptour.com/en/tournaments")
    players = extract_players_from_draw_html(html_text)

    matches: List[Dict[str, Any]] = []
    seen_match_ids: Set[str] = set()

    for idx, player in enumerate(players):
        player_id = player["id"]
        api_url = f"{ATP_BASE_URL}/-/ls/playerdrawpath/grouped/{year}/{event_id}/{player_id}"

        try:
            payload = fetch_json(api_url, referer=draws_url)
        except Exception as exc:
            print(f"WARN playerdraw failed: {event_id}/{year}/{player_id}: {exc}")
            continue

        for result_item in payload.get("MatchResults", []) or []:
            match = normalize_match(player, result_item)
            if not match:
                continue
            match_id = str(match["matchId"])
            if match_id in seen_match_ids:
                continue
            seen_match_ids.add(match_id)
            matches.append(match)

        if idx % 10 == 0:
            print(f"  players checked: {idx + 1}/{len(players)} for {tournament.get('name')}")
        time.sleep(REQUEST_SLEEP_SECONDS)

    matches.sort(key=lambda m: (int(m.get("roundId") or 999), str(m.get("matchId") or "")))
    return players, matches


def select_tournaments_for_results(flat: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    live = [t for t in flat if t.get("isLive")]
    past = [t for t in flat if t.get("isPastEvent") and not t.get("isLive")]
    recent_past = past[-PAST_TOURNAMENTS_TO_UPDATE:]

    selected: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for tournament in recent_past + live:
        key = (str(tournament.get("year") or ""), str(tournament.get("id") or ""))
        if key[0] and key[1]:
            selected[key] = tournament
    return list(selected.values())


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    print("Fetching ATP calendar...")
    calendar = fetch_calendar()
    flat_tournaments = flatten_tournaments(calendar)

    save_json(
        DATA_DIR / "tournaments.json",
        {
            "source": ATP_CALENDAR_URL,
            "generatedAt": generated_at,
            "data": calendar,
        },
    )

    save_json(
        DATA_DIR / "tournaments_flat.json",
        {
            "source": ATP_CALENDAR_URL,
            "generatedAt": generated_at,
            "count": len(flat_tournaments),
            "tournaments": flat_tournaments,
        },
    )

    selected = select_tournaments_for_results(flat_tournaments)
    print(f"Generating results for {len(selected)} tournaments...")

    index_items: List[Dict[str, Any]] = []

    for tournament in selected:
        year = str(tournament.get("year") or "")
        event_id = str(tournament.get("id") or "")
        name = tournament.get("name")
        print(f"Tournament: {year}/{event_id} {name}")

        try:
            players, matches = fetch_tournament_matches(tournament)
        except Exception as exc:
            print(f"WARN tournament failed: {year}/{event_id} {name}: {exc}")
            players, matches = [], []

        folder = DATA_DIR / year / event_id
        save_json(folder / "tournament.json", tournament)
        save_json(
            folder / "players.json",
            {
                "generatedAt": generated_at,
                "tournament": tournament,
                "count": len(players),
                "players": players,
            },
        )
        save_json(
            folder / "matches.json",
            {
                "generatedAt": generated_at,
                "tournament": tournament,
                "count": len(matches),
                "matches": matches,
            },
        )

        index_items.append(
            {
                "year": year,
                "id": event_id,
                "name": name,
                "players": len(players),
                "matches": len(matches),
                "matchesPath": f"data/{year}/{event_id}/matches.json",
            }
        )

    save_json(
        DATA_DIR / "results_index.json",
        {
            "generatedAt": generated_at,
            "count": len(index_items),
            "items": index_items,
        },
    )

    print("Done.")


if __name__ == "__main__":
    main()
