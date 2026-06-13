# ATP data v35 - 6h + Playwright fallback + live mode

Uwaga:
- Częstotliwość 2h/6h NIE była przyczyną problemu.
- Logi pokazały właściwą przyczynę: GitHub Actions dostaje 403 Forbidden z ATP.

Zmiany:
- schedule wraca na 6 godzin: `0 */6 * * *`,
- jeśli `requests` dostaje 403, skrypt próbuje pobrać stronę przez Playwright/Chromium,
- automatyczny workflow aktualizuje domyślnie tylko turnieje live (`UPDATE_MODE=live`),
  żeby nie odpalać 400+ stron przez przeglądarkę,
- ręcznie można odpalić `UPDATE_MODE=full`,
- zostaje ochrona przed nadpisaniem istniejących danych zerem przy 403,
- dodany `run_update_local.bat` z wyborem live/full.

Wrzucić do repo `atp-data`:
- `scripts/update_atp.py`
- `.github/workflows/main.yml`
- `requirements.txt`
- opcjonalnie `run_update_local.bat`

Po wrzuceniu:
1. Run workflow ręcznie z `update_mode=live`.
2. Sprawdź log, czy pojawia się:
   `WARN requests got 403, trying Playwright`
3. Sprawdź `data/2026/440/matches.json` i `data/2026/321/matches.json`.

Jeśli Playwright też dostanie 403:
- GitHub Actions jest całkowicie blokowany przez ATP,
- wtedy zostaje lokalne pobieranie albo inne źródło danych.
