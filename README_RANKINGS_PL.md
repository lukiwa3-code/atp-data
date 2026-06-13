# ATP Rankings updater v1

To jest osobny updater rankingów ATP.

Wgraj do repo `atp-data`:

- `scripts/update_rankings.py`
- `scripts/playwright_fetch.py`
- `.github/workflows/rankings.yml`
- `requirements.txt`

Nie podmieniaj tym `main.yml`, bo `main.yml` jest od wyników turniejów.

## Jak działa

- `rankings.yml` uruchamia tylko `scripts/update_rankings.py`
- nie uruchamia `scripts/update_atp.py`
- zapisuje pliki do `data/rankings/YYYY-MM-DD.json`
- aktualizuje `data/rankings_index.json`
- przy 403 próbuje Playwright
- jeśli ranking się nie pobierze albo parser widzi 0 zawodników, nie kasuje starego pliku

## Ręczne uruchomienie

GitHub → Actions → Update ATP Rankings → Run workflow

Domyślnie:
- `start_date = 2025-01-01`
- `end_date` puste, czyli aktualny poniedziałek
- `force = false`

## Harmonogram

Co poniedziałek o 11:00 UTC pobiera ostatnie 8 tygodni.
