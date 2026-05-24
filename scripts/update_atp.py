import html
import json
import re
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

ATP_BASE_URL = "https://www.atptour.com"
ATP_CALENDAR_URL = "https://www.atptour.com/en/-/tournaments/calendar/tour"

# Wyniki pobieramy teraz z zakładki Results, a nie z Player Draw.
# To jest znacznie pewniejsze dla zakończonych turniejów, np. Acapulco.
REQUEST_SLEEP_SECONDS = 0.20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.atptour.com/en/tournaments",
}


ROUND_NAMES = [
    "Final",
    "Semifinals",
    "Quarterfinals",
    "Round of 16",
    "Round of 32",
    "Round of 64",
    "Round of 128",
    "2nd Round Qualifying",
    "1st Round Qualifying",
    "Qualifying",
]

ROUND_TO_SHORT = {
    "Final": "F",
    "Semifinals": "SF",
    "Quarterfinals": "QF",
    "Round of 16": "R16",
    "Round of 32": "R32",
    "Round of 64": "R64",
    "Round of 128": "R128",
    "2nd Round Qualifying": "Q2",
    "1st Round Qualifying": "Q1",
    "Qualifying": "Q",
}


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


def save_matches_safely(path: Path, new_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Nie kasuj dobrych danych, jeśli świeży parser zwróci 0 meczów.

    To jest bezpiecznik na wypadek, gdy ATP zmieni HTML albo parser trafi
    na chwilowo pustą/dziwną odpowiedź.
    """
    new_count = int(new_payload.get("count") or 0)
    old_payload = load_existing_json(path)
    old_count = 0
    if isinstance(old_payload, dict):
        old_count = int(old_payload.get("count") or 0)

    if new_count == 0 and old_count > 0:
        old_payload["preservedBecauseNewParseWasEmpty"] = True
        old_payload["lastFailedUpdateAt"] = new_payload.get("generatedAt")
        save_json(path, old_payload)
        return old_payload

    save_json(path, new_payload)
    return new_payload


def fetch_text(url: str, referer: Optional[str] = None) -> str:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer

    response = requests.get(url, headers=headers, timeout=45)
    response.raise_for_status()
    return response.text


def fetch_json(url: str, referer: Optional[str] = None) -> Any:
    headers = dict(HEADERS)
    headers["Accept"] = "application/json, text/plain, */*"
    if referer:
        headers["Referer"] = referer

    response = requests.get(url, headers=headers, timeout=45)
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


def current_results_url_from_archive(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    # /en/scores/archive/hamburg/414/2026/results
    # -> /en/scores/current/hamburg/414/results
    match = re.search(r"(/en/scores/)archive/([^/]+)/([^/]+)/20\d{2}/results", url)
    if match:
        return f"{match.group(1)}current/{match.group(2)}/{match.group(3)}/results"
    return None


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


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def is_date_heading(line: str) -> bool:
    return bool(re.search(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+\w+,\s+20\d{2}", line))


def extract_round_from_line(line: str) -> Optional[str]:
    for round_name in ROUND_NAMES:
        if line.startswith(round_name + " -") or line == round_name:
            return round_name
    return None


def is_noise_line(line: str) -> bool:
    if not line:
        return True

    lower = line.lower()
    if lower.startswith("ump:"):
        return True

    noise_exact = {
        "h2h", "stats", "print", "refresh", "singles", "doubles", "match type",
        "date (all)", "round (all)", "player (all)", "country (all)",
        "timepenalb", "timepenala",
        "centre court", "center court", "court 1", "court 2", "court 3",
        "stadium", "grandstand", "show court"
    }
    if lower in noise_exact:
        return True

    # ATP czasem rozbija nagłówek "Final - Centre Court" na osobne teksty:
    # "Final" i "Centre Court". Wtedy "Centre Court" nie może zostać uznane
    # za zawodnika, bo parser gubi finał.
    if "court" in lower and not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]+\s+[A-Za-zÀ-ÖØ-öø-ÿ]+", line):
        return True
    if lower.endswith(" court") or lower.startswith("court "):
        return True
    if lower.startswith("not before") or lower.startswith("starts at"):
        return True

    if line.startswith("Game Set and Match"):
        return True

    if is_date_heading(line):
        return True

    if extract_round_from_line(line):
        return True

    # same cyfry, wyniki setów, czasy
    if re.fullmatch(r"[\d\s().:-]+", line):
        return True

    # same kwalifikatory/seed bez nazwiska
    if re.fullmatch(r"\([A-Za-z0-9\s.-]+\)", line):
        return True

    return False


def clean_player_name(line: str) -> str:
    line = normalize_space(line)
    # usuń seed/qualifier na końcu, np. "Flavio Cobolli (5)" albo "Patrick Kypson (Q)"
    line = re.sub(r"\s+\([^)]*\)$", "", line).strip()
    return line


def looks_like_player_name(line: str) -> bool:
    line = clean_player_name(line)
    if len(line) < 3:
        return False
    if is_noise_line(line):
        return False
    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", line):
        return False
    # odfiltruj elementy nawigacji
    bad_fragments = [
        "results archive", "atp tour", "apps", "challenger tv",
        "header", "search", "profile", "latest", "close",
        "player-photo", "image:", "wins the point", "match point",
        "break point", "set point", "double fault", "2nd serve",
        "1st serve", "serve.", "ace."
    ]
    if any(x in line.lower() for x in bad_fragments):
        return False
    return True


def parse_score_from_game_set(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Przykład:
    # Game Set and Match Flavio Cobolli. Flavio Cobolli wins the match 7-6(4) 6-4 .
    match = re.search(
        r"Game Set and Match\s+(.+?)\.\s+(.+?)\s+wins the match\s+(.+?)\s*\.?$",
        line,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None, None

    winner_1 = normalize_space(match.group(1))
    winner_2 = normalize_space(match.group(2))
    score = normalize_space(match.group(3))
    winner = winner_2 or winner_1

    # oczyść dziwne końcówki
    score = score.replace(" .", ".").rstrip(".").strip()
    return winner, score, line


def hash_match_id(event_id: str, date: str, round_long: str, p1: str, p2: str, score: str) -> str:
    raw = f"{event_id}|{date}|{round_long}|{p1}|{p2}|{score}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:10].upper()
    return f"RES-{digest}"


def is_score_token(line: str) -> bool:
    line = normalize_space(line)
    if not line or ":" in line:
        return False
    # ATP potrafi pokazać tie-break jako "6 8" albo samą cyfrę seta.
    return bool(re.fullmatch(r"\d+(?:\s+\d+)?|RET|W/O|DEF", line))


def score_main_number(token: str) -> Optional[int]:
    token = normalize_space(token)
    match = re.match(r"(\d+)", token)
    if not match:
        return None
    return int(match.group(1))


def make_score_from_displayed_numbers(p1_scores: List[str], p2_scores: List[str]) -> str:
    sets: List[str] = []
    max_len = min(len(p1_scores), len(p2_scores))

    for idx in range(max_len):
        p1 = normalize_space(p1_scores[idx])
        p2 = normalize_space(p2_scores[idx])

        p1_parts = p1.split()
        p2_parts = p2.split()

        p1_main = p1_parts[0] if p1_parts else p1
        p2_main = p2_parts[0] if p2_parts else p2

        set_text = f"{p1_main}-{p2_main}"

        # Jeśli jedna ze stron ma dodatkową liczbę, traktujemy ją jak tie-break.
        # Przykład z ATP: 7 / 6 8 -> 7-6(8)
        tie = None
        if len(p1_parts) > 1:
            tie = p1_parts[1]
        elif len(p2_parts) > 1:
            tie = p2_parts[1]

        if tie:
            set_text += f"({tie})"

        sets.append(set_text)

    return " ".join(sets)


def winner_from_displayed_scores(player1: str, player2: str, p1_scores: List[str], p2_scores: List[str]) -> str:
    p1_sets = 0
    p2_sets = 0

    for p1, p2 in zip(p1_scores, p2_scores):
        n1 = score_main_number(p1)
        n2 = score_main_number(p2)
        if n1 is None or n2 is None:
            continue
        if n1 > n2:
            p1_sets += 1
        elif n2 > n1:
            p2_sets += 1

    # W widoku ATP zwycięzca często jest pierwszym zawodnikiem w karcie.
    if p1_sets >= p2_sets:
        return player1
    return player2


def parse_match_block(block: List[str], current_date: str, event_id: str) -> Optional[Dict[str, Any]]:
    if not block:
        return None

    round_line = block[0]
    round_long = extract_round_from_line(round_line) or "Round"
    round_short = ROUND_TO_SHORT.get(round_long, round_long)

    game_line = None
    for line in block:
        if line.startswith("Game Set and Match"):
            game_line = line
            break

    # Zamiast brać ślepo pierwsze dwie "nazwy", szukamy pary zawodników,
    # po której realnie występują liczby wyników. To naprawia finały,
    # gdzie ATP dodaje po drodze teksty typu "Centre Court", komunikaty live,
    # obrazki albo notatki punktowe.
    entries: List[Dict[str, Any]] = []
    current_entry: Optional[Dict[str, Any]] = None

    for raw in block[1:]:
        line = normalize_space(raw)

        if not line:
            continue
        if line.startswith("Game Set and Match"):
            break
        if line.lower().startswith("ump:"):
            break
        if line in {"H2H", "Stats"}:
            continue

        # Bardzo ważne: liczby wyników trzeba złapać PRZED is_noise_line().
        # is_noise_line() celowo traktuje same cyfry jako szum, ale tutaj
        # te same cyfry są setami przypisanymi do aktualnego zawodnika.
        if current_entry and is_score_token(line):
            current_entry["scores"].append(line)
            continue

        if is_noise_line(line):
            continue

        if looks_like_player_name(line):
            name = clean_player_name(line)
            current_entry = {"name": name, "scores": []}
            entries.append(current_entry)
            continue

    # Zostaw tylko wpisy, które wyglądają jak zawodnik oraz mają wynik.
    scored_entries = [
        entry for entry in entries
        if entry.get("name") and len(entry.get("scores", [])) > 0
    ]

    if len(scored_entries) < 2:
        return None

    # Najczęściej pierwszy komplet z wynikami to dokładnie para z meczu.
    player1 = scored_entries[0]["name"]
    player2 = scored_entries[1]["name"]
    p1_scores = scored_entries[0]["scores"]
    p2_scores = scored_entries[1]["scores"]

    if game_line:
        winner, score, raw_source = parse_score_from_game_set(game_line)
        if not winner:
            winner = winner_from_displayed_scores(player1, player2, p1_scores, p2_scores)
        if not score:
            score = make_score_from_displayed_numbers(p1_scores, p2_scores)
        if not raw_source:
            raw_source = game_line
    else:
        score = make_score_from_displayed_numbers(p1_scores, p2_scores)
        winner = winner_from_displayed_scores(player1, player2, p1_scores, p2_scores)
        raw_source = "Parsed from displayed score numbers"

    if not score:
        return None

    return {
        "matchId": hash_match_id(event_id, current_date, round_long, player1, player2, score),
        "date": current_date,
        "round": round_short,
        "roundLong": round_long,
        "playerId": "",
        "playerName": player1,
        "opponentId": "",
        "opponentName": player2,
        "winnerPlayerId": "",
        "winnerName": winner,
        "isPlayerWinner": winner == player1,
        "matchState": "F",
        "reason": None,
        "formattedScore": score,
        "sourceText": raw_source,
    }

def parse_results_html(html_text: str, tournament: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    soup = BeautifulSoup(html_text, "html.parser")

    # ATP daje wyniki w HTML jako tekst z karty meczowej.
    lines = [normalize_space(x) for x in soup.stripped_strings]
    lines = [x for x in lines if x]

    event_id = str(tournament.get("id") or "")
    current_date = ""
    current_block: List[str] = []
    matches: List[Dict[str, Any]] = []
    players_seen: Dict[str, Dict[str, str]] = {}

    def flush_current_block() -> None:
        nonlocal current_block, matches, players_seen

        match = parse_match_block(current_block, current_date, event_id)
        if match:
            matches.append(match)
            players_seen[match["playerName"]] = {"id": "", "name": match["playerName"]}
            players_seen[match["opponentName"]] = {"id": "", "name": match["opponentName"]}

        current_block = []

    for line in lines:
        if is_date_heading(line):
            flush_current_block()
            current_date = line
            continue

        found_round = extract_round_from_line(line)
        if found_round:
            flush_current_block()
            current_block = [line]
            continue

        if current_block:
            current_block.append(line)

    flush_current_block()

    # usuń ewentualne duplikaty
    dedup: Dict[str, Dict[str, Any]] = {}
    for match in matches:
        dedup[match["matchId"]] = match

    clean_matches = list(dedup.values())

    round_order = {
        "F": 1,
        "SF": 2,
        "QF": 3,
        "R16": 4,
        "R32": 5,
        "R64": 6,
        "R128": 7,
        "Q2": 8,
        "Q1": 9,
    }
    clean_matches.sort(key=lambda m: (round_order.get(m.get("round", ""), 999), m.get("date", ""), m.get("matchId", "")))

    players = list(players_seen.values())
    players.sort(key=lambda p: p["name"])
    return players, clean_matches

def fetch_tournament_results(tournament: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], Optional[str]]:
    scores_url_raw = tournament.get("scoresUrl")
    current_url = current_results_url_from_archive(scores_url_raw)

    # Ważne:
    # Dla turniejów live ATP często szybciej aktualizuje /current/.../results,
    # a /archive/.../results potrafi być opóźnione. Dlatego live -> current najpierw.
    candidates: List[str] = []
    if tournament.get("isLive") and current_url:
        candidates.append(current_url)

    if scores_url_raw and scores_url_raw not in candidates:
        candidates.append(scores_url_raw)

    if current_url and current_url not in candidates:
        candidates.append(current_url)

    # Awaryjnie z drawUrl tworzymy resultsUrl.
    draws_url = tournament.get("drawsUrl")
    if draws_url:
        results_from_draw = str(draws_url).replace("/draws", "/results")
        if tournament.get("isLive"):
            results_from_draw_current = current_results_url_from_archive(results_from_draw)
            if results_from_draw_current and results_from_draw_current not in candidates:
                candidates.append(results_from_draw_current)
        if results_from_draw not in candidates:
            candidates.append(results_from_draw)

    last_error: Optional[str] = None

    for candidate in candidates:
        full_url = absolute_url(candidate)
        if not full_url:
            continue
        try:
            html_text = fetch_text(full_url, referer="https://www.atptour.com/en/tournaments")
            players, matches = parse_results_html(html_text, tournament)
            return players, matches, full_url
        except Exception as exc:
            last_error = f"{full_url}: {exc}"
            print(f"WARN results page failed: {last_error}")
            time.sleep(REQUEST_SLEEP_SECONDS)

    print(f"WARN no results page parsed for {tournament.get('name')}: {last_error}")
    return [], [], None


def select_tournaments_for_results(flat: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Generujemy wyniki dla turniejów live i zakończonych.
    # Dla nadchodzących nie ma sensu robić matches.json.
    selected = [
        t for t in flat
        if (t.get("isLive") or t.get("isPastEvent")) and t.get("scoresUrl") and t.get("year") and t.get("id")
    ]

    unique: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for tournament in selected:
        key = (str(tournament.get("year")), str(tournament.get("id")))
        unique[key] = tournament

    return list(unique.values())


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

    for index, tournament in enumerate(selected, start=1):
        year = str(tournament.get("year") or "")
        event_id = str(tournament.get("id") or "")
        name = tournament.get("name")
        print(f"[{index}/{len(selected)}] Tournament: {year}/{event_id} {name}")

        try:
            players, matches, source_url = fetch_tournament_results(tournament)
        except Exception as exc:
            print(f"WARN tournament failed: {year}/{event_id} {name}: {exc}")
            players, matches, source_url = [], [], None

        folder = DATA_DIR / year / event_id
        save_json(folder / "tournament.json", tournament)
        save_json(
            folder / "players.json",
            {
                "generatedAt": generated_at,
                "source": source_url,
                "tournament": tournament,
                "count": len(players),
                "players": players,
            },
        )
        matches_payload = {
            "generatedAt": generated_at,
            "source": source_url,
            "tournament": tournament,
            "count": len(matches),
            "matches": matches,
        }
        saved_matches_payload = save_matches_safely(folder / "matches.json", matches_payload)
        saved_matches_count = int(saved_matches_payload.get("count") or 0)

        index_items.append(
            {
                "year": year,
                "id": event_id,
                "name": name,
                "players": len(players),
                "matches": saved_matches_count,
                "matchesPath": f"data/{year}/{event_id}/matches.json",
                "source": source_url,
            }
        )

        time.sleep(REQUEST_SLEEP_SECONDS)

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
