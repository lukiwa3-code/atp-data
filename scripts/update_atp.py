import html
import json
import re
import time
import unicodedata
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

ATP_BASE_URL = "https://www.atptour.com"
ATP_CALENDAR_URL = "https://www.atptour.com/en/-/tournaments/calendar/tour"
HISTORY_YEARS = [2025, 2026]

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


def calendar_urls_for_year(year: int) -> List[str]:
    return [
        f"{ATP_CALENDAR_URL}?year={year}",
        f"{ATP_CALENDAR_URL}?Year={year}",
        f"{ATP_CALENDAR_URL}?tournamentYear={year}",
        f"{ATP_CALENDAR_URL}?season={year}",
    ]


def fetch_calendar() -> Dict[str, Any]:
    return fetch_json(ATP_CALENDAR_URL)


def fetch_calendar_for_year(year: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    candidates = calendar_urls_for_year(year)

    try:
        current_year = datetime.now(timezone.utc).year
        if year == current_year:
            candidates.insert(0, ATP_CALENDAR_URL)
    except Exception:
        pass

    last_error = None

    for url in candidates:
        try:
            calendar = fetch_json(url)
            flat = flatten_tournaments(calendar)
            matching_year = [
                item for item in flat
                if str(item.get("year") or "") == str(year)
            ]

            if matching_year:
                print(f"Calendar {year}: {len(matching_year)} tournaments from {url}")
                return calendar, url

        except Exception as exc:
            last_error = exc
            print(f"WARN calendar fetch failed for {year} {url}: {exc}")
            time.sleep(REQUEST_SLEEP_SECONDS)

    print(f"WARN no calendar found for {year}: {last_error}")
    return None, None


def flatten_multi_year_calendars(years: List[int]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    flat_all: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []

    for year in years:
        calendar, source_url = fetch_calendar_for_year(year)
        if not calendar:
            continue

        flat = flatten_tournaments(calendar)
        flat = [
            item for item in flat
            if str(item.get("year") or "") == str(year)
        ]

        flat_all.extend(flat)
        sources.append(
            {
                "year": year,
                "source": source_url,
                "count": len(flat),
                "data": calendar,
            }
        )

    dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in flat_all:
        key = (str(item.get("year") or ""), str(item.get("id") or ""))
        dedup[key] = item

    result = list(dedup.values())
    result.sort(key=lambda item: (str(item.get("year") or ""), str(item.get("month") or ""), str(item.get("date") or "")))

    return result, sources


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
    return bool(re.fullmatch(r"\d+(?:\s+\d+)?|RET|W/O|DEF", line))


def score_main_number(token: str) -> Optional[int]:
    token = normalize_space(token)
    match = re.match(r"(\d+)", token)
    if not match:
        return None
    return int(match.group(1))


def score_extra_number(token: str) -> Optional[str]:
    parts = normalize_space(token).split()
    if len(parts) > 1 and re.fullmatch(r"\d+", parts[1]):
        return parts[1]
    return None


def is_plain_digit_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+", normalize_space(token)))


def valid_set_score(a: int, b: int) -> bool:
    if (a == 7 and b in (5, 6)) or (b == 7 and a in (5, 6)):
        return True
    if (a == 6 and b <= 4) or (b == 6 and a <= 4):
        return True
    if max(a, b) >= 6 and abs(a - b) >= 2:
        return True
    return False


def parse_score_paths(p1_scores: List[str], p2_scores: List[str]) -> List[List[Dict[str, Any]]]:
    memo: Dict[Tuple[int, int], List[List[Dict[str, Any]]]] = {}

    def rec(i: int, j: int) -> List[List[Dict[str, Any]]]:
        key = (i, j)
        if key in memo:
            return memo[key]

        if i >= len(p1_scores) and j >= len(p2_scores):
            return [[]]

        if i >= len(p1_scores) or j >= len(p2_scores):
            return []

        p1_token = normalize_space(p1_scores[i])
        p2_token = normalize_space(p2_scores[j])
        n1 = score_main_number(p1_token)
        n2 = score_main_number(p2_token)

        if n1 is None or n2 is None:
            memo[key] = []
            return []

        paths: List[List[Dict[str, Any]]] = []

        def add_option(next_i: int, next_j: int, tie: Optional[str]) -> None:
            for tail in rec(next_i, next_j):
                paths.append([{"p1": n1, "p2": n2, "tie": tie}] + tail)

        if valid_set_score(n1, n2):
            tie_same_token = None
            if n1 == 7 and n2 == 6:
                tie_same_token = score_extra_number(p2_token)
            elif n2 == 7 and n1 == 6:
                tie_same_token = score_extra_number(p1_token)

            add_option(i + 1, j + 1, tie_same_token)

            # Tie-break może być osobnym kolejnym tokenem po stronie przegranego.
            # To naprawia Grand Slam, gdzie wynik potrafi przyjść jako:
            # p1: 6, 7, 6, 5, 6
            # p2: 3, 6, 6, 7, 0
            # czyli: 6-3 7-6(6) 6-7(5) 6-0
            if n1 == 7 and n2 == 6 and j + 1 < len(p2_scores):
                next_loser = normalize_space(p2_scores[j + 1])
                if is_plain_digit_token(next_loser):
                    add_option(i + 1, j + 2, next_loser)

            if n2 == 7 and n1 == 6 and i + 1 < len(p1_scores):
                next_loser = normalize_space(p1_scores[i + 1])
                if is_plain_digit_token(next_loser):
                    add_option(i + 2, j + 1, next_loser)

        memo[key] = paths
        return paths

    return rec(0, 0)


def score_path_quality(path: List[Dict[str, Any]], total_tokens: int) -> Tuple[int, int, int, int]:
    suspicious = 0
    tiebreaks = 0

    for one_set in path:
        p1 = one_set["p1"]
        p2 = one_set["p2"]
        tie = one_set.get("tie")
        if p1 == 6 and p2 == 6:
            suspicious += 1
        if ((p1 == 7 and p2 == 6) or (p1 == 6 and p2 == 7)) and tie:
            tiebreaks += 1

    return (
        -suspicious,
        tiebreaks,
        len(path),
        -abs(len(path) - min(5, total_tokens // 2)),
    )


def choose_best_score_path(p1_scores: List[str], p2_scores: List[str]) -> List[Dict[str, Any]]:
    paths = parse_score_paths(p1_scores, p2_scores)
    if not paths:
        return []

    total_tokens = len(p1_scores) + len(p2_scores)
    return max(paths, key=lambda path: score_path_quality(path, total_tokens))


def score_text_from_path(path: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for one_set in path:
        set_text = f"{one_set['p1']}-{one_set['p2']}"
        tie = one_set.get("tie")
        if tie:
            set_text += f"({tie})"
        parts.append(set_text)
    return " ".join(parts)


def make_score_from_displayed_numbers(p1_scores: List[str], p2_scores: List[str]) -> str:
    return score_text_from_path(choose_best_score_path(p1_scores, p2_scores))


def winner_from_displayed_scores(player1: str, player2: str, p1_scores: List[str], p2_scores: List[str]) -> str:
    path = choose_best_score_path(p1_scores, p2_scores)

    p1_sets = 0
    p2_sets = 0

    for one_set in path:
        n1 = int(one_set["p1"])
        n2 = int(one_set["p2"])
        if n1 > n2:
            p1_sets += 1
        elif n2 > n1:
            p2_sets += 1

    if p1_sets >= p2_sets:
        return player1
    return player2


def parse_walkover_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    # Przykład z ATP:
    # Winner: V. VACHEROT by Walkover
    match = re.search(r"Winner:\s+(.+?)\s+by\s+(.+)$", line, flags=re.IGNORECASE)
    if not match:
        return None, None

    winner_text = normalize_space(match.group(1))
    reason_text = normalize_space(match.group(2))
    return winner_text, reason_text


def normalize_for_match(value: str) -> str:
    value = normalize_space(value).lower()
    value = re.sub(r"[^a-zà-öø-ÿ\s.]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def winner_text_matches_name(winner_text: str, candidate_name: str) -> bool:
    # Obsługuje warianty typu:
    # "V. VACHEROT" -> "Valentin Vacherot"
    # "T. PAUL" -> "Tommy Paul"
    w = normalize_for_match(winner_text)
    c = normalize_for_match(candidate_name)

    if not w or not c:
        return False

    if w == c:
        return True

    w_parts = w.replace(".", "").split()
    c_parts = c.split()

    if not w_parts or not c_parts:
        return False

    # Pełne nazwisko zwykle jest ostatnim elementem.
    w_last = w_parts[-1]
    c_last = c_parts[-1]

    if w_last != c_last:
        return False

    # Jeśli ATP podało inicjał, porównaj z pierwszą literą imienia.
    if len(w_parts) >= 2 and len(c_parts) >= 2:
        w_initial = w_parts[0][0]
        c_initial = c_parts[0][0]
        return w_initial == c_initial

    return True


def choose_walkover_winner(winner_text: str, candidate_names: List[str]) -> Optional[str]:
    for candidate in candidate_names:
        if winner_text_matches_name(winner_text, candidate):
            return candidate
    return candidate_names[0] if candidate_names else None

def parse_match_block(block: List[str], current_date: str, event_id: str) -> Optional[Dict[str, Any]]:
    if not block:
        return None

    round_line = block[0]
    round_long = extract_round_from_line(round_line) or "Round"
    round_short = ROUND_TO_SHORT.get(round_long, round_long)

    game_line = None
    walkover_winner_text = None
    walkover_reason = None

    for line in block:
        if line.startswith("Game Set and Match"):
            game_line = line
        winner_text, reason_text = parse_walkover_line(line)
        if winner_text:
            walkover_winner_text = winner_text
            walkover_reason = reason_text

    entries: List[Dict[str, Any]] = []
    current_entry: Optional[Dict[str, Any]] = None

    for raw in block[1:]:
        line = normalize_space(raw)

        if not line:
            continue
        if line.startswith("Game Set and Match"):
            break

        # Nie przerywamy na Ump/H2H, bo przy walkowerach ATP pokazuje
        # "Winner: ... by Walkover" dopiero po tych elementach.
        if line.lower().startswith("ump:"):
            continue
        if line in {"H2H", "Stats"}:
            continue
        if parse_walkover_line(line)[0]:
            continue

        # Najpierw łapiemy liczby, bo is_noise_line traktuje same cyfry jako szum.
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

    candidate_names = []
    for entry in entries:
        name = entry.get("name")
        if name and name not in candidate_names:
            candidate_names.append(name)

    # WALKOVER / W/O
    if walkover_winner_text and len(candidate_names) >= 2:
        winner = choose_walkover_winner(walkover_winner_text, candidate_names)
        if not winner:
            return None

        loser = next((name for name in candidate_names if name != winner), candidate_names[1])

        reason_clean = walkover_reason or "Walkover"
        reason_upper = reason_clean.upper()
        if "WALKOVER" in reason_upper:
            score = "W/O"
        else:
            score = reason_clean

        return {
            "matchId": hash_match_id(event_id, current_date, round_long, winner, loser, score),
            "date": current_date,
            "round": round_short,
            "roundLong": round_long,
            "playerId": "",
            "playerName": winner,
            "opponentId": "",
            "opponentName": loser,
            "winnerPlayerId": "",
            "winnerName": winner,
            "isPlayerWinner": True,
            "matchState": "F",
            "reason": reason_clean,
            "formattedScore": score,
            "sourceText": f"Winner: {walkover_winner_text} by {reason_clean}",
        }

    scored_entries = [
        entry for entry in entries
        if entry.get("name") and len(entry.get("scores", [])) > 0
    ]

    if len(scored_entries) < 2:
        return None

    raw_player1 = scored_entries[0]["name"]
    raw_player2 = scored_entries[1]["name"]
    raw_p1_scores = scored_entries[0]["scores"]
    raw_p2_scores = scored_entries[1]["scores"]

    if game_line:
        winner, score, raw_source = parse_score_from_game_set(game_line)
        if not winner:
            winner = winner_from_displayed_scores(raw_player1, raw_player2, raw_p1_scores, raw_p2_scores)
        if not score:
            if winner == raw_player2:
                score = make_score_from_displayed_numbers(raw_p2_scores, raw_p1_scores)
            else:
                score = make_score_from_displayed_numbers(raw_p1_scores, raw_p2_scores)
        if not raw_source:
            raw_source = game_line

        if winner == raw_player2:
            player1 = raw_player2
            player2 = raw_player1
        else:
            player1 = raw_player1
            player2 = raw_player2

    else:
        winner = winner_from_displayed_scores(raw_player1, raw_player2, raw_p1_scores, raw_p2_scores)

        if winner == raw_player2:
            player1 = raw_player2
            player2 = raw_player1
            score = make_score_from_displayed_numbers(raw_p2_scores, raw_p1_scores)
        else:
            player1 = raw_player1
            player2 = raw_player2
            score = make_score_from_displayed_numbers(raw_p1_scores, raw_p2_scores)

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
        "winnerName": player1,
        "isPlayerWinner": True,
        "matchState": "F",
        "reason": None,
        "formattedScore": score,
        "sourceText": raw_source,
    }


def player_key(name: Optional[str]) -> str:
    if not name:
        return ""
    value = unicodedata.normalize("NFKD", normalize_space(str(name)))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def original_order(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda item: int(item.get("_originalIndex", 0)))


def order_previous_round_by_next_round(
    previous_round_matches: List[Dict[str, Any]],
    next_round_matches_ordered: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    previous_by_winner: Dict[str, Dict[str, Any]] = {}

    for match in previous_round_matches:
        key = player_key(match.get("winnerName") or match.get("playerName"))
        if key and key not in previous_by_winner:
            previous_by_winner[key] = match

    ordered: List[Dict[str, Any]] = []
    used_ids = set()

    for next_match in next_round_matches_ordered:
        # Kolejność dwóch zawodników w następnym meczu wskazuje górną i dolną gałąź drabinki.
        for participant in [next_match.get("playerName"), next_match.get("opponentName")]:
            previous_match = previous_by_winner.get(player_key(participant))
            if not previous_match:
                continue

            marker = previous_match.get("matchId") or id(previous_match)
            if marker in used_ids:
                continue

            ordered.append(previous_match)
            used_ids.add(marker)

    # Bezpiecznik: jeśli czegoś nie da się wywnioskować, zostawiamy resztę w kolejności z ATP.
    for match in original_order(previous_round_matches):
        marker = match.get("matchId") or id(match)
        if marker not in used_ids:
            ordered.append(match)
            used_ids.add(marker)

    return ordered


def apply_bracket_order(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nadaje kolejność meczów wewnątrz rund według drabinki.

    Wyniki ATP bywają posortowane datą/kortem. Drabinkę można odtworzyć z relacji:
    zwycięzcy poprzedniej rundy -> zawodnicy następnej rundy.

    Przykład:
    Final: A vs B
    Semifinals: szukamy meczów SF, które wygrał A i B, w tej kolejności.
    Quarterfinals: potem z par SF odtwarzamy kolejność QF itd.
    """
    for idx, match in enumerate(matches):
        match["_originalIndex"] = idx

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for match in matches:
        round_key = str(match.get("round") or "")
        groups.setdefault(round_key, []).append(match)

    ordered_by_round: Dict[str, List[Dict[str, Any]]] = {}

    main_chain = ["F", "SF", "QF", "R16", "R32", "R64", "R128"]

    # Startujemy od najwyższej dostępnej rundy, np. F dla zakończonych turniejów,
    # albo R128 dla świeżo rozpoczętego turnieju.
    start_index = None
    for idx, round_key in enumerate(main_chain):
        if round_key in groups:
            start_index = idx
            ordered_by_round[round_key] = original_order(groups[round_key])
            break

    if start_index is not None:
        for idx in range(start_index + 1, len(main_chain)):
            previous_round = main_chain[idx]
            next_round = main_chain[idx - 1]

            if previous_round not in groups:
                continue

            if next_round in ordered_by_round:
                ordered_by_round[previous_round] = order_previous_round_by_next_round(
                    groups[previous_round],
                    ordered_by_round[next_round]
                )
            else:
                ordered_by_round[previous_round] = original_order(groups[previous_round])

    # Kwalifikacje jako osobna mała drabinka.
    if "Q2" in groups:
        ordered_by_round["Q2"] = original_order(groups["Q2"])

    if "Q1" in groups:
        if "Q2" in ordered_by_round:
            ordered_by_round["Q1"] = order_previous_round_by_next_round(groups["Q1"], ordered_by_round["Q2"])
        else:
            ordered_by_round["Q1"] = original_order(groups["Q1"])

    # Pozostałe nietypowe rundy zostawiamy w kolejności źródłowej.
    for round_key, round_matches in groups.items():
        if round_key not in ordered_by_round:
            ordered_by_round[round_key] = original_order(round_matches)

    for round_key, round_matches in ordered_by_round.items():
        for order_index, match in enumerate(round_matches, start=1):
            match["bracketOrder"] = order_index

    display_round_order = {
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

    cleaned: List[Dict[str, Any]] = []
    for match in matches:
        match.pop("_originalIndex", None)
        cleaned.append(match)

    return sorted(
        cleaned,
        key=lambda match: (
            display_round_order.get(str(match.get("round") or ""), 999),
            int(match.get("bracketOrder") or 9999),
            str(match.get("date") or ""),
            str(match.get("matchId") or ""),
        )
    )

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

    clean_matches = apply_bracket_order(clean_matches)

    players = list(players_seen.values())
    players.sort(key=lambda p: p["name"])
    return players, clean_matches


def current_draw_url_from_archive(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"(/en/scores/)archive/([^/]+)/([^/]+)/20\d{2}/draws", url)
    if match:
        return f"{match.group(1)}current/{match.group(2)}/{match.group(3)}/draws"
    return None


def normalize_draw_round(text: Optional[str]) -> Tuple[str, str]:
    label = normalize_space(text or "")
    lower = label.lower()

    if "round of 128" in lower or "r128" in lower:
        return "R128", "Round of 128"
    if "round of 64" in lower or "r64" in lower:
        return "R64", "Round of 64"
    if "round of 32" in lower or "r32" in lower:
        return "R32", "Round of 32"
    if "round of 16" in lower or "r16" in lower:
        return "R16", "Round of 16"
    if "quarter" in lower or "qf" == lower:
        return "QF", "Quarterfinals"
    if "semi" in lower or "sf" == lower:
        return "SF", "Semifinals"
    if "final" in lower and "semi" not in lower:
        return "F", "Final"
    if "2nd round qualifying" in lower or "q2" == lower:
        return "Q2", "2nd Round Qualifying"
    if "1st round qualifying" in lower or "q1" == lower:
        return "Q1", "1st Round Qualifying"

    return label or "Round", label or "Round"


def full_name_from_player_href(href: Optional[str]) -> Tuple[str, str]:
    if not href:
        return "", ""

    match = re.search(r"/players/([^/]+)/([^/]+)/overview", href, flags=re.IGNORECASE)
    if not match:
        return "", ""

    slug = match.group(1)
    player_id = match.group(2).upper()

    name = " ".join(part.capitalize() for part in slug.split("-") if part)
    return name, player_id


def player_id_from_stats_item(stats_item: Any) -> str:
    link = stats_item.select_one(".name a[href]")
    if link:
        _, player_id = full_name_from_player_href(link.get("href"))
        if player_id:
            return player_id

    img = stats_item.select_one("img[src*='player-headshot']")
    if img:
        src = img.get("src") or ""
        match = re.search(r"/player-headshot/([^/?#]+)", src)
        if match:
            value = match.group(1).upper()
            if value != "0":
                return value

    return ""


def clean_draw_display_name(value: str) -> str:
    value = normalize_space(value)
    value = re.sub(r"\s+\([^)]*\)$", "", value).strip()
    return value


def extract_country_from_stats_item(stats_item: Any) -> str:
    use = stats_item.select_one("svg.atp-flag use[href]")
    if not use:
        return ""
    href = use.get("href") or ""
    match = re.search(r"#flag-([a-z]{2,3})", href, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def extract_score_tokens_from_stats_item(stats_item: Any) -> List[str]:
    tokens: List[str] = []

    for score_item in stats_item.select(".scores .score-item"):
        spans = [normalize_space(span.get_text(" ", strip=True)) for span in score_item.select("span")]
        spans = [span for span in spans if span and span != "-"]
        if not spans:
            continue
        tokens.append(" ".join(spans))

    return tokens


def extract_draw_player(stats_item: Any) -> Dict[str, Any]:
    name_el = stats_item.select_one(".name")
    link = name_el.select_one("a[href]") if name_el else None

    display_name = ""
    full_name = ""
    player_id = player_id_from_stats_item(stats_item)

    if link:
        display_name = clean_draw_display_name(link.get_text(" ", strip=True))
        full_name_from_href, id_from_href = full_name_from_player_href(link.get("href"))
        full_name = full_name_from_href or display_name
        player_id = player_id or id_from_href
    elif name_el:
        display_name = clean_draw_display_name(name_el.get_text(" ", strip=True))
        full_name = display_name

    if not display_name:
        display_name = full_name or "TBD"
    if not full_name:
        full_name = display_name

    score_tokens = extract_score_tokens_from_stats_item(stats_item)

    return {
        "id": player_id,
        "displayName": display_name,
        "fullName": full_name,
        "nameKey": player_key(full_name or display_name),
        "country": extract_country_from_stats_item(stats_item),
        "scoreTokens": score_tokens,
        "isWinner": bool(stats_item.select_one(".winner")),
    }


def score_from_draw_players(player1: Dict[str, Any], player2: Dict[str, Any]) -> str:
    p1_scores = list(player1.get("scoreTokens") or [])
    p2_scores = list(player2.get("scoreTokens") or [])

    joined = " ".join(p1_scores + p2_scores).upper()
    if "W/O" in joined or "WALKOVER" in joined:
        return "W/O"

    if not p1_scores and not p2_scores:
        return ""

    if player2.get("isWinner"):
        score = make_score_from_displayed_numbers(p2_scores, p1_scores)
    else:
        score = make_score_from_displayed_numbers(p1_scores, p2_scores)

    if score:
        if "RET" in joined and "RET" not in score:
            score = f"{score} RET"
        return score

    # Awaryjnie, jeśli ATP podało nietypowy tekst.
    winner_scores = p2_scores if player2.get("isWinner") else p1_scores
    return " ".join(winner_scores).strip()


def draw_item_to_match(item: Any, round_short: str, round_long: str, bracket_order: int) -> Optional[Dict[str, Any]]:
    stats_items = item.select(".draw-stats > .stats-item")
    if len(stats_items) < 2:
        stats_items = item.select(".stats-item")

    if len(stats_items) < 2:
        return None

    p1 = extract_draw_player(stats_items[0])
    p2 = extract_draw_player(stats_items[1])

    if not p1.get("displayName") and not p2.get("displayName"):
        return None

    winner = ""
    if p1.get("isWinner"):
        winner = p1.get("fullName") or p1.get("displayName") or ""
    elif p2.get("isWinner"):
        winner = p2.get("fullName") or p2.get("displayName") or ""

    score = score_from_draw_players(p1, p2)

    return {
        "bracketOrder": bracket_order,
        "round": round_short,
        "roundLong": round_long,
        "player1": p1.get("displayName") or "",
        "player1FullName": p1.get("fullName") or "",
        "player1Id": p1.get("id") or "",
        "player1Country": p1.get("country") or "",
        "player1ScoreTokens": p1.get("scoreTokens") or [],
        "player2": p2.get("displayName") or "",
        "player2FullName": p2.get("fullName") or "",
        "player2Id": p2.get("id") or "",
        "player2Country": p2.get("country") or "",
        "player2ScoreTokens": p2.get("scoreTokens") or [],
        "winnerName": winner,
        "formattedScore": score,
    }


def extract_draw_from_html(html_text: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    rounds: List[Dict[str, Any]] = []

    draw_columns = soup.select(".atp-draw-container .draw")
    if not draw_columns:
        draw_columns = soup.select(".draw")

    for draw_column in draw_columns:
        header = draw_column.select_one(".draw-header")
        header_text = normalize_space(header.get_text(" ", strip=True)) if header else ""

        # Pomijamy szablony Vue bez realnej zawartości.
        draw_items = draw_column.select(".draw-content > .draw-item")
        if not draw_items:
            draw_items = draw_column.select(".draw-item")

        if not header_text or not draw_items:
            continue

        round_short, round_long = normalize_draw_round(header_text)

        matches: List[Dict[str, Any]] = []
        for idx, item in enumerate(draw_items, start=1):
            match = draw_item_to_match(item, round_short, round_long, idx)
            if match:
                matches.append(match)

        if matches:
            rounds.append(
                {
                    "round": round_short,
                    "roundLong": round_long,
                    "sourceHeader": header_text,
                    "count": len(matches),
                    "matches": matches,
                }
            )

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

    rounds.sort(key=lambda item: round_order.get(str(item.get("round") or ""), 999))
    return rounds


def fetch_tournament_draw(tournament: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    draws_url_raw = tournament.get("drawsUrl")
    current_url = current_draw_url_from_archive(draws_url_raw)

    candidates: List[str] = []

    if tournament.get("isLive") and current_url:
        candidates.append(current_url)

    if draws_url_raw and draws_url_raw not in candidates:
        candidates.append(draws_url_raw)

    if current_url and current_url not in candidates:
        candidates.append(current_url)

    last_error: Optional[str] = None

    for candidate in candidates:
        full_url = absolute_url(candidate)
        if not full_url:
            continue

        try:
            html_text = fetch_text(full_url, referer="https://www.atptour.com/en/tournaments")
            rounds = extract_draw_from_html(html_text)
            if rounds:
                return rounds, full_url
        except Exception as exc:
            last_error = f"{full_url}: {exc}"
            print(f"WARN draw page failed: {last_error}")
            time.sleep(REQUEST_SLEEP_SECONDS)

    print(f"WARN no draw parsed for {tournament.get('name')}: {last_error}")
    return [], None

def month_to_number(month_name: str) -> int:
    month = normalize_space(month_name or "").lower()
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    return month_map.get(month[:3], month_map.get(month, 0))


def parse_tournament_date_range(date_text: str, fallback_year: Optional[int] = None) -> Tuple[str, str]:
    """Zwraca start/end turnieju z oryginalnego zakresu ATP.

    To NIE jest data meczu. Używamy tego tylko do sortowania turniejów w historii.
    """
    text = normalize_space(date_text or "")
    if not text:
        return "", ""

    match = re.search(
        r"(\d{1,2})\s*([A-Za-z]+)?\s*[-–]\s*(\d{1,2})\s*([A-Za-z]+)\s*,?\s*(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", ""

    start_day = int(match.group(1))
    start_month_name = match.group(2) or match.group(4)
    end_day = int(match.group(3))
    end_month_name = match.group(4)
    year = int(match.group(5) or fallback_year or 0)

    start_month = month_to_number(start_month_name)
    end_month = month_to_number(end_month_name)

    if not start_month or not end_month or not year:
        return "", ""

    try:
        # ATP zapisuje turnieje na granicy roku zwykle jako:
        # 30 Dec - 5 Jan, 2025
        # Rok przy końcu zakresu oznacza wtedy rok daty końcowej,
        # więc start jest w roku poprzednim: 2024-12-30, koniec 2025-01-05.
        start_year = year
        end_year = year

        if start_month > end_month:
            start_year = year - 1

        start_date = datetime(start_year, start_month, start_day).date()
        end_date = datetime(end_year, end_month, end_day).date()

        # Awaryjnie dla nietypowych zakresów zapisanych odwrotnie.
        if end_date < start_date:
            end_date = datetime(end_year + 1, end_month, end_day).date()

        return start_date.isoformat(), end_date.isoformat()
    except Exception:
        return "", ""


def extract_tournament_date_from_results_html(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    page_text = normalize_space(soup.get_text(" ", strip=True))

    # Przykład nagłówka ATP:
    # London, Great Britain | 30 Jun - 13 Jul, 2025
    match = re.search(
        r"\|\s*(\d{1,2}\s*[A-Za-z]*\s*[-–]\s*\d{1,2}\s+[A-Za-z]+,?\s*20\d{2})",
        page_text,
        flags=re.IGNORECASE,
    )
    if match:
        return normalize_space(match.group(1))

    match = re.search(
        r"(\d{1,2}\s*[A-Za-z]*\s*[-–]\s*\d{1,2}\s+[A-Za-z]+,?\s*20\d{2})",
        page_text,
        flags=re.IGNORECASE,
    )
    if match:
        return normalize_space(match.group(1))

    return ""


def update_tournament_original_date_from_results(tournament: Dict[str, Any], html_text: str) -> None:
    date_from_page = extract_tournament_date_from_results_html(html_text)

    if not date_from_page:
        date_from_page = str(tournament.get("date") or "")

    year_value = str(tournament.get("year") or "")
    fallback_year = int(year_value) if year_value.isdigit() else None
    start_date, end_date = parse_tournament_date_range(date_from_page, fallback_year)

    if date_from_page:
        tournament["date"] = date_from_page
        tournament["dateSource"] = "results_header_or_calendar"

    if start_date:
        tournament["startDate"] = start_date
        tournament["tournamentStartDate"] = start_date

    if end_date:
        tournament["endDate"] = end_date
        tournament["tournamentEndDate"] = end_date


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
            update_tournament_original_date_from_results(tournament, html_text)
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



def slug_from_name(name: str) -> str:
    value = unicodedata.normalize("NFKD", normalize_space(name or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def parse_atp_date_to_iso(value: Optional[str]) -> str:
    text_value = normalize_space(value or "")
    if not text_value:
        return ""

    # Przykład: Sun, 24 May, 2026
    for pattern in ("%a, %d %B, %Y", "%d %B, %Y"):
        try:
            return datetime.strptime(text_value, pattern).date().isoformat()
        except Exception:
            pass

    match = re.search(r"(\d{1,2})\s+([A-Za-z]+),\s+(20\d{2})", text_value)
    if match:
        try:
            return datetime.strptime(match.group(0), "%d %B, %Y").date().isoformat()
        except Exception:
            pass

    return ""


def names_equal_for_history(a: Optional[str], b: Optional[str]) -> bool:
    return player_key(a) == player_key(b)


def collect_draw_player_meta(draw_rounds: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}

    for round_item in draw_rounds or []:
        for match in round_item.get("matches", []) or []:
            for prefix in ("player1", "player2"):
                full_name = match.get(f"{prefix}FullName") or match.get(prefix) or ""
                display_name = match.get(prefix) or full_name
                player_id = match.get(f"{prefix}Id") or ""

                key = player_key(full_name or display_name)
                if not key:
                    continue

                current = result.get(key, {})
                result[key] = {
                    "key": key,
                    "name": current.get("name") or full_name or display_name,
                    "displayName": current.get("displayName") or display_name or full_name,
                    "playerId": current.get("playerId") or player_id,
                }

    return result


def ranking_week_for_date(date_iso: str) -> str:
    """Zwraca poniedziałek rankingu ATP obowiązujący w dniu meczu."""
    if not date_iso:
        return ""

    try:
        date_value = datetime.fromisoformat(date_iso).date()
        monday = date_value - timedelta(days=date_value.weekday())
        return monday.isoformat()
    except Exception:
        return ""


def ranking_candidate_urls(ranking_date: str) -> List[str]:
    # ATP zmieniało parametry strony rankingów. Próbujemy kilka wariantów.
    return [
        f"{ATP_BASE_URL}/en/rankings/singles?rankRange=0-5000&dateWeek={ranking_date}",
        f"{ATP_BASE_URL}/en/rankings/singles?rankRange=0-5000&rankDate={ranking_date}",
        f"{ATP_BASE_URL}/en/rankings/singles?rankRange=0-5000&date={ranking_date}",
        f"{ATP_BASE_URL}/en/rankings/singles?dateWeek={ranking_date}&rankRange=0-5000",
    ]


def parse_ranking_rows_from_html(html_text: str, ranking_date: str, source_url: str) -> Dict[str, Dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    players: Dict[str, Dict[str, Any]] = {}

    # 1) Najpierw próbujemy parsować normalne wiersze tabeli.
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

        # Rank zwykle jest pierwszą liczbą w wierszu.
        rank = None
        rank_match = re.search(r"^\s*(\d{1,4})\b", row_text)
        if not rank_match:
            rank_match = re.search(r"\bRank\s*#?\s*(\d{1,4})\b", row_text, flags=re.IGNORECASE)

        if rank_match:
            rank = int(rank_match.group(1))

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
            "rankingDate": ranking_date,
            "rankingType": "historical_week",
            "source": source_url,
        }

    # 2) Awaryjnie: jeśli tabela nie zadziała, szukamy linków do zawodników w kolejności strony.
    # W takim trybie rank jest kolejnością wystąpienia, więc używamy tylko jeśli nic nie znaleziono.
    if not players:
        seen = set()
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
                "rankingDate": ranking_date,
                "rankingType": "historical_week_inferred_order",
                "source": source_url,
            }

    return players


def fetch_historical_rankings_for_week(ranking_date: str) -> Dict[str, Dict[str, Any]]:
    if not ranking_date:
        return {}

    for url in ranking_candidate_urls(ranking_date):
        try:
            html_text = fetch_text(url, referer="https://www.atptour.com/en/rankings/singles")
            players = parse_ranking_rows_from_html(html_text, ranking_date, url)

            if players:
                print(f"Ranking {ranking_date}: {len(players)} players from {url}")
                return players

        except Exception as exc:
            print(f"WARN ranking fetch failed {ranking_date} {url}: {exc}")
            time.sleep(REQUEST_SLEEP_SECONDS)

    print(f"WARN no ranking parsed for {ranking_date}")
    return {}


def normalize_ranking_players_payload(players_payload: Any) -> Dict[str, Dict[str, Any]]:
    """Obsługuje oba formaty rankingów:
    1) stary/nowy updater: {"players": {"janniksinner": {...}}}
    2) osobny ranking workflow: {"players": [{"nameKey": "janniksinner", ...}, ...]}
    """
    normalized: Dict[str, Dict[str, Any]] = {}

    if isinstance(players_payload, dict):
        for key, value in players_payload.items():
            if not isinstance(value, dict):
                continue

            normalized_key = (
                str(value.get("nameKey") or "")
                or str(value.get("displayNameKey") or "")
                or str(value.get("key") or "")
                or str(key or "")
            )

            if not normalized_key:
                normalized_key = player_key(value.get("name") or value.get("displayName") or "")

            if normalized_key:
                normalized[normalized_key] = value

        return normalized

    if isinstance(players_payload, list):
        for value in players_payload:
            if not isinstance(value, dict):
                continue

            normalized_key = (
                str(value.get("nameKey") or "")
                or str(value.get("displayNameKey") or "")
                or str(value.get("key") or "")
                or player_key(value.get("name") or value.get("displayName") or "")
            )

            if normalized_key:
                normalized[normalized_key] = {
                    **value,
                    "key": normalized_key,
                }

    return normalized


def ranking_file_candidates(ranking_date: str) -> List[Path]:
    return [
        DATA_DIR / "rankings" / "singles" / f"{ranking_date}.json",
        DATA_DIR / "rankings" / f"{ranking_date}.json",
    ]


def load_or_fetch_historical_rankings(ranking_dates: List[str], generated_at: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    rankings_by_date: Dict[str, Dict[str, Dict[str, Any]]] = {}
    rankings_dir = DATA_DIR / "rankings" / "singles"
    rankings_dir.mkdir(parents=True, exist_ok=True)

    unique_dates = sorted({date for date in ranking_dates if date})

    for ranking_date in unique_dates:
        existing_players: Dict[str, Dict[str, Any]] = {}

        # Najpierw czytamy istniejące rankingi z data/rankings/singles.
        # To jest miejsce, gdzie masz już komplet rankingów 2025/2026.
        for candidate_path in ranking_file_candidates(ranking_date):
            existing = load_existing_json(candidate_path)

            if not isinstance(existing, dict):
                continue

            normalized = normalize_ranking_players_payload(existing.get("players"))

            if normalized:
                existing_players = normalized
                break

        if existing_players:
            rankings_by_date[ranking_date] = existing_players
            continue

        # Jeśli pliku nie było, pobieramy ranking i zapisujemy już do data/rankings/singles.
        players = fetch_historical_rankings_for_week(ranking_date)
        rankings_by_date[ranking_date] = players

        save_json(
            rankings_dir / f"{ranking_date}.json",
            {
                "generatedAt": generated_at,
                "source": ranking_candidate_urls(ranking_date)[0],
                "rankingDate": ranking_date,
                "count": len(players),
                "players": list(players.values()),
            },
        )

        time.sleep(REQUEST_SLEEP_SECONDS)

    save_json(
        DATA_DIR / "rankings_index.json",
        {
            "generatedAt": generated_at,
            "source": "data/rankings/singles/*.json",
            "count": len(unique_dates),
            "items": [
                {
                    "rankingDate": date,
                    "count": len(rankings_by_date.get(date, {})),
                    "path": f"data/rankings/singles/{date}.json",
                }
                for date in unique_dates
            ],
        },
    )

    return rankings_by_date



def rank_for_player_on_date(rankings_by_date: Dict[str, Dict[str, Dict[str, Any]]], player_key_value: str, date_iso: str) -> Tuple[Optional[int], str]:
    ranking_date = ranking_week_for_date(date_iso)
    if not ranking_date:
        return None, ""

    ranking_players = rankings_by_date.get(ranking_date, {})
    item = ranking_players.get(player_key_value)

    if not isinstance(item, dict):
        return None, ranking_date

    rank = item.get("rank")
    try:
        return int(rank), ranking_date
    except Exception:
        return None, ranking_date

def build_player_histories_from_matches(
    generated_at: str,
    tournament_match_payloads: List[Dict[str, Any]],
    draw_meta_by_player_key: Dict[str, Dict[str, str]],
) -> None:
    histories: Dict[str, List[Dict[str, Any]]] = {}
    player_meta: Dict[str, Dict[str, str]] = {}

    def remember_player(name: str, player_id: str = "") -> str:
        key = player_key(name)
        if not key:
            return ""

        meta_from_draw = draw_meta_by_player_key.get(key, {})
        player_meta[key] = {
            "key": key,
            "name": meta_from_draw.get("name") or name,
            "displayName": meta_from_draw.get("displayName") or name,
            "playerId": meta_from_draw.get("playerId") or player_id or "",
        }
        return key

    for payload in tournament_match_payloads:
        tournament = payload.get("tournament", {}) or {}
        matches = payload.get("matches", []) or []

        for match in matches:
            player_name = match.get("playerName") or ""
            opponent_name = match.get("opponentName") or ""
            winner_name = match.get("winnerName") or player_name

            if not player_name or not opponent_name:
                continue

            player_key_value = remember_player(player_name, match.get("playerId") or "")
            opponent_key_value = remember_player(opponent_name, match.get("opponentId") or "")

            if not player_key_value or not opponent_key_value:
                continue

            score = match.get("formattedScore") or ""
            # Ważne: daty mają być tylko oryginalne z ATP.
            # Nie wyliczamy dat po rundzie ani po dacie końca turnieju.
            date_text = match.get("date") or ""
            date_iso = parse_atp_date_to_iso(date_text)

            player_won = names_equal_for_history(winner_name, player_name)
            opponent_won = names_equal_for_history(winner_name, opponent_name)

            base_info = {
                "date": date_text,
                "dateIso": date_iso,
                "tournamentId": tournament.get("id") or "",
                "tournamentYear": tournament.get("year") or "",
                "tournamentName": tournament.get("name") or "",
                "tournamentType": tournament.get("type") or "",
                "tournamentDate": tournament.get("date") or "",
                "tournamentStartDate": tournament.get("tournamentStartDate") or tournament.get("startDate") or "",
                "tournamentEndDate": tournament.get("tournamentEndDate") or tournament.get("endDate") or "",
                "surface": tournament.get("surface") or "",
                "round": match.get("round") or "",
                "roundLong": match.get("roundLong") or "",
                "score": score,
                "matchId": match.get("matchId") or "",
                "reason": match.get("reason"),
            }

            histories.setdefault(player_key_value, []).append(
                {
                    **base_info,
                    "playerName": player_name,
                    "opponentName": opponent_name,
                    "opponentKey": opponent_key_value,
                    "result": "W" if player_won else "L",
                }
            )

            histories.setdefault(opponent_key_value, []).append(
                {
                    **base_info,
                    "playerName": opponent_name,
                    "opponentName": player_name,
                    "opponentKey": player_key_value,
                    "result": "W" if opponent_won else "L",
                }
            )

    # Rankingi historyczne: bierzemy ranking z poniedziałku obowiązującego w dniu meczu.
    ranking_dates: List[str] = []

    for items in histories.values():
        for item in items:
            ranking_date = ranking_week_for_date(item.get("dateIso") or "")
            if ranking_date:
                ranking_dates.append(ranking_date)

    rankings_by_date = load_or_fetch_historical_rankings(ranking_dates, generated_at)

    history_index: List[Dict[str, Any]] = []

    history_dir = DATA_DIR / "player-history"
    history_dir.mkdir(parents=True, exist_ok=True)

    for key, items in histories.items():
        items.sort(
            key=lambda item: (
                item.get("dateIso") or "",
                item.get("tournamentYear") or "",
                item.get("tournamentName") or "",
            ),
            reverse=True,
        )

        try:
            generated_date = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).date()
        except Exception:
            generated_date = datetime.now(timezone.utc).date()

        history_start_date = generated_date.replace(year=generated_date.year - 1, month=1, day=1)

        last_year_matches: List[Dict[str, Any]] = []
        for item in items:
            date_iso = item.get("dateIso") or ""
            include_item = False

            try:
                include_item = datetime.fromisoformat(date_iso).date() >= history_start_date
            except Exception:
                include_item = True

            if include_item:
                last_year_matches.append(item)

        player_rank = None

        for item in last_year_matches:
            match_date_iso = item.get("dateIso") or ""

            player_rank, player_ranking_date = rank_for_player_on_date(rankings_by_date, key, match_date_iso)
            opponent_rank, opponent_ranking_date = rank_for_player_on_date(
                rankings_by_date,
                item.get("opponentKey") or "",
                match_date_iso,
            )

            item["playerRank"] = player_rank
            item["opponentRank"] = opponent_rank
            item["rankingDate"] = player_ranking_date or opponent_ranking_date
            item["rankingNote"] = "historical_week"

        meta = player_meta.get(key, {"name": key, "displayName": key, "playerId": ""})
        payload = {
            "generatedAt": generated_at,
            "note": "Historia jest budowana z meczów zapisanych w tym repo. Zakres: od 1 stycznia poprzedniego roku, np. cały 2025 i 2026. Rankingi są z tygodnia meczu, jeśli udało się je pobrać.",
            "historyStartDate": history_start_date.isoformat(),
            "player": meta,
            "count": len(last_year_matches),
            "matches": last_year_matches,
        }

        save_json(history_dir / f"{key}.json", payload)

        history_index.append(
            {
                "key": key,
                "name": meta.get("name") or meta.get("displayName") or key,
                "displayName": meta.get("displayName") or meta.get("name") or key,
                "playerId": meta.get("playerId") or "",
                "rank": player_rank,
                "count": len(last_year_matches),
                "path": f"data/player-history/{key}.json",
            }
        )

    history_index.sort(key=lambda item: item.get("name") or "")

    save_json(
        DATA_DIR / "player_history_index.json",
        {
            "generatedAt": generated_at,
            "count": len(history_index),
            "items": history_index,
        },
    )


def extract_score_slug_and_id(tournament: Dict[str, Any]) -> Tuple[str, str]:
    for key in ("scoresUrl", "drawsUrl", "scheduleUrl"):
        url = str(tournament.get(key) or "")
        match = re.search(r"/en/scores/(?:archive|current)/([^/]+)/([^/]+)(?:/20\d{2})?/", url)
        if match:
            return match.group(1), match.group(2)

    return "", str(tournament.get("id") or "")


def build_archive_url(slug: str, event_id: str, year: int, page: str) -> str:
    if not slug or not event_id:
        return ""
    return f"/en/scores/archive/{slug}/{event_id}/{year}/{page}"


def synthesize_year_from_reference(reference_tournaments: List[Dict[str, Any]], target_year: int) -> List[Dict[str, Any]]:
    """Awaryjnie tworzy listę turniejów dla roku historycznego.

    ATP endpoint kalendarza nie zawsze zwraca stare lata. Wyniki archiwalne ATP
    mają jednak przewidywalne adresy:
    /en/scores/archive/{slug}/{id}/{year}/results

    Ta funkcja bierze znane ID/slug turniejów z aktualnego kalendarza i buduje
    odpowiedniki dla target_year. Nie jest to idealny kalendarz historyczny,
    ale pozwala pobrać większość wyników 2025 zamiast dostać pustą historię.
    """
    synthetic: List[Dict[str, Any]] = []

    for tournament in reference_tournaments:
        slug, event_id = extract_score_slug_and_id(tournament)
        if not slug or not event_id:
            continue

        item = dict(tournament)
        item["year"] = str(target_year)
        item["date"] = ""
        item["month"] = ""
        item["isLive"] = False
        item["isPastEvent"] = True
        item["scoresUrl"] = build_archive_url(slug, event_id, target_year, "results")
        item["drawsUrl"] = build_archive_url(slug, event_id, target_year, "draws")
        item["scheduleUrl"] = build_archive_url(slug, event_id, target_year, "schedule")
        item["syntheticHistoricalFallback"] = True
        item["syntheticSourceYear"] = tournament.get("year")
        synthetic.append(item)

    return synthetic


def ensure_history_years_available(flat_tournaments: List[Dict[str, Any]], years: List[int]) -> List[Dict[str, Any]]:
    result = list(flat_tournaments)

    years_present = {
        int(str(item.get("year") or "0"))
        for item in result
        if str(item.get("year") or "").isdigit()
    }

    reference_year = max(years_present) if years_present else None
    reference_tournaments = [
        item for item in result
        if reference_year is not None and str(item.get("year") or "") == str(reference_year)
    ]

    existing_keys = {
        (str(item.get("year") or ""), str(item.get("id") or ""))
        for item in result
    }

    for year in years:
        if year in years_present:
            continue

        print(f"WARN calendar for {year} missing, creating archive fallback from {reference_year}")
        synthetic = synthesize_year_from_reference(reference_tournaments, year)

        added = 0
        for item in synthetic:
            key = (str(item.get("year") or ""), str(item.get("id") or ""))
            if key in existing_keys:
                continue
            result.append(item)
            existing_keys.add(key)
            added += 1

        print(f"Fallback {year}: added {added} synthetic archive tournaments")

    result.sort(key=lambda item: (str(item.get("year") or ""), str(item.get("month") or ""), str(item.get("date") or ""), str(item.get("id") or "")))
    return result


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    print("Fetching ATP calendars...")
    flat_tournaments, calendar_sources = flatten_multi_year_calendars(HISTORY_YEARS)
    flat_tournaments = ensure_history_years_available(flat_tournaments, HISTORY_YEARS)

    save_json(
        DATA_DIR / "tournaments.json",
        {
            "source": ATP_CALENDAR_URL,
            "years": HISTORY_YEARS,
            "generatedAt": generated_at,
            "countSources": len(calendar_sources),
            "sources": calendar_sources,
        },
    )

    save_json(
        DATA_DIR / "tournaments_flat.json",
        {
            "source": ATP_CALENDAR_URL,
            "years": HISTORY_YEARS,
            "generatedAt": generated_at,
            "count": len(flat_tournaments),
            "note": "Jeśli ATP nie zwróciło kalendarza historycznego, część turniejów z poprzedniego roku mogła zostać utworzona jako archive fallback po ID/slug z aktualnego kalendarza.",
            "tournaments": flat_tournaments,
        },
    )

    selected = select_tournaments_for_results(flat_tournaments)
    print(f"Generating results for {len(selected)} tournaments...")

    index_items: List[Dict[str, Any]] = []
    tournament_match_payloads: List[Dict[str, Any]] = []
    draw_meta_by_player_key: Dict[str, Dict[str, str]] = {}

    for index, tournament in enumerate(selected, start=1):
        year = str(tournament.get("year") or "")
        event_id = str(tournament.get("id") or "")
        name = tournament.get("name")
        print(f"[{index}/{len(selected)}] Tournament: {year}/{event_id} {name}")

        try:
            players, matches, source_url = fetch_tournament_results(tournament)
        except Exception as exc:
            print(f"WARN tournament results failed: {year}/{event_id} {name}: {exc}")
            players, matches, source_url = [], [], None

        try:
            draw_rounds, draw_source_url = fetch_tournament_draw(tournament)
        except Exception as exc:
            print(f"WARN tournament draw failed: {year}/{event_id} {name}: {exc}")
            draw_rounds, draw_source_url = [], None

        folder = DATA_DIR / year / event_id
        save_json(folder / "tournament.json", tournament)

        draw_match_count = sum(len(round_item.get("matches", [])) for round_item in draw_rounds)
        draw_player_meta = collect_draw_player_meta(draw_rounds)
        draw_meta_by_player_key.update(draw_player_meta)

        save_json(
            folder / "draw.json",
            {
                "generatedAt": generated_at,
                "source": draw_source_url,
                "tournament": tournament,
                "countRounds": len(draw_rounds),
                "countMatches": draw_match_count,
                "rounds": draw_rounds,
            },
        )
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

        if isinstance(saved_matches_payload, dict):
            tournament_match_payloads.append(saved_matches_payload)

        index_items.append(
            {
                "year": year,
                "id": event_id,
                "name": name,
                "players": len(players),
                "matches": saved_matches_count,
                "drawRounds": len(draw_rounds),
                "drawMatches": draw_match_count,
                "matchesPath": f"data/{year}/{event_id}/matches.json",
                "drawPath": f"data/{year}/{event_id}/draw.json",
                "source": source_url,
                "drawSource": draw_source_url,
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

    print("Building player histories...")
    build_player_histories_from_matches(
        generated_at=generated_at,
        tournament_match_payloads=tournament_match_payloads,
        draw_meta_by_player_key=draw_meta_by_player_key,
    )

    print("Done.")


if __name__ == "__main__":
    main()
