# ATP data v36 - Playwright subprocess, 6h

Co naprawia:
- częstotliwość wraca na 6 godzin,
- naprawia błąd z logów:
  `Playwright Sync API inside the asyncio loop`,
- naprawia problem braku Chromium:
  workflow instaluje i testuje Playwright Chromium przed update,
- Playwright działa w osobnym procesie `scripts/playwright_fetch.py`,
  więc nie zostawia uszkodzonego kontekstu po błędzie,
- w trybie `live` skrypt używa istniejącego `tournaments_flat.json`
  i nie próbuje od nowa pobierać całego kalendarza ATP,
- aktualizuje tylko live turnieje, chyba że ręcznie wybierzesz `full`.

Wrzucić do repo `atp-data`:
- `scripts/update_atp.py`
- `scripts/playwright_fetch.py`
- `.github/workflows/main.yml`
- `requirements.txt`
- opcjonalnie `run_update_local.bat`

Po wrzuceniu uruchom workflow ręcznie z `update_mode=live`.
W logu szukaj:
- `Playwright Chromium OK`
- `UPDATE_MODE=live; using existing tournaments_flat.json`
- `WARN requests got 403, trying Playwright subprocess`
